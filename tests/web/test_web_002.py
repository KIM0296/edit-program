"""WEB-002: media upload + local ASR (mocked) + trial mode, through the FastAPI TestClient.

The transcriber and the PyAV prober are injected fakes: no model, no media
decoding, no network. Resolve is simulated by text edits of our own XML.
"""

import json
import os
import threading
import time
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

import httpx
import web_fixtures as wf
from aie_web import admin
from aie_web.app import create_app
from aie_web.asr import VAD_METHOD, AsrError, AsrOutput, Progress, serialize_result
from aie_web.media import StreamFacts, evaluate
from aie_web.pipeline import PipelineError
from aie_web.store import JOB, MEDIA, TRANSCRIPT, ProjectStore, Settings
from aie_web.trial import InviteStore
from fastapi import FastAPI
from fastapi.testclient import TestClient

from davinci_ai_editor.transcript_evidence import (
    AudioClock,
    TranscriptProducerRef,
    ingest_faster_whisper,
)

MEDIA_BYTES = b"\x00\x01fake-media" * 64


def cfr_facts(**overrides: object) -> StreamFacts:
    values: dict[str, object] = {
        "container_duration": Fraction(8),
        "has_video": True,
        "video_avg_rate": Fraction(25),
        "video_base_rate": Fraction(25),
        "video_time_base": Fraction(1, 12800),
        "video_frames": 200,
        "video_duration": Fraction(8),
        "video_start": Fraction(0),
        "pts_deltas": (512,) * 40,
        "has_audio": True,
        "audio_start": Fraction(0),
        "audio_duration": Fraction(8),
        "timecode_tag": "01:00:00:00",
    }
    values.update(overrides)
    return StreamFacts(**values)  # type: ignore[arg-type]


class FakeTranscriber:
    def __init__(
        self,
        payload: dict[str, object] | None = None,
        error: Exception | None = None,
        gate: threading.Event | None = None,
    ) -> None:
        self.payload = payload
        self.error = error
        self.gate = gate
        self.calls: list[Path] = []

    def transcribe(self, media: Path, progress: Progress) -> AsrOutput:
        self.calls.append(media)
        assert media.name == MEDIA and media.read_bytes() == MEDIA_BYTES
        if self.gate is not None:
            assert self.gate.wait(10)
        progress(0.5)
        if self.error is not None:
            raise self.error
        return AsrOutput(
            payload=self.payload if self.payload is not None else wf.transcript_payload(),
            tool_version="1.1.1",
            model_id="small (cpu, int8)",
            model_revision="rev-536b0662742c02347bc0e980a01041f333bce120",
            vad_method=VAD_METHOD,
            vad_config_digest="sha256:" + "a" * 64,
            language_requested="ko",
        )


def _settings(tmp_path: Path, **overrides: object) -> Settings:
    values: dict[str, object] = {
        "root": tmp_path / "projects",
        "allowed_hosts": ("testserver",),
    }
    values.update(overrides)
    return Settings(**values)  # type: ignore[arg-type]


def _app(
    tmp_path: Path,
    transcriber: FakeTranscriber | None = None,
    facts: StreamFacts | None = None,
    **overrides: object,
) -> tuple[FastAPI, TestClient]:
    probe = facts or cfr_facts()
    app = create_app(
        _settings(tmp_path, **overrides),
        transcriber=transcriber or FakeTranscriber(),
        prober=lambda _: probe,
    )
    return app, TestClient(app)


def _token(client: TestClient, page: str = "/new") -> str:
    return wf.csrf_token(client.get(page).text)


def _upload_media(
    client: TestClient,
    *,
    name: str = "interview.mov",
    data: bytes = MEDIA_BYTES,
    token: str | None = None,
    **fields: str,
) -> httpx.Response:
    form = {
        "csrf_token": _token(client) if token is None else token,
        "media_folder": "D:\\Footage",
        "timeline_name": "인터뷰",
        "timeline_start": "01:00:00:00",
        "gap_seconds": "1.0",
    }
    form.update(fields)
    return client.post(
        "/media",
        data=form,
        files={"media": (name, data, "video/quicktime")},
        follow_redirects=False,
    )


