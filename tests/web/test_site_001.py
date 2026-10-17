"""SITE-001: Coditor public landing site (landing, privacy, robots, shared design, no externals)."""

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("multipart")

import web_fixtures as wf
from aie_web import render
from aie_web.app import create_app
from aie_web.store import Settings
from fastapi.testclient import TestClient

PUBLIC_PAGES = ("/", "/privacy", "/studio", "/guide", "/limits")
_URL = re.compile(
    r"""(?:https?:)?//[^\s"'<>]+|\b(?:src|href|action)\s*=\s*["'](?!/|#|mailto:|data:)"""
)


def _client(tmp_path: Path, **overrides: object) -> TestClient:
    values: dict[str, object] = {
        "root": tmp_path / "projects",
        "allowed_hosts": ("testserver",),
    }
    values.update(overrides)
    return TestClient(create_app(Settings(**values)))  # type: ignore[arg-type]


def _trial_client(tmp_path: Path) -> tuple[TestClient, str]:
    client = _client(tmp_path, trial_mode=True)
    app = client.app
    code, _ = app.state.invites.issue(72, 5, "tester")  # type: ignore[attr-defined]
    return client, code


def test_landing_renders_core_message_sections_and_meta(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/")
    assert response.status_code == 200
    page = response.text
    for token in (
        "<title>Coditor — 인터뷰 편집 어시스턴트 for DaVinci Resolve</title>",
        "AI에게 편집 업무는 맡기되, 편집권은 넘기지 않는다.",
        "찾는 건 Coditor가",
        "결정은 편집자가.",
        "작동 방식 보기",
        'id="problem"',
        'id="how"',
        'id="why"',
        'id="compare"',
        'id="start"',
        "후보 표시",
        "Resolve 안에서 승인",
        "승인한 컷만 적용",
        "적용 결과 검증",
        "사람이 고친 부분은 다시 돌려도 보존",
        "레이어를 합치지 않음",
        "자동 삭제 없음, 승인 필수",
        "한국어 후보",
        "개발 중 · 실기 검증 예정",
        "tier 1",
        'lang="ko"',
        'name="description"',
        'property="og:title"',
        'property="og:description"',
        'rel="icon" type="image/svg+xml" href="data:image/svg+xml,',
        'content="index, follow"',
        'role="img"',
        "<main",
        "<footer",
        "© Coditor",
        'href="/privacy"',
    ):
        assert token in page, token
    visible = re.sub(r"<[^>]+>", " ", page.split('<main id="main">', 1)[1])
    assert re.search(r"\d+\s*%", visible) is None  # no time-saving percentages
    assert '<ol class="steps">' in page and page.count("<svg") >= 5


def test_landing_cta_depends_on_trial_state(tmp_path: Path) -> None:
    local = _client(tmp_path / "local").get("/").text
    assert 'href="/new">새 프로젝트 만들기' in local and 'name="consent"' not in local
    client, code = _trial_client(tmp_path / "trial")
    open_page = client.get("/").text
    assert 'href="#start">체험 코드로 시작하기' in open_page
    assert 'action="/trial/start"' in open_page and 'name="consent"' in open_page
    assert "72시간" in open_page and "프로젝트 5개" in open_page and "CFR" in open_page
    assert "Resolve 무료 버전" in open_page
    assert client.get("/trial").status_code == 200
    token = wf.csrf_token(open_page)
    ok = client.post(
        "/trial/start",
        data={"csrf_token": token, "code": code, "consent": "yes"},
        follow_redirects=False,
    )
    assert ok.status_code == 303 and ok.headers["location"] == "/new"
    active = client.get("/").text
    assert "체험 중입니다" in active and 'name="consent"' not in active
    assert "5개 더 만들 수 있습니다" in active
    assert client.get("/trial", follow_redirects=False).headers["location"] == "/new"
    assert _client(tmp_path / "off").get("/trial").status_code == 404


def test_contact_email_is_configurable_placeholder(tmp_path: Path) -> None:
    default = _client(tmp_path / "a").get("/").text
    assert 'href="mailto:contact@safestay.kr?subject=' in default
    custom = _client(tmp_path / "b", contact_email="hello@example.org").get("/").text
    assert "mailto:hello@example.org" in custom and "contact@safestay.kr" not in custom
    privacy = _client(tmp_path / "c", contact_email="hello@example.org").get("/privacy").text
    assert "mailto:hello@example.org" in privacy


def test_contact_email_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AIE_WEB_CONTACT_EMAIL", " team@example.org ")
    assert Settings.from_env().contact_email == "team@example.org"
    monkeypatch.delenv("AIE_WEB_CONTACT_EMAIL")
    assert Settings.from_env().contact_email == "contact@safestay.kr"


def test_contact_email_is_escaped(tmp_path: Path) -> None:
    page = _client(tmp_path, contact_email='x"><script>alert(1)</script>').get("/").text
    assert "<script>alert(1)</script>" not in page and "&lt;script&gt;" in page


def test_privacy_page_follows_retention_rules(tmp_path: Path) -> None:
    trial = _client(tmp_path / "t", trial_mode=True, trial_code_hours=72.0).get("/privacy")
    assert trial.status_code == 200
    text = trial.text
    for token in (
        "개인정보 안내",
        "전사와 편집 후보 생성에만",
        "72시간",
        "자동으로 삭제",
        "aie_csrf",
    ):
        assert token in text, token
    assert "aie_trial" in text and "이 프로젝트 삭제" in text and "외부 글꼴" in text
    local = _client(tmp_path / "l", max_age_hours=24.0).get("/privacy").text
    assert "24시간이 지나면 자동으로 삭제" in local


def test_studio_and_guide_public_pages(tmp_path: Path) -> None:
    client = _client(tmp_path)
    studio = client.get("/studio")
    assert studio.status_code == 200 and "Free 체험과 Studio" in studio.text
    assert "개발 중" in studio.text and "Coditor" in studio.text
    guide = client.get("/guide")
    assert guide.status_code == 200 and "DaVinci Resolve 무료 버전으로 체험하기" in guide.text


def test_public_html_names_no_external_url(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path in (*PUBLIC_PAGES, "/new", "/trial-missing"):
        text = client.get(path).text
        found = _URL.findall(text)
        assert not found, (path, found)
        assert "<script" not in text.lower()
        assert "@import" not in text and "url(" not in text  # no fonts / remote CSS
    trial, _ = _trial_client(tmp_path / "trial")
    for path in ("/", "/trial"):
        assert not _URL.findall(trial.get(path).text)


def test_robots_txt(tmp_path: Path) -> None:
    response = _client(tmp_path).get("/robots.txt")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    lines = response.text.splitlines()
    assert lines[0] == "User-agent: *"
    for allowed in ("/", "/privacy", "/studio", "/guide"):
        assert f"Allow: {allowed}" in lines
    for blocked in ("/p/", "/new", "/media", "/projects", "/trial", "/admin"):
        assert f"Disallow: {blocked}" in lines
    assert response.text == render.ROBOTS_TXT


def test_security_headers_on_public_pages(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path in (*PUBLIC_PAGES, "/robots.txt"):
        headers = client.get(path).headers
        csp = headers["content-security-policy"]
        assert "default-src 'none'" in csp and "frame-ancestors 'none'" in csp
        assert "script-src" not in csp  # no script is ever allowed
        assert headers["x-content-type-options"] == "nosniff"
        assert headers["referrer-policy"] == "no-referrer"
    cookies = _client(tmp_path / "fresh").get("/").headers.get_list("set-cookie")
    assert len(cookies) == 1 and cookies[0].startswith("aie_csrf=")


def test_app_pages_share_design_tokens_and_are_noindex(tmp_path: Path) -> None:
    client = _client(tmp_path)
    for path in ("/new", "/limits", "/studio", "/guide", "/privacy", "/"):
        text = client.get(path).text
        assert "--accent:" in text and "prefers-color-scheme:light" in text, path
        assert 'class="skip" href="#main"' in text and ":focus-visible" in text
    assert 'content="noindex, nofollow"' in client.get("/new").text
    assert 'content="index, follow"' in client.get("/privacy").text


def test_unknown_host_still_refused(tmp_path: Path) -> None:
    client = _client(tmp_path, allowed_hosts=("safestay.kr", "www.safestay.kr", "testserver"))
    assert client.get("/", headers={"host": "safestay.kr"}).status_code == 200
    assert client.get("/", headers={"host": "www.safestay.kr"}).status_code == 200
    assert client.get("/", headers={"host": "evil.example"}).status_code == 400
