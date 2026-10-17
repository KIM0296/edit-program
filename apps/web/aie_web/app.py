"""FastAPI routes for the Free web flow (WEB-001 + WEB-002 media upload, local ASR, trial mode).

Run (from the repository root, after ``pip install -e ".[dev,web,asr]"``)::

    python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765

Configuration comes from environment variables (see :class:`aie_web.store.Settings`).
By default only ``127.0.0.1`` / ``localhost`` Host headers are accepted
(``AIE_WEB_ALLOWED_HOSTS`` widens this for a tunnel / reverse proxy). ASR runs
on this machine from a locally cached model; there is no LLM and no network call.
"""

import json
import re
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from fractions import Fraction
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from davinci_ai_editor.apply_cuts import AppliedTimeline
from davinci_ai_editor.roundtrip_verification import ActualProvenance

from . import render
from .asr import FasterWhisperTranscriber, Transcriber
from .jobs import JobRunner, JobState, job_record, job_state, read_job
from .media import Prober, evaluate, frames_for, read_streams, resolve_media_path, safe_filename
from .pipeline import (
    ApprovalView,
    AsrTool,
    MediaFacts,
    PipelineError,
    Profile,
    ProjectBuild,
    TranscriptSource,
    applied_xml,
    apply,
    build_approval,
    build_project,
    candidate_otio,
    candidate_xml,
    clean_text,
    decode_xml,
    parse_frame_or_timecode,
    parse_gap_seconds,
    parse_rate,
    verify,
)
from .security import (
    CSRF_COOKIE,
    TRIAL_COOKIE,
    CsrfRefused,
    check_csrf,
    cookie_token,
    is_https,
    new_token,
)
from .store import (
    APPROVAL,
    CONFIRMED,
    JOB,
    MEDIA,
    TRANSCRIPT,
    MediaTooLarge,
    ProjectNotFound,
    ProjectStore,
    Settings,
)
from .trial import Invite, InviteError, InviteStore

CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)
_VERIFY_PROVENANCE = {
    ActualProvenance.IMMEDIATE_REEXPORT.value: ActualProvenance.IMMEDIATE_REEXPORT,
    ActualProvenance.AFTER_HUMAN_EDIT.value: ActualProvenance.AFTER_HUMAN_EDIT,
}
_TIMECODE_SHAPE = re.compile(r"^(\d{1,9}|\d{2}:\d{2}:\d{2}[:;]\d{2})$")
SWEEP_INTERVAL_SECONDS = 60.0


class UploadTooLarge(PipelineError):
    """The uploaded file exceeds its size limit (HTTP 413)."""


class Busy(PipelineError):
    """Another ASR job is queued or running (HTTP 409)."""


class TrialRequired(Exception):
    """Trial mode is on and this browser has no valid invite session."""