def _project_id(response: httpx.Response) -> str:
    assert response.status_code == 303, response.text
    return response.headers["location"].split("/")[2]


def _wait(app: FastAPI) -> None:
    assert app.state.runner.join(10)


def _post(client: TestClient, url: str, data: dict[str, str] | None = None) -> httpx.Response:
    return client.post(
        url, data={**(data or {}), "csrf_token": _token(client)}, follow_redirects=False
    )


def _upload_xml(client: TestClient, url: str, text: str, **fields: str) -> httpx.Response:
    return client.post(
        url,
        data={**fields, "csrf_token": _token(client)},
        files={"export": ("export.xml", text.encode("utf-8"), "application/xml")},
        follow_redirects=False,
    )


# --------------------------------------------------------------------------- full flow


def test_media_upload_transcribe_and_full_flow(tmp_path: Path) -> None:
    fake = FakeTranscriber()
    app, client = _app(tmp_path, fake)
    new = client.get("/new").text
    assert "저장과 삭제 안내" in new and "Studio에서는" in new and "CFR" in new
    response = _upload_media(client)
    pid = _project_id(response)
    assert response.headers["location"] == f"/p/{pid}/status"
    _wait(app)
    status = client.get(f"/p/{pid}/status").text
    assert "DONE" in status and "후보 목록 보기" in status
    store: ProjectStore = app.state.store
    meta = store.meta(pid)
    source = meta["source"]
    assert isinstance(source, dict)
    assert source["tool"] == "faster-whisper" and source["tool_version"] == "1.1.1"
    assert source["model_id"] == "small (cpu, int8)"
    assert str(source["model_revision"]).startswith("rev-")
    assert source["vad_method"] == VAD_METHOD and source["language_requested"] == "ko"
    stored = json.loads((store.path(pid, TRANSCRIPT)).read_text("utf-8"))
    assert stored == wf.transcript_payload()  # exact faster-whisper shape stored

    page = client.get(f"/p/{pid}").text
    for token in ("AIE-0001", "AIE-0002", "AIE-0003", "Studio에서는", "삭제 예정"):
        assert token in page
    xml = client.get(f"/p/{pid}/download/candidates.xml").text
    assert "file:///D:/Footage/interview.mov" in xml
    assert "<name>AIE-0001 ?</name>" in xml and "<name>AIE-0003 ?</name>" in xml

    assert _upload_xml(client, f"/p/{pid}/approval", wf.editor_export(xml)).status_code == 303
    confirm = client.get(f"/p/{pid}/confirm").text
    assert "승인된 컷 2개" in confirm and "44프레임" in confirm
    ok = _post(client, f"/p/{pid}/confirm", {"digest": wf.hidden_digest(confirm)})
    assert ok.status_code == 303
    applied = client.get(f"/p/{pid}/download/applied.xml").text
    report = _upload_xml(
        client, f"/p/{pid}/verify", wf.reexport(applied), provenance="IMMEDIATE_REEXPORT"
    )
    assert "MATCH (일치)" in report.text
    assert len(fake.calls) == 1


def test_folder_omitted_uses_relink_placeholder(tmp_path: Path) -> None:
    app, client = _app(tmp_path)
    pid = _project_id(_upload_media(client, media_folder=""))
    _wait(app)
    xml = client.get(f"/p/{pid}/download/candidates.xml").text
    assert "file:///AIE-RELINK/interview.mov" in xml
    refused = _upload_media(client, media_folder="Footage\\relative")
    assert refused.status_code == 400 and "RELATIVE_FOLDER" in refused.text


# --------------------------------------------------------------------------- refusals


def test_vfr_is_refused_with_cfr_message(tmp_path: Path) -> None:
    for facts in (
        cfr_facts(video_avg_rate=Fraction(2997, 100), video_base_rate=Fraction(30)),
        cfr_facts(pts_deltas=(512, 512, 513, 700, 512)),
    ):
        app, client = _app(tmp_path, facts=facts)
        response = _upload_media(client)
        assert response.status_code == 400
        assert "CFR로 변환 후 다시 올려 주세요" in response.text and "VFR_DETECTED" in response.text
        assert list(app.state.store.project_ids()) == []


