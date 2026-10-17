"""FastAPI routes for the WEB-001 Free flow (local development server only).

Run (from the repository root, after ``pip install -e ".[dev,web]"``)::

    python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765

Only ``127.0.0.1`` / ``localhost`` Host headers are accepted. No auth, no
database, no media upload, no ASR, no LLM and no network calls.
"""

import json
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse, Response
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from davinci_ai_editor.apply_cuts import AppliedTimeline
from davinci_ai_editor.roundtrip_verification import ActualProvenance

from . import render
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
from .store import APPROVAL, CONFIRMED, TRANSCRIPT, ProjectNotFound, ProjectStore, Settings

CSP = (
    "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
    "frame-ancestors 'none'; base-uri 'none'"
)
_VERIFY_PROVENANCE = {
    ActualProvenance.IMMEDIATE_REEXPORT.value: ActualProvenance.IMMEDIATE_REEXPORT,
    ActualProvenance.AFTER_HUMAN_EDIT.value: ActualProvenance.AFTER_HUMAN_EDIT,
}


class UploadTooLarge(PipelineError):
    """The uploaded file exceeds its size limit (HTTP 413)."""


def _html(content: str, status: int = 200) -> HTMLResponse:
    return HTMLResponse(content, status_code=status)


def _redirect(url: str) -> RedirectResponse:
    return RedirectResponse(url, status_code=303)


def _int_field(value: str, label: str, *, minimum: int = 0) -> int:
    text = value.strip()
    if not text.isdigit() or len(text) > 12 or int(text) < minimum:
        raise PipelineError(f"{label}: {minimum} 이상의 정수를 입력하세요.")
    return int(text)


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


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings.from_env()
    store = ProjectStore(config)

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        store.cleanup()
        yield

    app = FastAPI(
        title="AIE Free (local)", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan
    )
    app.state.store = store

    @app.middleware("http")
    async def guard(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        if request.method == "POST":
            length = request.headers.get("content-length")
            if length is None or not length.isdigit():
                response: Response = _html(
                    render.error_page("요청 크기를 알 수 없어 거부했습니다."), 411
                )
            elif int(length) > config.max_request_bytes:
                response = _html(
                    render.error_page("요청이 너무 큽니다.", ("REQUEST_TOO_LARGE",)), 413
                )
            else:
                response = await call_next(request)
        else:
            response = await call_next(request)
        response.headers["Content-Security-Policy"] = CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        return response

    # Added last so it runs first: only loopback Host headers (DNS-rebinding guard).
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=list(config.allowed_hosts))

    @app.exception_handler(PipelineError)
    async def pipeline_error(_: Request, exc: PipelineError) -> HTMLResponse:
        status = 413 if isinstance(exc, UploadTooLarge) else 400
        return _html(render.error_page(exc.message, exc.codes), status)

    @app.exception_handler(ProjectNotFound)
    async def not_found(_: Request, __: ProjectNotFound) -> HTMLResponse:
        return _html(
            render.error_page("프로젝트를 찾을 수 없습니다 (삭제되었거나 만료됨).", back="/new"),
            404,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(_: Request, exc: StarletteHTTPException) -> HTMLResponse:
        message = (
            "페이지를 찾을 수 없습니다." if exc.status_code == 404 else "요청을 처리할 수 없습니다."
        )
        return _html(render.error_page(message, back="/"), exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_: Request, __: RequestValidationError) -> HTMLResponse:
        return _html(render.error_page("입력 형식이 올바르지 않습니다.", back="/"), 400)

    # ----------------------------------------------------------------- helpers

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

    # ----------------------------------------------------------------- pages

    @app.get("/", response_class=HTMLResponse)
    async def landing() -> HTMLResponse:
        return _html(render.landing())

    @app.get("/limits", response_class=HTMLResponse)
    async def limits() -> HTMLResponse:
        return _html(render.limits())

    @app.get("/new", response_class=HTMLResponse)
    async def new_form() -> HTMLResponse:
        return _html(render.new_project())

    @app.post("/projects", response_model=None)
    async def create_project(
        transcript: Annotated[UploadFile | None, File()] = None,
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
        except UploadTooLarge as exc:
            return _html(render.new_project(exc.message, exc.codes, values), 413)
        except PipelineError as exc:
            return _html(render.new_project(exc.message, exc.codes, values), 400)
        project_id = store.create({"facts": facts.to_json(), "source": source.to_json()}, raw)
        store.cleanup()
        return _redirect(f"/p/{project_id}")

    @app.get("/p/{project_id}", response_class=HTMLResponse)
    async def project(project_id: str) -> HTMLResponse:
        build = load_build(project_id)
        return _html(
            render.project_page(
                project_id,
                build,
                store.read(project_id, APPROVAL) is not None,
                store.read(project_id, CONFIRMED) is not None,
            )
        )

    @app.get("/p/{project_id}/download/{name}", response_model=None)
    async def download(project_id: str, name: str) -> Response:
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
        project_id: str, export: Annotated[UploadFile | None, File()] = None
    ) -> Response:
        build = load_build(project_id)
        raw = await _read_upload(export, config.max_xml_bytes, "승인 XML")
        build_approval(build, decode_xml(raw), config.max_xml_bytes)  # refuse before storing
        store.write(project_id, APPROVAL, raw)
        store.remove(project_id, CONFIRMED)  # a new selection makes any old approval stale
        return _redirect(f"/p/{project_id}/confirm")

    @app.get("/p/{project_id}/confirm", response_model=None)
    async def confirm_page(project_id: str) -> Response:
        build = load_build(project_id)
        view = load_approval(project_id, build)
        if view is None:
            return _redirect(f"/p/{project_id}")
        return _html(render.confirm_page(project_id, build, view))

    @app.post("/p/{project_id}/confirm", response_model=None)
    async def confirm(project_id: str, digest: Annotated[str, Form()] = "") -> Response:
        build = load_build(project_id)
        view = load_approval(project_id, build)
        if view is None:
            raise PipelineError("먼저 Resolve에서 내보낸 승인 XML을 업로드하세요.")
        apply(view, digest.strip())  # ApplyRefused -> PipelineError (nothing applied)
        store.write(project_id, CONFIRMED, json.dumps({"digest": digest.strip()}).encode("utf-8"))
        return _redirect(f"/p/{project_id}/applied")

    @app.get("/p/{project_id}/applied", response_model=None)
    async def applied_page(project_id: str) -> Response:
        build = load_build(project_id)
        applied = load_applied(project_id, build)
        if applied is None:
            return _redirect(f"/p/{project_id}/confirm")
        return _html(render.applied_page(project_id, applied))

    @app.post("/p/{project_id}/verify", response_model=None)
    async def verify_upload(
        project_id: str,
        export: Annotated[UploadFile | None, File()] = None,
        provenance: Annotated[str, Form()] = "",
    ) -> Response:
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
    async def delete(project_id: str) -> HTMLResponse:
        if not store.delete(project_id):
            raise ProjectNotFound("no such project")
        return _html(render.deleted_page())

    return app


app = create_app()
