"""Local ASR behind a small interface (faster-whisper in the optional ``asr`` extra).

The web flow only depends on :class:`Transcriber`; tests inject a fake. The real
:class:`FasterWhisperTranscriber` loads the model **from the local cache only**
(``HF_HUB_OFFLINE=1``, ``local_files_only=True``, telemetry off) and fails with a
clear Korean message when the model is absent. It never downloads at runtime.

The result is serialized to the exact JSON shape that
``transcript_evidence.ingest_faster_whisper`` reads (``language``,
``language_probability``, ``segments[].id/start/end/text/words[]`` with
``word/start/end/probability``), so the WEB-001 path consumes it unchanged.
"""

import dataclasses
import hashlib
import importlib
import json
import os
import threading
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .store import Settings

FASTER_WHISPER_VERSION = "1.1.1"
VAD_METHOD = "faster-whisper vad_filter (Silero VAD v5)"

Progress = Callable[[float], None]


class AsrError(RuntimeError):
    """A friendly, user-facing ASR failure (Korean message + English codes)."""

    def __init__(self, message: str, codes: tuple[str, ...] = ()) -> None:
        super().__init__(message)
        self.message = message
        self.codes = codes


@dataclass(frozen=True)
class AsrOutput:
    payload: dict[str, object]  # faster-whisper serialized shape
    tool_version: str
    model_id: str
    model_revision: str | None
    vad_method: str | None
    vad_config_digest: str | None
    language_requested: str | None


class Transcriber(Protocol):
    def transcribe(self, media: Path, progress: Progress) -> AsrOutput: ...


def config_digest(config: dict[str, Any]) -> str:
    text = json.dumps(config, sort_keys=True, default=str)
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def _offline_environment() -> None:
    # huggingface_hub reads these at import time: no network, no telemetry.
    os.environ["HF_HUB_OFFLINE"] = "1"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["HF_HUB_DISABLE_IMPLICIT_TOKEN"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"


def decode_audio_16k(media: Path) -> Any:
    """16 kHz mono float32 samples, mirroring ``faster_whisper.audio.decode_audio``.

    faster-whisper 1.1.1 calls ``av.open(..., metadata_errors=...)``, a keyword PyAV
    14+ removed, so with the PyAV that pip resolves today (19.x) its own decoder
    raises ``TypeError``. We decode the same way (s16 mono resample, FIFO grouping,
    invalid frames skipped) and pass the array to ``WhisperModel.transcribe``.
    """
    av: Any = importlib.import_module("av")
    np: Any = importlib.import_module("numpy")
    resampler = av.audio.resampler.AudioResampler(format="s16", layout="mono", rate=16000)
    fifo = av.audio.fifo.AudioFifo()
    chunks: list[Any] = []

    def resample(frame: Any) -> None:
        for out in resampler.resample(frame):
            chunks.append(out.to_ndarray().reshape(-1))

    with av.open(str(media), mode="r") as container:
        frames = container.decode(audio=0)
        while True:
            try:
                frame = next(frames)
            except StopIteration:
                break
            except av.error.InvalidDataError:
                continue
            frame.pts = None
            fifo.write(frame)
            if fifo.samples >= 500000:
                resample(fifo.read())
        if fifo.samples > 0:
            resample(fifo.read())
        resample(None)
    if not chunks:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(chunks).astype(np.float32) / 32768.0


def serialize_result(
    segments: Any, info: Any, progress: Progress | None = None
) -> dict[str, object]:
    """faster-whisper ``(segments, info)`` -> the JSON shape ``ingest_faster_whisper`` reads."""
    duration = float(info.duration) if info.duration else 0.0
    out: list[dict[str, object]] = []
    for segment in segments:
        words = None
        if segment.words is not None:
            words = [
                {
                    "start": word.start,
                    "end": word.end,
                    "word": word.word,
                    "probability": word.probability,
                }
                for word in segment.words
            ]
        out.append(
            {
                "id": segment.id,
                "seek": segment.seek,
                "start": segment.start,
                "end": segment.end,
                "text": segment.text,
                "avg_logprob": segment.avg_logprob,
                "compression_ratio": segment.compression_ratio,
                "no_speech_prob": segment.no_speech_prob,
                "temperature": segment.temperature,
                "words": words,
            }
        )
        if progress is not None and duration > 0:
            progress(min(1.0, float(segment.end) / duration))
    return {
        "language": info.language,
        "language_probability": info.language_probability,
        "duration": info.duration,
        "segments": out,
    }


class FasterWhisperTranscriber:
    """faster-whisper on this machine (default ``small``, CPU, int8). Model loaded once, lazily."""

    def __init__(
        self,
        model: str = "small",
        language: str = "ko",
        vad: bool = True,
        device: str = "cpu",
        compute_type: str = "int8",
        model_dir: str | None = None,
    ) -> None:
        self.model_name = model
        self.language = language
        self.vad = vad
        self.device = device
        self.compute_type = compute_type
        self.model_dir = model_dir
        self._model: Any = None
        self._revision: str | None = None
        self._version = FASTER_WHISPER_VERSION
        self._lock = threading.Lock()

    @classmethod
    def from_settings(cls, settings: Settings) -> "FasterWhisperTranscriber":
        return cls(
            settings.asr_model,
            settings.asr_language,
            settings.asr_vad,
            settings.asr_device,
            settings.asr_compute_type,
            settings.asr_model_dir,
        )

    def _load(self) -> Any:
        if self._model is not None:
            return self._model
        _offline_environment()
        try:
            module: Any = importlib.import_module("faster_whisper")
            utils: Any = importlib.import_module("faster_whisper.utils")
        except ImportError as exc:
            raise AsrError(
                '음성 인식 구성요소가 설치되지 않았습니다. 관리자: pip install -e ".[web,asr]"',
                ("ASR_EXTRA_NOT_INSTALLED",),
            ) from exc
        try:
            path = utils.download_model(
                self.model_name, local_files_only=True, cache_dir=self.model_dir
            )
        except Exception as exc:  # LocalEntryNotFoundError and friends
            raise AsrError(
                f"음성 인식 모델({self.model_name})이 이 PC에 없습니다. 실행 중에는 내려받지 않습니다. "
                "관리자가 모델을 미리 내려받아야 합니다(WEB_002_STATUS.md 참고).",
                ("ASR_MODEL_MISSING", type(exc).__name__),
            ) from exc
        self._model = module.WhisperModel(
            path, device=self.device, compute_type=self.compute_type, local_files_only=True
        )
        self._revision = Path(path).name or None
        self._version = str(getattr(module, "__version__", FASTER_WHISPER_VERSION))
        return self._model

    def transcribe(self, media: Path, progress: Progress) -> AsrOutput:
        with self._lock:
            model = self._load()
            segments, info = model.transcribe(
                decode_audio_16k(media),
                language=self.language or None,
                word_timestamps=True,
                vad_filter=self.vad,
            )
            payload = serialize_result(segments, info, progress)
        vad_digest = None
        if self.vad:
            options: Any = getattr(info, "vad_options", None)
            is_instance = dataclasses.is_dataclass(options) and not isinstance(options, type)
            raw = dataclasses.asdict(options) if is_instance else {}
            vad_digest = config_digest({"vad_filter": True, "vad_options": raw})
        return AsrOutput(
            payload=payload,
            tool_version=self._version,
            model_id=f"{self.model_name} ({self.device}, {self.compute_type})",
            model_revision=self._revision,
            vad_method=VAD_METHOD if self.vad else None,
            vad_config_digest=vad_digest,
            language_requested=self.language or None,
        )