def test_non_whitelisted_rate_and_no_audio_refused(tmp_path: Path) -> None:
    with pytest.raises(PipelineError) as rate:
        evaluate(
            cfr_facts(video_avg_rate=Fraction(15), video_base_rate=Fraction(15), pts_deltas=()), 600
        )
    assert "RATE_NOT_WHITELISTED" in rate.value.codes
    with pytest.raises(PipelineError) as audio:
        evaluate(cfr_facts(has_audio=False), 600)
    assert audio.value.codes == ("NO_AUDIO",)
    with pytest.raises(PipelineError) as early:
        evaluate(cfr_facts(audio_start=Fraction(0), video_start=Fraction(1)), 600)
    assert early.value.codes == ("AUDIO_BEFORE_VIDEO",)
    late = evaluate(cfr_facts(audio_start=Fraction(1, 2)), 600)
    assert late.offset_ms == 500 and late.notes
    ntsc = evaluate(
        cfr_facts(
            video_avg_rate=Fraction(30000, 1001),
            video_base_rate=Fraction(30000, 1001),
            video_time_base=Fraction(1, 30000),
            pts_deltas=(1001,) * 10,
            timecode_tag="00:59:59;28",
        ),
        600,
    )
    assert ntsc.rate is not None and ntsc.start_frame is not None


def test_missing_start_timecode_prompts_the_user(tmp_path: Path) -> None:
    app, client = _app(tmp_path, facts=cfr_facts(timecode_tag=None))
    response = _upload_media(client)
    pid = _project_id(response)
    assert response.headers["location"] == f"/p/{pid}/facts"
    assert client.get(f"/p/{pid}", follow_redirects=False).headers["location"].endswith("/facts")
    page = client.get(f"/p/{pid}/facts").text
    assert "0으로 가정하지 않습니다" in page and "Start TC" in page
    refused = _post(client, f"/p/{pid}/facts", {"media_start": "", "profile": "RESOLVE"})
    assert refused.status_code == 400 and "MEDIA_START_UNKNOWN" in refused.text
    assert not app.state.runner.active()  # nothing queued
    accepted = _post(
        client,
        f"/p/{pid}/facts",
        {"media_start": "00:00:10:00", "profile": "RESOLVE", "timeline_start": "01:00:00:00"},
    )
    assert accepted.headers["location"] == f"/p/{pid}/status"
    _wait(app)
    facts = app.state.store.meta(pid)["facts"]
    assert facts["media_start_frame"] == 250


def test_audio_only_asks_for_rate(tmp_path: Path) -> None:
    audio = StreamFacts(
        container_duration=Fraction(8),
        has_video=False,
        has_audio=True,
        audio_start=Fraction(0),
        audio_duration=Fraction(8),
    )
    app, client = _app(tmp_path, facts=audio)
    pid = _project_id(_upload_media(client, name="talk.wav"))
    assert "타임라인 프레임레이트" in client.get(f"/p/{pid}/facts").text
    _post(client, f"/p/{pid}/facts", {"rate": "25/1", "media_start": "0", "profile": "RESOLVE"})
    _wait(app)
    assert app.state.store.meta(pid)["facts"]["duration_frames"] == 200


def test_oversize_and_too_long_media_refused(tmp_path: Path) -> None:
    app, client = _app(tmp_path, max_media_bytes=100)
    response = _upload_media(client)
    assert response.status_code == 413 and "너무 큽니다" in response.text
    assert list(app.state.store.project_ids()) == []
    app, client = _app(tmp_path, facts=cfr_facts(video_duration=Fraction(700), video_frames=17500))
    response = _upload_media(client)
    assert response.status_code == 400 and "MEDIA_TOO_LONG" in response.text
    assert list(app.state.store.project_ids()) == []
    unsupported = _upload_media(client, name="evil.exe")
    assert unsupported.status_code == 400 and "UNSUPPORTED_EXTENSION" in unsupported.text
    huge = client.post(
        "/media",
        content=b"x",
        headers={"content-length": str(Settings().max_media_request_bytes + 1)},
    )
    assert huge.status_code == 413


