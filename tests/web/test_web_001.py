"""WEB-001: Free web flow end to end through the FastAPI TestClient (synthetic data only).

Resolve is simulated by text edits of our own XML output (marker renames, a
human marker, renumbered clipitem ids). No media, no ASR, no network.
"""

import time
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

import httpx
import web_fixtures as wf
from aie_web.app import create_app
from aie_web.store import ProjectStore, Settings
from fastapi.testclient import TestClient


def _settings(tmp_path: Path, max_transcript_bytes: int = 5 * 1024 * 1024) -> Settings:
    return Settings(
        root=tmp_path / "projects",
        max_age_hours=24.0,
        allowed_hosts=("testserver",),
        max_transcript_bytes=max_transcript_bytes,
    )


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    return _settings(tmp_path)


@pytest.fixture
def client(settings: Settings) -> TestClient:
    return TestClient(create_app(settings))


def _with_token(client: TestClient, data: dict[str, str]) -> dict[str, str]:
    return {**data, "csrf_token": wf.csrf_token(client.get("/new").text)}


def _create(client: TestClient, payload: bytes | None = None, **fields: str) -> str:
    response = client.post(
        "/projects",
        data=_with_token(client, wf.form(**fields)),
        files={
            "transcript": ("transcript.json", payload or wf.transcript_bytes(), "application/json")
        },
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    location = response.headers["location"]
    assert location.startswith("/p/")
    return location.removeprefix("/p/")


def _upload(client: TestClient, url: str, text: str | bytes, **fields: str) -> httpx.Response:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return client.post(
        url,
        data=_with_token(client, fields),
        files={"export": ("export.xml", data, "application/xml")},
        follow_redirects=False,
    )


def _clipitems(text: str, kind: str) -> list[ET.Element]:
    return ET.fromstring(text).findall(f"sequence/media/{kind}/track/clipitem")


def _spans(items: list[ET.Element]) -> list[tuple[str | None, ...]]:
    return [
        (c.findtext("start"), c.findtext("end"), c.findtext("in"), c.findtext("out")) for c in items
    ]


def test_static_pages_explain_free_vs_studio_and_limits(client: TestClient) -> None:
    landing = client.get("/")
    assert landing.status_code == 200
    assert "Studio에서는" in landing.text and "Free" in landing.text
    assert "default-src 'none'" in landing.headers["content-security-policy"]
    limits = client.get("/limits").text
    assert "새 타임라인" in limits and "색보정" in limits and "Studio에서는" in limits
    assert "Studio에서는" in client.get("/new").text


def test_end_to_end_candidates_approval_apply_verify(client: TestClient) -> None:
    pid = _create(client)
    page = client.get(f"/p/{pid}").text
    # candidate list with reasons; transcript gaps labelled as such, not acoustic silence
    for token in ("AIE-0001", "AIE-0002", "AIE-0003"):
        assert token in page
    assert "반복 후보" in page and "필러 후보" in page and "전사 공백 후보" in page
    assert "음향 무음 아님" in page
    assert "Studio에서는" in page
    assert "File &gt; Import &gt; Timeline…" in page and "AIE-0012 OK" in page

    xml = client.get(f"/p/{pid}/download/candidates.xml")
    assert xml.status_code == 200 and "attachment" in xml.headers["content-disposition"]
    video = _clipitems(xml.text, "video")
    assert len(video) == 1 and len(_clipitems(xml.text, "audio")) == 1
    markers = [
        (m.findtext("name"), m.findtext("in"), m.findtext("out"))
        for m in video[0].findall("marker")
    ]
    assert markers == [
        ("AIE-0001 ?", "17", "27"),
        ("AIE-0002 ?", "63", "97"),
        ("AIE-0003 ?", "100", "108"),
    ]
    assert video[0].find("file/timecode/frame") is not None  # media start written, never assumed
    otio = client.get(f"/p/{pid}/download/candidates.otio")
    assert otio.status_code == 200 and '"OTIO_SCHEMA": "Timeline.1"' in otio.text
    srt = client.get(f"/p/{pid}/download/transcript.srt").text
    assert srt.startswith("1\n00:00:00,000 --> 00:00:02,400\n")

    # --- selection in Resolve (simulated) -> confirmation (not yet approval) ---
    response = _upload(client, f"/p/{pid}/approval", wf.editor_export(xml.text))
    assert response.status_code == 303
    confirm = client.get(f"/p/{pid}/confirm")
    assert confirm.status_code == 200
    body = confirm.text
    assert "승인된 컷 2개" in body and "44프레임" in body and "1.760초" in body
    assert "REJECTED" in body and "AIE-0003" in body
    assert "Studio에서는" in body
    digest = wf.hidden_digest(body)
    # nothing applied before the confirm button
    assert client.get(f"/p/{pid}/applied", follow_redirects=False).status_code == 303
    assert client.get(f"/p/{pid}/download/applied.xml").status_code == 400

    # --- wrong digest refused, nothing applied ---
    wrong = client.post(
        f"/p/{pid}/confirm", data=_with_token(client, {"digest": "0" * 64}), follow_redirects=False
    )
    assert wrong.status_code == 400 and "일치하지 않습니다" in wrong.text
    assert client.get(f"/p/{pid}/applied", follow_redirects=False).status_code == 303

    # --- approval: the exact digest ---
    ok = client.post(
        f"/p/{pid}/confirm", data=_with_token(client, {"digest": digest}), follow_redirects=False
    )
    assert ok.status_code == 303 and ok.headers["location"] == f"/p/{pid}/applied"
    applied_page = client.get(f"/p/{pid}/applied").text
    assert "인터뷰 AIE v2" in applied_page and "검증되지 않은" in applied_page
    applied = client.get(f"/p/{pid}/download/applied.xml").text
    video, audio = _clipitems(applied, "video"), _clipitems(applied, "audio")
    expected = [
        ("0", "17", "0", "17"),
        ("17", "53", "27", "63"),
        ("53", "156", "97", "200"),
    ]
    assert _spans(video) == expected and _spans(audio) == expected  # identical A/V cut
    assert [m.findtext("name") for c in video for m in c.findall("marker")] == ["AIE-0003 X"]
    for v in video:
        assert len(v.findall("link")) == 2  # linked A/V

    # --- verification of a simulated immediate re-export ---
    report = _upload(
        client, f"/p/{pid}/verify", wf.reexport(applied), provenance="IMMEDIATE_REEXPORT"
    )
    assert report.status_code == 200
    text = report.text
    assert "MATCH (일치)" in text and "FILE_ROUNDTRIP" in text
    # re-export after a human edit without evidence is never a success
    edited = _upload(
        client,
        f"/p/{pid}/verify",
        wf.reexport(applied).replace("<end>17</end>", "<end>16</end>", 1),
        provenance="IMMEDIATE_REEXPORT",
    )
    assert "MATCH (일치)" not in edited.text


def test_human_edit_is_protected_and_shown(client: TestClient) -> None:
    pid = _create(client)
    xml = client.get(f"/p/{pid}/download/candidates.xml").text
    text = wf.rename(xml, "AIE-0001 ?", "AIE-0001 OK")
    human = "<marker><name>keep laugh</name><comment /><in>150</in><out>151</out></marker>"
    text = text.replace("</clipitem>", human + "</clipitem>", 1)
    assert _upload(client, f"/p/{pid}/approval", text).status_code == 303
    body = client.get(f"/p/{pid}/confirm").text
    assert "HUMAN_EDIT_LOCKED" in body and "승인된 컷 0개" in body
    assert 'name="digest"' not in body  # no confirm button without approved cuts


def test_unknown_marker_is_never_applied(client: TestClient) -> None:
    pid = _create(client)
    xml = client.get(f"/p/{pid}/download/candidates.xml").text
    text = wf.rename(xml, "AIE-0001 ?", "AIE-0001 maybe")
    _upload(client, f"/p/{pid}/approval", text)
    body = client.get(f"/p/{pid}/confirm").text
    assert "UNKNOWN" in body and "MALFORMED" in body and "승인된 컷 0개" in body


def test_transcript_text_is_html_escaped(client: TestClient) -> None:
    pid = _create(client, timeline_name="<img src=x onerror=alert(2)>")
    page = client.get(f"/p/{pid}").text
    assert wf.XSS not in page and "<img src=x" not in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page
    assert "&lt;img src=x onerror=alert(2)&gt;" in page


def test_oversize_uploads_are_refused(tmp_path: Path) -> None:
    client = TestClient(create_app(_settings(tmp_path, max_transcript_bytes=512)))
    big = wf.transcript_bytes() + b" " * 1024
    response = client.post(
        "/projects",
        data=_with_token(client, wf.form()),
        files={"transcript": ("t.json", big, "application/json")},
    )
    assert response.status_code == 413 and "너무 큽니다" in response.text
    huge = b"x" * (Settings().max_request_bytes + 10)
    response = client.post(
        "/projects",
        data=_with_token(client, wf.form()),
        files={"transcript": ("t.json", huge, "application/json")},
    )
    assert response.status_code == 413


def test_malformed_json_and_xml_get_friendly_errors(client: TestClient) -> None:
    response = client.post(
        "/projects",
        data=_with_token(client, wf.form()),
        files={"transcript": ("t.json", b"{not json", "application/json")},
    )
    assert response.status_code == 400 and "전사 JSON 형식이 올바르지 않습니다" in response.text
    assert "D:\\Footage\\interview.mov" in response.text  # form values kept (escaped)
    wrong_shape = client.post(
        "/projects",
        data=_with_token(client, wf.form()),
        files={"transcript": ("t.json", b'{"segments": 3}', "application/json")},
    )
    assert wrong_shape.status_code == 400 and "INVALID_TYPE" in wrong_shape.text
    pid = _create(client)
    bad = _upload(client, f"/p/{pid}/approval", "<xmeml><oops")
    assert bad.status_code == 400 and "FCP7 XML을 읽을 수 없습니다" in bad.text
    xxe = '<?xml version="1.0"?><!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><xmeml>&e;</xmeml>'
    refused = _upload(client, f"/p/{pid}/approval", xxe)
    assert refused.status_code == 400 and "FCP7 XML을 읽을 수 없습니다" in refused.text
    assert "root:" not in refused.text
    assert (
        client.get(f"/p/{pid}/confirm", follow_redirects=False).status_code == 303
    )  # nothing stored


def test_project_ids_cannot_traverse_paths(client: TestClient, settings: Settings) -> None:
    secret = settings.root.parent / "secret.txt"
    secret.write_text("top secret", "utf-8")
    for path in (
        "/p/..%2Fsecret.txt",
        "/p/..%2F..%2Fetc",
        "/p/ABCDEF",
        "/p/" + "0" * 32,
        "/p/%2E%2E",
        "/p/" + "0" * 32 + "/download/candidates.xml",
    ):
        response = client.get(path)
        assert response.status_code == 404, path
        assert "top secret" not in response.text
    pid = _create(client)
    assert client.get(f"/p/{pid}/download/meta.json").status_code == 404
    assert client.post("/p/..%2Fprojects/delete", data=_with_token(client, {})).status_code == 404
    assert secret.exists()


def test_delete_and_cleanup(client: TestClient, settings: Settings) -> None:
    first, second = _create(client), _create(client)
    deleted = client.post(f"/p/{first}/delete", data=_with_token(client, {}))
    assert deleted.status_code == 200
    assert client.get(f"/p/{first}").status_code == 404
    store = ProjectStore(settings)
    assert store.cleanup(now=time.time()) == 0
    assert store.cleanup(now=time.time() + 25 * 3600) == 1
    assert client.get(f"/p/{second}").status_code == 404
    assert list(settings.root.iterdir()) == []


def test_resolve_profile_requires_media_start(client: TestClient) -> None:
    response = client.post(
        "/projects",
        data=_with_token(client, wf.form(media_start="")),
        files={"transcript": ("t.json", wf.transcript_bytes(), "application/json")},
    )
    assert response.status_code == 400 and "MEDIA_START_UNKNOWN" in response.text
    assert "0으로 가정하지 않습니다" in response.text
    pid = _create(client, media_start="", profile="GENERIC")  # generic keeps it UNKNOWN
    xml = client.get(f"/p/{pid}/download/candidates.xml").text
    assert _clipitems(xml, "video")[0].find("file/timecode") is None
    assert client.get(f"/p/{pid}/download/candidates.otio").status_code == 200


def test_rate_must_come_from_the_whitelist(client: TestClient) -> None:
    response = client.post(
        "/projects",
        data=_with_token(client, wf.form(rate="23.98")),
        files={"transcript": ("t.json", wf.transcript_bytes(), "application/json")},
    )
    assert response.status_code == 400 and "UNKNOWN_RATE" in response.text


def test_foreign_host_header_refused(client: TestClient) -> None:
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