def _html(content: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(content, status_code=status)


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _int_field(value: str, label: str, *, minimum: int = 0) -> int:
    text = value.strip()
    if not text.isdigit() or len(text) > 12 or int(text) < minimum:
        raise PipelineError(f"{label}: {minimum} 이상의 정수를 입력하세요.")
    return int(text)


def _status_for(exc: PipelineError) -> int:
    if isinstance(exc, UploadTooLarge):
        return 413
    if isinstance(exc, CsrfRefused):
        return 403
    if isinstance(exc, Busy):
        return 409
    return 400


async def _read_upload(upload: UploadFile | None, limit: int, label: str) -> bytes:
    if upload is None or not upload.filename:
        raise PipelineError(f"{label} 파일을 선택하세요.")
    data = await upload.read(limit + 1)
    await upload.close()
    if len(data) > limit:
        raise UploadTooLarge(
            f"{label} 파일이 너무 큽니다 (최대 {limit // (1024 * 1024)} MB).", ("UPLOAD_TOO_LARGE",)
        )
    if not data:
        raise PipelineError(f"{label} 파일이 비어 있습니다.")
    return data


def _duration_text(seconds: Fraction) -> str:
    total = float(seconds)
    return f"{int(total // 60)}분 {total % 60:.1f}초"


def create_app(
    settings: Settings | None = None,
    *,
    transcriber: Transcriber | None = None,
    prober: Prober | None = None,
) -> FastAPI:
    config = settings or Settings.from_env()
    store = ProjectStore(config)
    invites = InviteStore(config.invites_path)
    probe_file: Prober = prober or read_streams
    if config.trial_mode:
        for code in config.invite_codes:
            invites.issue(
                config.trial_code_hours, config.trial_max_projects, label="env", code=code
            )
    cached: list[Transcriber] = []

    def get_transcriber() -> Transcriber:
        if transcriber is not None:
            return transcriber
        if not cached:
            cached.append(FasterWhisperTranscriber.from_settings(config))
        return cached[0]

    def on_failure(_: str, meta: dict[str, object]) -> None:
        code = meta.get("trial_code_id")
        if isinstance(code, str):
            invites.release_project(code)

    runner = JobRunner(store, get_transcriber, on_failure)
    last_sweep = [0.0]

    def sweep(now: float | None = None, force: bool = False) -> int:
        moment = time.time() if now is None else now
        if not force and moment - last_sweep[0] < SWEEP_INTERVAL_SECONDS:
            return 0
        last_sweep[0] = moment
        removed = store.cleanup(moment)
        removed += store.delete_for_codes(invites.dead_code_ids(moment))
        return removed

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        sweep(force=True)
        yield

    app = FastAPI(
        title="AIE Free", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.store = store
    app.state.invites = invites
    app.state.runner = runner
    app.state.sweep = sweep

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        token = cookie_token(request)
        fresh = token is None
        request.state.csrf = token or new_token()
        sweep()
        if request.method == "POST":
            limit = (
                config.max_media_request_bytes
                if request.url.path == "/media"
                else config.max_request_bytes
            )
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                response: Response = _html(
                    render.error_page("요청 크기를 알 수 없어 거부했습니다."), 411
                )
            elif int(length) > limit:
                response = _html(
                    render.error_page("요청이 너무 큽니다.", ("REQUEST_TOO_LARGE",)), 413
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        if fresh:
            response.set_cookie(
                CSRF_COOKIE,
                request.state.csrf,
                httponly=True,
                samesite="strict",
                secure=is_https(request, config),
                path="/",
            )
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    # Added last so it runs first: only configured Host headers (DNS-rebinding guard).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.allowed_hosts))

    @app.exception_handler(PipelineError)
    async def pipeline_error(_: Request, exc: PipelineError) -> HTMLResponse:
        return _html(render.error_page(exc.message, exc.codes), _status_for(exc))

    @app.exception_handler(ProjectNotFound)
    async def not_found(_: Request, __: ProjectNotFound) -> HTMLResponse:
        return _html(
            render.error_page("프로젝트를 찾을 수 없습니다 (삭제되었거나 만료됨).", back="/new"),
            404,
        )

    @app.exception_handler(TrialRequired)
    async def trial_required(_: Request, __: TrialRequired) -> Response:
        return _redirect("/")

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> HTMLResponse:
        message = (
            "페이지를 찾을 수 없습니다." if exc.status_code == 404 else "요청을 처리할 수 없습니다."
        )
        return _html(render.error_page(message, back="/"), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, __: RequestValidationError) -> HTMLResponse:
        return _html(render.error_page("입력 형식이 올바르지 않습니다.", back="/"), 400)

    # ----------------------------------------------------------------- session helpers

    def csrf(request: Request) -> str:
        return str(request.state.csrf)

    def trial_session(request: Request) -> tuple[str, Invite] | None:
        if not config.trial_mode:
            return None
        code = request.cookies.get(TRIAL_COOKIE, "")
        invite = invites.lookup(code) if code else None
        return (code, invite) if invite is not None else None

    def require_session(request: Request) -> tuple[str, Invite] | None:
        session = trial_session(request)
        if config.trial_mode and session is None:
            raise TrialRequired()
        return session

    def access(request: Request, project_id: str) -> dict[str, object]:
        """Project meta, if this browser may see it (trial: only its own code's projects)."""
        session = require_session(request)
        meta = store.meta(project_id)
        if session is not None and meta.get("trial_code_id") != session[1].code_id:
            raise ProjectNotFound("not this code's project")
        return meta

    def expires_at(meta: dict[str, object], session: tuple[str, Invite] | None) -> float | None:
        if session is not None:
            return session[1].expires_at
        created = meta.get("created_at")
        if isinstance(created, (int, float)):
            return float(created) + config.max_age_hours * 3600
        return None

    def notice(request: Request, meta: dict[str, object] | None = None) -> str:
        session = trial_session(request)
        hours = config.trial_code_hours if config.trial_mode else config.max_age_hours
        due = expires_at(meta, session) if meta is not None else None
        if session is not None and meta is None:
            due = session[1].expires_at
        text = render.retention_notice(hours, due, trial=config.trial_mode)
        if session is not None:
            text += (
                f"<p class='muted'>이 체험 코드로 프로젝트를 {session[1].remaining_projects()}개 "
                "더 만들 수 있습니다.</p>"
            )
        media = meta.get("media") if meta is not None else None
        if isinstance(media, dict):
            notes = media.get("notes")
            if isinstance(notes, list) and notes:
                items = "".join(f"<li>{render.e(n)}</li>" for n in notes)
                text += f"<div class='card'><b>미디어 메모</b><ul>{items}</ul></div>"
        return text

    def new_page(
        request: Request,
        error: str = "",
        codes: tuple[str, ...] = (),
        values: dict[str, str] | None = None,
    ) -> str:
        return render.new_project(
            error,
            codes,
            values,
            csrf=csrf(request),
            max_minutes=config.max_media_seconds // 60,
            max_mb=config.max_media_bytes // (1024 * 1024),
            asr_label=f"faster-whisper {config.asr_model} ({config.asr_device}), "
            f"언어 {config.asr_language}, VAD {'켬' if config.asr_vad else '끔'}",
            allow_json=not config.trial_mode,
            notice=notice(request),
            busy=runner.active(),
        )

    # ----------------------------------------------------------------- project helpers

    def load_build(project_id: str) -> ProjectBuild:
        meta = store.meta(project_id)
        raw = store.read(project_id, TRANSCRIPT)
        facts, source = meta.get("facts"), meta.get("source")
        if raw is None or not isinstance(facts, dict) or not isinstance(source, dict):
            raise ProjectNotFound("corrupt project")
        return build_project(raw, TranscriptSource.from_json(source), MediaFacts.from_json(facts))

    def load_approval(project_id: str, build: ProjectBuild) -> ApprovalView | None:
        raw = store.read(project_id, APPROVAL)
        if raw is None:
            return None
        return build_approval(build, decode_xml(raw), config.max_xml_bytes)

    def load_applied(project_id: str, build: ProjectBuild) -> AppliedTimeline | None:
        raw = store.read(project_id, CONFIRMED)
        view = load_approval(project_id, build)
        if raw is None or view is None:
            return None
        digest = json.loads(raw.decode("utf-8")).get("digest")
        return apply(view, str(digest))

    def pending_redirect(project_id: str) -> Response | None:
        """Media projects before their transcript is ready go to facts / status."""
        state = job_state(read_job(store, project_id))
        if state is None or state is JobState.DONE:
            return None
        if state is JobState.NEEDS_FACTS:
            return _redirect(f"/p/{project_id}/facts")
        return _redirect(f"/p/{project_id}/status")

    def finalize(project_id: str, meta: dict[str, object], values: dict[str, str]) -> None:
        """Complete the media facts (never guessed) and queue the ASR job."""
        media, pending = meta.get("media"), meta.get("pending")
        if not isinstance(media, dict) or not isinstance(pending, dict):
            raise ProjectNotFound("corrupt project")
        rate_text = media.get("rate") or values.get("rate", "")
        rate = parse_rate(str(rate_text))
        frames = media.get("duration_frames")
        duration = (
            frames
            if isinstance(frames, int)
            else frames_for(Fraction(str(media["duration_seconds"])), rate)
        )
        start = media.get("start_frame")
        if not isinstance(start, int):
            start = parse_frame_or_timecode(values.get("media_start", ""), rate, "미디어 시작")
        try:
            profile = Profile(values.get("profile", "RESOLVE"))
        except ValueError as exc:
            raise PipelineError("프로필은 목록에서 선택하세요.") from exc
        tl_text = values.get("timeline_start", str(pending.get("timeline_start", "")))
        tl_start = parse_frame_or_timecode(tl_text, rate, "타임라인 시작")
        facts = MediaFacts(
            media_path=resolve_media_path(
                str(media.get("folder", "")), str(media["original_filename"])
            ),
            rate=rate,
            duration_frames=duration,
            media_start_frame=start,
            profile=profile,
            timeline_name=clean_text(str(pending.get("timeline_name", "")), 80),
            timeline_start_frame=0 if tl_start is None else tl_start,
        )
        offset = media.get("offset_ms")
        source = TranscriptSource(
            AsrTool.FASTER_WHISPER,
            "PENDING",
            config.asr_model,
            offset if isinstance(offset, int) else 0,
            str(pending.get("gap_seconds", "1.0")),
        )
        store.update_meta(project_id, facts=facts.to_json(), source=source.to_json())
        runner.submit(project_id)

    # ----------------------------------------------------------------- public pages

    @app.get("/", response_class=HTMLResponse)
    async def landing(request: Request) -> HTMLResponse:
        if config.trial_mode and trial_session(request) is None:
            return _html(
                render.consent_page(
                    csrf(request),
                    config.trial_code_hours,
                    config.trial_max_projects,
                    config.max_media_seconds // 60,
                )
            )
        return _html(render.landing())

    @app.post("/trial/start", response_model=None)
    async def trial_start(
        request: Request,
        csrf_token: Annotated[str, Form()] = "",
        code: Annotated[str, Form()] = "",
        consent: Annotated[str, Form()] = "",
    ) -> Response:
        if not config.trial_mode:
            raise StarletteHTTPException(404)
        check_csrf(request, csrf_token)

        def again(message: str, status: int) -> HTMLResponse:
            page = render.consent_page(
                csrf(request),
                config.trial_code_hours,
                config.trial_max_projects,
                config.max_media_seconds // 60,
                error=message,
            )
            return _html(page, status)

        if consent != "yes":
            return again("동의 체크박스를 선택해야 시작할 수 있습니다.", 400)
        try:
            invite = invites.start(code)
        except InviteError as exc:
            return again(exc.message, 403)
        response = _redirect("/new")
        remaining = (invite.expires_at or time.time()) - time.time()
        response.set_cookie(
            TRIAL_COOKIE,
            code.strip()[:64],
            max_age=max(60, int(remaining)),
            httponly=True,
            samesite="strict",
            secure=is_https(request, config),
            path="/",
        )
        return response

    @app.get("/limits", response_class=HTMLResponse)
    async def limits() -> HTMLResponse:
        return _html(render.limits())

    @app.get("/studio", response_class=HTMLResponse)
    async def studio() -> HTMLResponse:
        return _html(render.studio_page())

    @app.get("/guide", response_class=HTMLResponse)
    async def guide() -> HTMLResponse:
        return _html(render.guide_page())

    @app.get("/new", response_class=HTMLResponse)
    async def new_form(request: Request) -> HTMLResponse:
        require_session(request)
        return _html(new_page(request))

    # ----------------------------------------------------------------- WEB-002 media

    @app.post("/media", response_model=None)
    async def upload_media(
        request: Request,
        media: Annotated[UploadFile | None, File()] = None,
        csrf_token: Annotated[str, Form()] = "",
        media_folder: Annotated[str, Form()] = "",
        timeline_name: Annotated[str, Form()] = "",
        timeline_start: Annotated[str, Form()] = "01:00:00:00",
        gap_seconds: Annotated[str, Form()] = "1.0",
    ) -> Response:
        check_csrf(request, csrf_token)
        session = require_session(request)
        values = {
            "media_folder": media_folder,
            "timeline_name": timeline_name,
            "timeline_start": timeline_start,
            "gap_seconds": gap_seconds,
        }
        try:
            if media is None or not media.filename:
                raise PipelineError("영상 또는 오디오 파일을 선택하세요.")
            filename = safe_filename(media.filename)
            resolve_media_path(media_folder, filename)  # validate the folder early
            if not clean_text(timeline_name, 80):
                raise PipelineError("타임라인 이름을 입력하세요.")
            if not _TIMECODE_SHAPE.match(timeline_start.strip()):
                raise PipelineError("타임라인 시작: 프레임 수 또는 HH:MM:SS:FF 를 입력하세요.")
            parse_gap_seconds(gap_seconds)
            if runner.active():
                raise Busy(
                    "지금 다른 전사 작업이 진행 중입니다. 한 번에 하나만 처리하므로 잠시 후 다시 올려 주세요.",
                    ("ASR_BUSY",),
                )
            if session is not None and session[1].remaining_projects() <= 0:
                raise PipelineError(
                    f"이 체험 코드로 만들 수 있는 프로젝트 {session[1].max_projects}개를 모두 사용했습니다.",
                    ("TRIAL_PROJECT_LIMIT",),
                )
        except PipelineError as exc:
            if media is not None:
                await media.close()
            return _html(new_page(request, exc.message, exc.codes, values), _status_for(exc))
        project_id = store.create(
            {
                "kind": "media",
                "trial_code_id": session[1].code_id if session is not None else None,
                "pending": {
                    "timeline_name": clean_text(timeline_name, 80),
                    "timeline_start": timeline_start.strip(),
                    "gap_seconds": gap_seconds.strip() or "1.0",
                },
            }
        )
        try:
            size = await run_in_threadpool(
                store.save_stream, project_id, MEDIA, media.file, config.max_media_bytes
            )
            facts = await run_in_threadpool(probe_file, store.path(project_id, MEDIA))
            probe = evaluate(facts, config.max_media_seconds)
            if session is not None:
                invites.consume_project(session[0])
        except MediaTooLarge:
            store.delete(project_id)
            limit_mb = config.max_media_bytes // (1024 * 1024)
            too_large = UploadTooLarge(
                f"파일이 너무 큽니다 (최대 {limit_mb} MB).", ("MEDIA_TOO_LARGE",)
            )
            return _html(new_page(request, too_large.message, too_large.codes, values), 413)
        except InviteError as exc:
            store.delete(project_id)
            return _html(new_page(request, exc.message, (exc.code,), values), 403)
        except PipelineError as exc:
            store.delete(project_id)
            return _html(new_page(request, exc.message, exc.codes, values), _status_for(exc))
        except BaseException:
            store.delete(project_id)
            raise
        finally:
            await media.close()
        media_meta = {
            "original_filename": filename,
            "folder": clean_text(media_folder, 900),
            "size_bytes": size,
            "duration_text": _duration_text(probe.duration_seconds),
            **probe.to_json(),
        }
        meta = store.update_meta(project_id, media=media_meta)
        if probe.rate is not None and probe.start_frame is not None:
            try:
                finalize(project_id, meta, {"profile": "RESOLVE"})
            except PipelineError as exc:
                store.write_json(project_id, JOB, job_record(JobState.NEEDS_FACTS))
                return _html(
                    render.facts_page(
                        project_id, media_meta, csrf(request), exc.message, exc.codes
                    ),
                    400,
                )
            return _redirect(f"/p/{project_id}/status")
        store.write_json(project_id, JOB, job_record(JobState.NEEDS_FACTS))
        return _redirect(f"/p/{project_id}/facts")

    @app.get("/p/{project_id}/facts", response_model=None)
    async def facts_form(request: Request, project_id: str) -> Response:
        meta = access(request, project_id)
        if job_state(read_job(store, project_id)) is not JobState.NEEDS_FACTS:
            return _redirect(f"/p/{project_id}/status")
        media = meta.get("media")
        pending = meta.get("pending")
        values = {}
        if isinstance(pending, dict):
            values["timeline_start"] = str(pending.get("timeline_start", ""))
        return _html(
            render.facts_page(
                project_id, media if isinstance(media, dict) else {}, csrf(request), values=values
            )
        )

    @app.post("/p/{project_id}/facts", response_model=None)
    async def facts_submit(
        request: Request,
        project_id: str,
        csrf_token: Annotated[str, Form()] = "",
        rate: Annotated[str, Form()] = "",
        media_start: Annotated[str, Form()] = "",
        profile: Annotated[str, Form()] = "RESOLVE",
        timeline_start: Annotated[str, Form()] = "01:00:00:00",
    ) -> Response:
        check_csrf(request, csrf_token)
        meta = access(request, project_id)
        if job_state(read_job(store, project_id)) is not JobState.NEEDS_FACTS:
            return _redirect(f"/p/{project_id}/status")
        values = {
            "rate": rate,
            "media_start": media_start,
            "profile": profile,
            "timeline_start": timeline_start,
        }
        try:
            finalize(project_id, meta, values)
        except PipelineError as exc:
            media = meta.get("media")
            page = render.facts_page(
                project_id,
                media if isinstance(media, dict) else {},
                csrf(request),
                exc.message,
                exc.codes,
                values,
            )
            return _html(page, 400)
        return _redirect(f"/p/{project_id}/status")

    @app.get("/p/{project_id}/status", response_model=None)
    async def status(request: Request, project_id: str) -> Response:
        meta = access(request, project_id)
        job = read_job(store, project_id)
        if job is None:
            return _redirect(f"/p/{project_id}")
        if job_state(job) is JobState.NEEDS_FACTS:
            return _redirect(f"/p/{project_id}/facts")
        media = meta.get("media")
        filename = str(media.get("original_filename", "")) if isinstance(media, dict) else ""
        return _html(
            render.status_page(project_id, job, csrf(request), filename, notice(request, meta))
        )

    # ----------------------------------------------------------------- WEB-001 flow

    @app.post("/projects", response_model=None)
    async def create_project(
        request: Request,
        transcript: Annotated[UploadFile | None, File()] = None,
        csrf_token: Annotated[str, Form()] = "",
        tool: Annotated[str, Form()] = "",
        tool_version: Annotated[str, Form()] = "",
        model_id: Annotated[str, Form()] = "",
        offset_ms: Annotated[str, Form()] = "0",
        media_path: Annotated[str, Form()] = "",
        rate: Annotated[str, Form()] = "",
        duration_frames: Annotated[str, Form()] = "",
        media_start: Annotated[str, Form()] = "",
        profile: Annotated[str, Form()] = "RESOLVE",
        timeline_name: Annotated[str, Form()] = "",
        timeline_start: Annotated[str, Form()] = "01:00:00:00",
        gap_seconds: Annotated[str, Form()] = "1.0",
    ) -> Response:
        if config.trial_mode:
            raise StarletteHTTPException(404)  # trial testers upload media only
        check_csrf(request, csrf_token)
        values = {
            "tool": tool,
            "tool_version": tool_version,
            "model_id": model_id,
            "offset_ms": offset_ms,
            "media_path": media_path,
            "rate": rate,
            "duration_frames": duration_frames,
            "media_start": media_start,
            "profile": profile,
            "timeline_name": timeline_name,
            "timeline_start": timeline_start,
            "gap_seconds": gap_seconds,
        }
        try:
            raw = await _read_upload(transcript, config.max_transcript_bytes, "전사 JSON")
            try:
                asr = AsrTool(tool)
                chosen_profile = Profile(profile)
            except ValueError as exc:
                raise PipelineError("ASR 도구와 프로필은 목록에서 선택하세요.") from exc
            frame_rate = parse_rate(rate)
            tl_start = parse_frame_or_timecode(timeline_start, frame_rate, "타임라인 시작")
            parse_gap_seconds(gap_seconds)
            facts = MediaFacts(
                media_path=clean_text(media_path, 1024),
                rate=frame_rate,
                duration_frames=_int_field(duration_frames, "미디어 길이(프레임)", minimum=1),
                media_start_frame=parse_frame_or_timecode(media_start, frame_rate, "미디어 시작"),
                profile=chosen_profile,
                timeline_name=clean_text(timeline_name, 80),
                timeline_start_frame=0 if tl_start is None else tl_start,
            )
            source = TranscriptSource(
                asr,
                clean_text(tool_version, 80),
                clean_text(model_id, 80),
                _int_field(offset_ms or "0", "전사 시작 오프셋(ms)"),
                gap_seconds.strip() or "1.0",
            )
            build_project(raw, source, facts)  # validate everything before storing
        except PipelineError as exc:
            return _html(new_page(request, exc.message, exc.codes, values), _status_for(exc))
        project_id = store.create(
            {"kind": "transcript", "facts": facts.to_json(), "source": source.to_json()}, raw
        )
        return _redirect(f"/p/{project_id}")

    @app.get("/p/{project_id}", response_model=None)
    async def project(request: Request, project_id: str) -> Response:
        meta = access(request, project_id)
        redirect = pending_redirect(project_id)
        if redirect is not None:
            return redirect
        build = load_build(project_id)
        return _html(
            render.project_page(
                project_id,
                build,
                store.read(project_id, APPROVAL) is not None,
                store.read(project_id, CONFIRMED) is not None,
                csrf(request),
                notice(request, meta),
            )
        )

    @app.get("/p/{project_id}/download/{name}", response_model=None)
    async def download(request: Request, project_id: str, name: str) -> Response:
        access(request, project_id)
        build = load_build(project_id)
        if name == "candidates.xml":
            content, media = candidate_xml(build), "application/xml"
            filename = "aie_candidates.xml"
        elif name == "candidates.otio":
            content, media = candidate_otio(build), "application/json"
            filename = "aie_candidates.otio"
        elif name == "transcript.srt":
            content, media = build.srt_text, "text/plain"
            filename = "aie_transcript.srt"
        elif name == "applied.xml":
            applied = load_applied(project_id, build)
            if applied is None:
                raise PipelineError("아직 확인(승인)된 적용 결과가 없습니다.")
            content, media = applied_xml(applied), "application/xml"
            filename = "aie_applied.xml"
        else:
            raise StarletteHTTPException(404)
        return Response(
            content.encode("utf-8"),
            media_type=f"{media}; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    @app.post("/p/{project_id}/approval", response_model=None)
    async def upload_approval(
        request: Request,
        project_id: str,
        export: Annotated[UploadFile | None, File()] = None,
        csrf_token: Annotated[str, Form()] = "",
    ) -> Response:
        check_csrf(request, csrf_token)
        access(request, project_id)
        build = load_build(project_id)
        raw = await _read_upload(export, config.max_xml_bytes, "승인 XML")
        build_approval(build, decode_xml(raw), config.max_xml_bytes)  # refuse before storing
        store.write(project_id, APPROVAL, raw)
        store.remove(project_id, CONFIRMED)  # a new selection makes any old approval stale
        return _redirect(f"/p/{project_id}/confirm")

    @app.get("/p/{project_id}/confirm", response_model=None)
    async def confirm_page(request: Request, project_id: str) -> Response:
        access(request, project_id)
        build = load_build(project_id)
        view = load_approval(project_id, build)
        if view is None:
            return _redirect(f"/p/{project_id}")
        return _html(render.confirm_page(project_id, build, view, csrf(request)))

    @app.post("/p/{project_id}/confirm", response_model=None)
    async def confirm(
        request: Request,
        project_id: str,
        digest: Annotated[str, Form()] = "",
        csrf_token: Annotated[str, Form()] = "",
    ) -> Response:
        check_csrf(request, csrf_token)
        access(request, project_id)
        build = load_build(project_id)
        view = load_approval(project_id, build)
        if view is None:
            raise PipelineError("먼저 Resolve에서 내보낸 승인 XML을 업로드하세요.")
        apply(view, digest.strip())  # ApplyRefused -> PipelineError (nothing applied)
        store.write(project_id, CONFIRMED, json.dumps({"digest": digest.strip()}).encode("utf-8"))
        return _redirect(f"/p/{project_id}/applied")

    @app.get("/p/{project_id}/applied", response_model=None)
    async def applied_page(request: Request, project_id: str) -> Response:
        access(request, project_id)
        build = load_build(project_id)
        applied = load_applied(project_id, build)
        if applied is None:
            return _redirect(f"/p/{project_id}/confirm")
        return _html(render.applied_page(project_id, applied, csrf(request)))

    @app.post("/p/{project_id}/verify", response_model=None)
    async def verify_upload(
        request: Request,
        project_id: str,
        export: Annotated[UploadFile | None, File()] = None,
        provenance: Annotated[str, Form()] = "",
        csrf_token: Annotated[str, Form()] = "",
    ) -> Response:
        check_csrf(request, csrf_token)
        access(request, project_id)
        build = load_build(project_id)
        applied = load_applied(project_id, build)
        if applied is None:
            raise PipelineError("먼저 확인 버튼으로 컷을 적용하세요.")
        chosen = _VERIFY_PROVENANCE.get(provenance)
        if chosen is None:
            raise PipelineError("내보낸 파일의 출처를 목록에서 선택하세요.")
        raw = await _read_upload(export, config.max_xml_bytes, "다시 내보낸 XML")
        report = verify(applied, decode_xml(raw), chosen, config.max_xml_bytes)
        return _html(render.report_page(project_id, report))

    @app.post("/p/{project_id}/delete", response_class=HTMLResponse)
    async def delete(
        request: Request, project_id: str, csrf_token: Annotated[str, Form()] = ""
    ) -> HTMLResponse:
        check_csrf(request, csrf_token)
        access(request, project_id)
        if not store.delete(project_id):
            raise ProjectNotFound("no such project")
        return _html(render.deleted_page())

    return app


app = create_app()