def test_transcriber_failure_is_friendly_and_leaves_no_partial_state(tmp_path: Path) -> None:
    for error, code in (
        (RuntimeError("CUDA exploded at /secret/path"), "ASR_FAILED"),
        (AsrError("음성 인식 모델(small)이 이 PC에 없습니다.", ("ASR_MODEL_MISSING",)), None),
    ):
        app, client = _app(tmp_path, FakeTranscriber(error=error))
        pid = _project_id(_upload_media(client))
        _wait(app)
        status = client.get(f"/p/{pid}/status").text
        assert "FAILED" in status and "부분 결과는 남기지 않았고" in status
        assert "/secret/path" not in status
        if code:
            assert code in status and "다시 시도" in status
        else:
            assert "ASR_MODEL_MISSING" in status
        store: ProjectStore = app.state.store
        assert not store.path(pid, TRANSCRIPT).exists() and not store.path(pid, MEDIA).exists()
        assert client.get(f"/p/{pid}", follow_redirects=False).status_code == 303
        assert client.get(f"/p/{pid}/download/candidates.xml").status_code == 404


def test_ingest_refusal_after_asr_is_a_failure(tmp_path: Path) -> None:
    payload = wf.transcript_payload()
    payload["segments"][0]["words"][0]["start"] = 0.0004  # type: ignore[index]
    app, client = _app(tmp_path, FakeTranscriber(payload=payload))
    pid = _project_id(_upload_media(client))
    _wait(app)
    status = client.get(f"/p/{pid}/status").text
    assert "FAILED" in status and "NOT_ON_RESOLUTION_GRID" in status
    assert not app.state.store.path(pid, TRANSCRIPT).exists()


def test_one_job_at_a_time(tmp_path: Path) -> None:
    gate = threading.Event()
    app, client = _app(tmp_path, FakeTranscriber(gate=gate))
    pid = _project_id(_upload_media(client))
    assert "새로 고쳐집니다" in client.get(f"/p/{pid}/status").text
    busy = _upload_media(client)
    assert busy.status_code == 409 and "ASR_BUSY" in busy.text
    gate.set()
    _wait(app)
    assert _upload_media(client).status_code == 303


def test_csrf_missing_invalid_or_foreign_origin_refused(tmp_path: Path) -> None:
    app, client = _app(tmp_path)
    client.get("/new")
    missing = client.post(
        "/media", data={"timeline_name": "x"}, files={"media": ("a.mov", MEDIA_BYTES)}
    )
    assert missing.status_code == 403 and "CSRF_INVALID" in missing.text
    assert _upload_media(client, token="A" * 43).status_code == 403
    foreign = client.post(
        "/media",
        data={"csrf_token": _token(client), "timeline_name": "x"},
        files={"media": ("a.mov", MEDIA_BYTES)},
        headers={"origin": "https://evil.example"},
    )
    assert foreign.status_code == 403 and "ORIGIN_MISMATCH" in foreign.text
    assert list(app.state.store.project_ids()) == []
    pid = _project_id(_upload_media(client))
    _wait(app)
    assert client.post(f"/p/{pid}/delete").status_code == 403
    fresh = TestClient(app)  # another browser: its own cookie, our token is useless
    stolen = fresh.post(f"/p/{pid}/delete", data={"csrf_token": _token(client)})
    assert stolen.status_code == 403
    assert app.state.store.exists(pid)
    assert _post(client, f"/p/{pid}/delete").status_code == 200


def test_cleanup_deletes_media(tmp_path: Path) -> None:
    app, client = _app(tmp_path)
    pid = _project_id(_upload_media(client))
    _wait(app)
    store: ProjectStore = app.state.store
    assert store.path(pid, MEDIA).is_file()
    assert app.state.sweep(time.time() + 25 * 3600, force=True) == 1
    assert not (store.root / pid).exists()


