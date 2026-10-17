"""One background ASR job at a time (a single worker thread, FIFO).

Job state lives in the project's ``job.json``:

``NEEDS_FACTS`` (waiting for the start timecode / rate) -> ``QUEUED`` ->
``RUNNING`` -> ``DONE`` | ``FAILED``.

A project only gets ``transcript.json`` after the ASR result has been
serialized **and** accepted by the full WEB-001 build (TXE ingest, projection,
candidates). On any failure nothing partial is kept: no transcript, the media
file is deleted, the job shows a friendly Korean message, and a trial project
is given back to its invite code.
"""

import json
import queue
import threading
import time
from collections.abc import Callable
from enum import Enum

from .asr import AsrError, AsrOutput, Transcriber
from .pipeline import MediaFacts, PipelineError, TranscriptSource, build_project
from .store import JOB, MEDIA, TRANSCRIPT, ProjectNotFound, ProjectStore


class JobState(str, Enum):
    NEEDS_FACTS = "NEEDS_FACTS"
    QUEUED = "QUEUED"
    RUNNING = "RUNNING"
    DONE = "DONE"
    FAILED = "FAILED"


ACTIVE = frozenset({JobState.QUEUED, JobState.RUNNING})


def job_record(
    state: JobState, progress: float = 0.0, message: str = "", codes: tuple[str, ...] = ()
) -> dict[str, object]:
    return {
        "state": state.value,
        "progress": round(max(0.0, min(1.0, progress)), 3),
        "message": message,
        "codes": list(codes),
        "updated_at": time.time(),
    }


def read_job(store: ProjectStore, project_id: str) -> dict[str, object] | None:
    return store.read_json(project_id, JOB)


def job_state(record: dict[str, object] | None) -> JobState | None:
    if record is None:
        return None
    try:
        return JobState(str(record.get("state")))
    except ValueError:
        return None


class JobRunner:
    def __init__(
        self,
        store: ProjectStore,
        transcriber: Callable[[], Transcriber],
        on_failure: Callable[[str, dict[str, object]], None] | None = None,
    ) -> None:
        self.store = store
        self._transcriber = transcriber
        self._on_failure = on_failure
        self._queue: queue.Queue[str] = queue.Queue()
        self._lock = threading.Lock()
        self._pending: set[str] = set()
        self._thread: threading.Thread | None = None

    # ------------------------------------------------------------ public

    def active(self) -> bool:
        with self._lock:
            return bool(self._pending)

    def submit(self, project_id: str) -> None:
        self.store.write_json(project_id, JOB, job_record(JobState.QUEUED))
        with self._lock:
            self._pending.add(project_id)
            if self._thread is None or not self._thread.is_alive():
                self._thread = threading.Thread(target=self._work, name="aie-asr", daemon=True)
                self._thread.start()
        self._queue.put(project_id)

    def join(self, timeout: float = 30.0) -> bool:
        """Wait until no job is queued or running (tests / shutdown). True when idle."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if not self.active():
                return True
            time.sleep(0.02)
        return not self.active()

    # ------------------------------------------------------------ worker

    def _work(self) -> None:
        while True:
            try:
                project_id = self._queue.get(timeout=5.0)
            except queue.Empty:
                with self._lock:
                    if not self._pending:
                        self._thread = None
                        return
                continue
            try:
                self._run(project_id)
            finally:
                with self._lock:
                    self._pending.discard(project_id)

    def _set(self, project_id: str, record: dict[str, object]) -> None:
        try:
            self.store.write_json(project_id, JOB, record)
        except (ProjectNotFound, OSError):
            pass  # deleted meanwhile (expiry / user delete)

    def _run(self, project_id: str) -> None:
        try:
            meta = self.store.meta(project_id)
            media = self.store.path(project_id, MEDIA)
        except (ProjectNotFound, OSError, ValueError):
            return
        self._set(project_id, job_record(JobState.RUNNING, 0.0, "전사 중"))
        last = [0.0]

        def progress(value: float) -> None:
            if value - last[0] >= 0.02:
                last[0] = value
                self._set(project_id, job_record(JobState.RUNNING, value, "전사 중"))

        try:
            facts_data, source_data = meta.get("facts"), meta.get("source")
            if not isinstance(facts_data, dict) or not isinstance(source_data, dict):
                raise PipelineError("프로젝트 정보가 완성되지 않았습니다.", ("FACTS_MISSING",))
            facts = MediaFacts.from_json(facts_data)
            base = TranscriptSource.from_json(source_data)
            pending = meta.get("pending")
            vad = pending.get("asr_vad") if isinstance(pending, dict) else None
            output = self._transcriber().transcribe(
                media, progress, vad=vad if isinstance(vad, bool) else None
            )
            source = _with_producer(base, output)
            raw = json.dumps(output.payload, ensure_ascii=False).encode("utf-8")
            build_project(raw, source, facts)  # accepted by the full flow, or refused
            self.store.write(project_id, TRANSCRIPT, raw)
            self.store.update_meta(project_id, source=source.to_json())
        except (AsrError, PipelineError) as exc:
            self._fail(project_id, meta, exc.message, exc.codes)
            return
        except ProjectNotFound:
            return
        except Exception as exc:  # noqa: BLE001 - the decoder / model may raise anything
            self._fail(
                project_id,
                meta,
                "음성 인식 중 문제가 생겨 결과를 만들지 못했습니다. 다른 파일로 다시 시도해 주세요.",
                ("ASR_FAILED", type(exc).__name__),
            )
            return
        self._set(project_id, job_record(JobState.DONE, 1.0, "완료"))

    def _fail(
        self, project_id: str, meta: dict[str, object], message: str, codes: tuple[str, ...]
    ) -> None:
        for name in (TRANSCRIPT, MEDIA):
            try:
                self.store.remove(project_id, name)
            except (ProjectNotFound, OSError):
                pass
        self._set(project_id, job_record(JobState.FAILED, 0.0, message, codes[:5]))
        if self._on_failure is not None:
            self._on_failure(project_id, meta)


def _with_producer(base: TranscriptSource, output: AsrOutput) -> TranscriptSource:
    return TranscriptSource(
        base.tool,
        output.tool_version,
        output.model_id,
        base.offset_ms,
        base.gap_seconds,
        output.model_revision,
        output.vad_method,
        output.vad_config_digest,
        output.language_requested,
    )