def test_user_values_are_html_escaped(tmp_path: Path) -> None:
    app, client = _app(tmp_path)
    pid = _project_id(
        _upload_media(
            client, name="<img src=x onerror=alert(1)>.mov", timeline_name="<script>t</script>"
        )
    )
    _wait(app)
    status = client.get(f"/p/{pid}/status").text
    assert "<img src=x" not in status and "&lt;img src=x onerror=alert(1)&gt;.mov" in status
    page = client.get(f"/p/{pid}").text
    assert "<script>t</script>" not in page and wf.XSS not in page
    assert "&lt;script&gt;t&lt;/script&gt;" in page


# --------------------------------------------------------------------------- trial mode


def _trial(tmp_path: Path, max_projects: int = 5) -> tuple[FastAPI, TestClient, str]:
    app, client = _app(tmp_path, trial_mode=True, trial_max_projects=max_projects)
    code, _ = app.state.invites.issue(72, max_projects, "tester")
    return app, client, code


def _start(client: TestClient, code: str, consent: str = "yes") -> httpx.Response:
    token = _token(client, "/")
    return client.post(
        "/trial/start",
        data={"csrf_token": token, "code": code, "consent": consent},
        follow_redirects=False,
    )


def test_trial_requires_consent_and_a_valid_code(tmp_path: Path) -> None:
    app, client, code = _trial(tmp_path)
    landing = client.get("/").text
    assert "코드 만료(72시간) 시 자동 삭제됩니다" in landing and 'name="consent"' in landing
    assert client.get("/new", follow_redirects=False).headers["location"] == "/"
    no_consent = _start(client, code, consent="")
    assert no_consent.status_code == 400 and "동의" in no_consent.text
    assert "aie_trial" not in client.cookies
    wrong = _start(client, "AIE-NOPE-NOPE-NOPE")
    assert wrong.status_code == 403
    ok = _start(client, code)
    assert ok.status_code == 303 and ok.headers["location"] == "/new"
    new = client.get("/new").text
    assert "5개" in new and "B. 이미 가진 전사 JSON" not in new
    json_path = client.post(
        "/projects",
        data={**wf.form(), "csrf_token": _token(client)},
        files={"transcript": ("t.json", wf.transcript_bytes(), "application/json")},
    )
    assert json_path.status_code == 404  # trial testers upload media only
    invite = app.state.invites.list()[0]
    assert invite.first_used_at is not None and invite.status(time.time()) == "ACTIVE"


def test_trial_project_cap_and_isolation(tmp_path: Path) -> None:
    app, client, code = _trial(tmp_path, max_projects=2)
    _start(client, code)
    first = _project_id(_upload_media(client))
    _wait(app)
    _project_id(_upload_media(client))
    _wait(app)
    third = _upload_media(client)
    assert third.status_code == 400 and "TRIAL_PROJECT_LIMIT" in third.text
    other_code, _ = app.state.invites.issue(72, 5, "other")
    other = TestClient(app)
    _start(other, other_code)
    assert other.get(f"/p/{first}").status_code == 404  # not this code's project
    assert client.get(f"/p/{first}").status_code == 200


def test_trial_failed_asr_gives_the_project_back(tmp_path: Path) -> None:
    app, client, code = _trial(tmp_path, max_projects=1)
    app.state.runner._transcriber = lambda: FakeTranscriber(error=RuntimeError("boom"))
    _start(client, code)
    _project_id(_upload_media(client))
    _wait(app)
    assert app.state.invites.list()[0].projects_created == 0
    app.state.runner._transcriber = lambda: FakeTranscriber()
    assert _upload_media(client).status_code == 303


def test_trial_expiry_deletes_all_projects_of_the_code(tmp_path: Path) -> None:
    app, client, code = _trial(tmp_path)
    _start(client, code)
    pids = [_project_id(_upload_media(client)) for _ in range(1)]
    _wait(app)
    store: ProjectStore = app.state.store
    assert app.state.sweep(time.time() + 25 * 3600, force=True) == 0  # code window is 72 h
    assert all(store.exists(p) for p in pids)
    assert app.state.sweep(time.time() + 73 * 3600, force=True) == 1
    assert not any((store.root / p).exists() for p in pids)
    assert app.state.invites.lookup(code, now=time.time() + 73 * 3600) is None


def test_admin_cli_issue_list_and_revoke_deletes_now(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    settings = _settings(tmp_path, trial_mode=True)
    assert (
        admin.main(["issue", "--hours", "72", "--max-projects", "3", "--label", "kim"], settings)
        == 0
    )
    code = capsys.readouterr().out.split()[0]
    app = create_app(settings, transcriber=FakeTranscriber(), prober=lambda _: cfr_facts())
    client = TestClient(app)
    _start(client, code)
    pid = _project_id(_upload_media(client))
    _wait(app)
    assert admin.main(["list"], settings) == 0
    listing = capsys.readouterr().out
    assert "ACTIVE" in listing and "1/3" in listing and "kim" in listing
    assert admin.main(["revoke", code], settings) == 0
    assert "deleted 1 project" in capsys.readouterr().out
    assert not (ProjectStore(settings).root / pid).exists()
    assert client.get("/new", follow_redirects=False).headers["location"] == "/"
    assert admin.main(["revoke", "nope"], settings) == 1


def test_env_invite_codes_are_seeded(tmp_path: Path) -> None:
    _, client = _app(tmp_path, trial_mode=True, invite_codes=("DEMO-CODE-2026",))
    assert _start(client, "demo-code-2026").status_code == 303
    store = InviteStore(_settings(tmp_path).invites_path)
    assert [i.label for i in store.list()] == ["env"]


# --------------------------------------------------------------------------- hosts / proxy


def test_allowed_hosts_are_configurable(tmp_path: Path) -> None:
    _, client = _app(tmp_path, allowed_hosts=("demo.example.com",))
    assert client.get("/", headers={"host": "demo.example.com"}).status_code == 200
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
    assert client.get("/", headers={"host": "127.0.0.1"}).status_code == 400
    assert Settings().allowed_hosts == ("127.0.0.1", "localhost")  # default stays loopback


def test_forwarded_proto_only_with_trusted_proxy(tmp_path: Path) -> None:
    headers = {"x-forwarded-proto": "https"}
    _, plain = _app(tmp_path)
    assert "secure" not in plain.get("/", headers=headers).headers["set-cookie"].lower()
    _, proxied = _app(tmp_path, trust_proxy=True)
    assert "secure" in proxied.get("/", headers=headers).headers["set-cookie"].lower()


def test_studio_and_guide_pages(tmp_path: Path) -> None:
    _, client = _app(tmp_path)
    studio = client.get("/studio").text
    assert "현재 타임라인" in studio and "개발 중" in studio and "네이티브 검증" in studio
    assert "색보정 전에" in studio
    guide = client.get("/guide").text
    for token in ("CFR", "Import &gt; Timeline", "Relink", "AIE-0001 OK", "FCP 7 XML"):
        assert token in guide


# --------------------------------------------------------------------------- ASR wiring


def test_serialized_faster_whisper_result_is_ingestible() -> None:
    word = SimpleNamespace(start=0.3000000000000000444, end=0.62, word=" 안녕", probability=0.9)
    segment = SimpleNamespace(
        id=1,
        seek=0,
        start=0.3,
        end=0.62,
        text=" 안녕",
        avg_logprob=-0.2,
        compression_ratio=1.1,
        no_speech_prob=0.01,
        temperature=0.0,
        words=[word],
    )
    info = SimpleNamespace(language="ko", language_probability=1.0, duration=2.0)
    seen: list[float] = []
    payload = serialize_result([segment], info, seen.append)
    assert seen == [0.31]
    evidence = ingest_faster_whisper(
        json.loads(json.dumps(payload)),
        evidence_id="t",
        source_ref="m",
        producer=TranscriptProducerRef(
            "faster-whisper", "1.1.1", "small", None, None, None, None, "ko", "UNKNOWN", None
        ),
        clock=AudioClock(16000, True, True, 0),
    )
    assert evidence.segments[0].words[0].start_ms == 300


def _encode_mov(path: Path, pts: list[int], timecode: str | None) -> None:
    av = pytest.importorskip("av")
    np = pytest.importorskip("numpy")
    container = av.open(str(path), "w", format="mov")
    if timecode is not None:
        container.metadata["timecode"] = timecode
    video = container.add_stream("mpeg4", rate=25)
    video.width, video.height, video.pix_fmt = 64, 48, "yuv420p"
    video.codec_context.time_base = Fraction(1, 12800)
    audio = container.add_stream("pcm_s16le", rate=16000, layout="mono")
    image = np.zeros((48, 64, 3), dtype=np.uint8)
    for value in pts:
        frame = av.VideoFrame.from_ndarray(image, format="rgb24").reformat(format="yuv420p")
        frame.pts, frame.time_base = value, Fraction(1, 12800)
        for packet in video.encode(frame):
            container.mux(packet)
    for packet in video.encode():
        container.mux(packet)
    seconds = (pts[-1] + 512) / 12800
    samples = np.zeros((1, int(16000 * seconds)), dtype=np.int16)
    sound = av.AudioFrame.from_ndarray(samples, format="s16", layout="mono")
    sound.sample_rate, sound.pts = 16000, 0
    for packet in audio.encode(sound):
        container.mux(packet)
    for packet in audio.encode():
        container.mux(packet)
    container.close()


def test_pyav_probe_on_generated_files(tmp_path: Path) -> None:
    from aie_web.media import read_streams

    cfr = tmp_path / "cfr.mov"
    _encode_mov(cfr, [i * 512 for i in range(50)], "01:00:00:00")
    probe = evaluate(read_streams(cfr), 600)
    assert probe.rate is not None and (probe.rate.numerator, probe.rate.denominator) == (25, 1)
    assert probe.duration_frames == 50 and probe.start_frame == 90000 and not probe.audio_only
    untagged = tmp_path / "untagged.mov"
    _encode_mov(untagged, [i * 512 for i in range(50)], None)
    assert evaluate(read_streams(untagged), 600).start_frame is None
    vfr = tmp_path / "vfr.mov"
    _encode_mov(vfr, [0, 512, 1024, 2048, 2560, 4096, 4608, 5120, 7000, 7512], None)
    with pytest.raises(PipelineError) as refused:
        evaluate(read_streams(vfr), 600)
    assert "VFR_DETECTED" in refused.value.codes
    junk = tmp_path / "junk.mov"
    junk.write_bytes(b"not a movie" * 10)
    with pytest.raises(PipelineError) as not_media:
        read_streams(junk)
    assert not_media.value.codes[0] == "NOT_MEDIA"


def _tone_wav(path: Path) -> None:
    import math
    import struct
    import wave

    rate = 16000
    samples = [
        int(8000 * math.sin(2 * math.pi * 440 * i / rate)) if i < rate else 0
        for i in range(2 * rate)
    ]
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(1)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(struct.pack(f"<{len(samples)}h", *samples))


@pytest.mark.skipif(os.environ.get("AIE_REAL_ASR") != "1", reason="opt-in: AIE_REAL_ASR=1")
def test_real_small_model_on_synthetic_tone(tmp_path: Path) -> None:
    from aie_web.asr import FasterWhisperTranscriber

    wav = tmp_path / "tone.wav"
    _tone_wav(wav)
    progress: list[float] = []
    output = FasterWhisperTranscriber().transcribe(wav, progress.append)
    assert output.model_revision and output.tool_version == "1.1.1"
    assert output.language_requested == "ko" and output.vad_method == VAD_METHOD
    assert isinstance(output.payload["segments"], list)
    ingest_faster_whisper(
        json.loads(json.dumps(output.payload)),
        evidence_id="real",
        source_ref="tone",
        producer=TranscriptProducerRef(
            "faster-whisper",
            output.tool_version,
            output.model_id,
            None,
            None,
            None,
            None,
            "ko",
            "UNKNOWN",
            None,
        ),
        clock=AudioClock(16000, True, True, 0),
    )


def test_job_file_is_never_served(tmp_path: Path) -> None:
    app, client = _app(tmp_path)
    pid = _project_id(_upload_media(client))
    _wait(app)
    for name in (JOB, MEDIA, "meta.json", "../invites.json"):
        assert client.get(f"/p/{pid}/download/{name}").status_code == 404
