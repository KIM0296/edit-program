"""INT-002 web additions: per-track effect + override on the confirmation page,
invite-code brute-force protection, per-project VAD, Studio wording.

TEST_ONLY_SUPPORT. No Resolve, no media (synthetic transcript / fake transcriber).
"""

import re
from pathlib import Path

import pytest

pytest.importorskip("fastapi")

import httpx
import web_fixtures as wf
from aie_web.app import create_app
from aie_web.ratelimit import AttemptLimiter, LimitPolicy
from aie_web.render import STUDIO_STATUS_EN
from aie_web.store import Settings
from fastapi.testclient import TestClient
from test_web_002 import FakeTranscriber, _app, _project_id, _upload_media, _wait

from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.handoff_model import (
    HandoffClip,
    HandoffGap,
    HandoffMediaRef,
    HandoffTimeline,
    HandoffTrack,
    HandoffTrackKind,
)
from davinci_ai_editor.xmeml_reader import read_xmeml
from davinci_ai_editor.xmeml_writer import write_xmeml

SFX = HandoffMediaRef("sfx.wav", "D:/Footage/sfx.wav", FrameRange(0, 500), 0)
MUSIC = HandoffMediaRef("music.wav", "D:/Footage/music.wav", FrameRange(0, 500), 0)


def _client(tmp_path: Path) -> TestClient:
    settings = Settings(root=tmp_path / "projects", allowed_hosts=("testserver",))
    return TestClient(create_app(settings))


def _token(client: TestClient, page: str = "/new") -> str:
    return wf.csrf_token(client.get(page).text)


def _project(client: TestClient) -> str:
    response = client.post(
        "/projects",
        data={**wf.form(), "csrf_token": _token(client)},
        files={"transcript": ("t.json", wf.transcript_bytes(), "application/json")},
        follow_redirects=False,
    )
    assert response.status_code == 303, response.text
    return response.headers["location"].rsplit("/", 1)[-1]


def _with_track(candidate_xml: str, track: HandoffTrack) -> str:
    """The editor adds a layer in Resolve before exporting (a human addition)."""
    read = read_xmeml(candidate_xml)
    assert read.timeline is not None
    actual = read.timeline
    timeline = HandoffTimeline(
        actual.name, actual.rate, actual.start_frame, (*actual.tracks, track), actual.markers
    )
    text = write_xmeml(timeline).text
    assert text is not None
    return text


def _upload(client: TestClient, pid: str, text: str) -> httpx.Response:
    return client.post(
        f"/p/{pid}/approval",
        data={"csrf_token": _token(client)},
        files={"export": ("export.xml", text.encode("utf-8"), "application/xml")},
        follow_redirects=False,
    )


def _policy(client: TestClient, pid: str, track: str, policy: str) -> httpx.Response:
    return client.post(
        f"/p/{pid}/policy",
        data={"track": track, "policy": policy, "csrf_token": _token(client)},
        follow_redirects=False,
    )


def _summary_digest(page: str) -> str:
    match = re.search(r"confirmation_digest: ([0-9a-f]{64})", page)
    assert match is not None
    return match.group(1)


def _approve(xml: str, *tokens: str) -> str:
    for token in tokens:
        xml = wf.rename(xml, f"{token} ?", f"{token} OK")
    return xml


def test_confirm_page_shows_per_track_effect_and_override_changes_the_digest(
    tmp_path: Path,
) -> None:
    client = _client(tmp_path)
    pid = _project(client)
    candidates = client.get(f"/p/{pid}/download/candidates.xml").text
    sfx = HandoffTrack(
        "Audio 2",
        HandoffTrackKind.AUDIO,
        (HandoffGap(150), HandoffClip("sfx", SFX, FrameRange(0, 30))),
    )
    export = _approve(_with_track(candidates, sfx), "AIE-0001", "AIE-0002")
    assert _upload(client, pid, export).status_code == 303
    page = client.get(f"/p/{pid}/confirm").text
    assert "트랙별 결과" in page
    assert "자름 (44프레임)" in page  # V1 and A1: the dialogue and its linked audio
    assert "당김 44프레임" in page  # the SFX layer is not cut, only moved left
    assert 'action="/p/' + pid + '/policy"' in page and "함께 자르기" in page
    default_digest = wf.hidden_digest(page)
    # the user keeps the SFX in place: a different decision, a different digest
    assert _policy(client, pid, "Audio 2", "KEEP_IN_PLACE").status_code == 303
    page = client.get(f"/p/{pid}/confirm").text
    assert "변경: 그대로 두기" in page and "그대로" in page and "SYNC_SHIFT" in page
    keep_digest = wf.hidden_digest(page)
    assert keep_digest != default_digest
    stale = client.post(
        f"/p/{pid}/confirm",
        data={"digest": default_digest, "csrf_token": _token(client)},
        follow_redirects=False,
    )
    assert stale.status_code == 400 and "APPLY_REFUSED" in stale.text  # nothing applied
    applied = client.post(
        f"/p/{pid}/confirm",
        data={"digest": keep_digest, "csrf_token": _token(client)},
        follow_redirects=False,
    )
    assert applied.status_code == 303
    read = read_xmeml(client.get(f"/p/{pid}/download/applied.xml").text)
    assert read.timeline is not None
    starts = [s for s, _ in read.timeline.tracks[2].placements()]
    assert starts == [150]  # KEEP_IN_PLACE: the SFX did not move
    applied_page = client.get(f"/p/{pid}/applied").text
    assert "그대로" in applied_page and "자름 (44프레임)" in applied_page
    # changing the policy again makes the earlier approval stale; DEFAULT restores it
    assert _policy(client, pid, "Audio 2", "DEFAULT").status_code == 303
    assert client.get(f"/p/{pid}/applied", follow_redirects=False).status_code == 303
    assert wf.hidden_digest(client.get(f"/p/{pid}/confirm").text) == default_digest


def test_music_bed_conflict_and_override_on_a_human_added_layer(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pid = _project(client)
    candidates = client.get(f"/p/{pid}/download/candidates.xml").text
    music = HandoffTrack(
        "Audio 2", HandoffTrackKind.AUDIO, (HandoffClip("music", MUSIC, FrameRange(0, 200)),)
    )
    assert _upload(client, pid, _approve(_with_track(candidates, music), "AIE-0001")).is_redirect
    page = client.get(f"/p/{pid}/confirm").text
    assert "보류: LAYER_CONFLICT (AIE-0001)" in page and "LAYER_CONFLICT" in page
    assert 'name="digest"' not in page  # nothing to approve
    before = _summary_digest(page)
    assert _policy(client, pid, "Audio 2", "CUT_WITH_SOURCE").status_code == 303
    page = client.get(f"/p/{pid}/confirm").text
    assert "변경: 함께 자르기" in page
    assert _summary_digest(page) != before  # the override is bound by the digest
    # the music was added by a human in Resolve: Human Edit Wins, it is never cut
    assert "HUMAN_EDIT_LOCKED" in page and 'name="digest"' not in page


def test_unknown_track_or_policy_is_refused(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pid = _project(client)
    candidates = client.get(f"/p/{pid}/download/candidates.xml").text
    assert _upload(client, pid, _approve(candidates, "AIE-0001")).is_redirect
    assert _policy(client, pid, "Audio 9", "CUT_WITH_SOURCE").status_code == 400
    assert _policy(client, pid, "Audio 1", "UNKNOWN").status_code == 400
    assert _policy(client, pid, "Audio 1", "MERGE").status_code == 400
    no_csrf = client.post(f"/p/{pid}/policy", data={"track": "Audio 1", "policy": "KEEP_IN_PLACE"})
    assert no_csrf.status_code == 403


def test_marker_moved_to_cut_is_noted(tmp_path: Path) -> None:
    client = _client(tmp_path)
    pid = _project(client)
    candidates = client.get(f"/p/{pid}/download/candidates.xml").text
    export = _approve(candidates, "AIE-0001").replace(
        "</media>", "</media><marker><name>chapter</name><in>20</in><out>-1</out></marker>", 1
    )
    assert _upload(client, pid, export).is_redirect
    page = client.get(f"/p/{pid}/confirm").text
    assert "MARKER_MOVED_TO_CUT" in page and "컷 지점으로 옮김" in page


# --------------------------------------------------------------------------- brute force


class Clock:
    def __init__(self) -> None:
        self.now = 1_000_000.0

    def __call__(self) -> float:
        return self.now


def _trial_client(
    tmp_path: Path, limiter: AttemptLimiter, **settings: object
) -> tuple[TestClient, str]:
    values: dict[str, object] = {
        "root": tmp_path / "projects",
        "allowed_hosts": ("testserver",),
        "trial_mode": True,
    }
    values.update(settings)
    app = create_app(
        Settings(**values),  # type: ignore[arg-type]
        transcriber=FakeTranscriber(),
        limiter=limiter,
    )
    code, _ = app.state.invites.issue(72, 5, "tester")
    return TestClient(app), code


def _start(client: TestClient, code: str, **headers: str) -> httpx.Response:
    return client.post(
        "/trial/start",
        data={"csrf_token": _token(client, "/"), "code": code, "consent": "yes"},
        headers=headers,
        follow_redirects=False,
    )


def test_invite_code_entry_is_rate_limited_per_client_with_backoff(tmp_path: Path) -> None:
    clock = Clock()
    limiter = AttemptLimiter(LimitPolicy(ip_free_failures=3, ip_base_seconds=30), clock)
    client, code = _trial_client(tmp_path, limiter)
    for _ in range(2):
        assert _start(client, "AIE-AAAA-BBBB-CCCC").status_code == 403
    third = _start(client, "AIE-AAAA-BBBB-CCCC")
    assert third.status_code == 429 and "TRIAL_RATE_LIMITED" in third.text
    assert int(third.headers["retry-after"]) >= 30
    # while locked even the right code is not looked up
    locked = _start(client, code)
    assert locked.status_code == 429 and "aie_trial" not in client.cookies
    clock.now += 31
    assert _start(client, "AIE-AAAA-BBBB-CCCC").status_code == 429  # 4th failure: 60 s
    clock.now += 61
    ok = _start(client, code)
    assert ok.status_code == 303 and ok.headers["location"] == "/new"
    assert limiter.retry_after("testclient") == 0  # success clears the client


def test_invite_code_global_limit_and_cookie_guesses(tmp_path: Path) -> None:
    clock = Clock()
    limiter = AttemptLimiter(
        LimitPolicy(ip_free_failures=100, global_max_failures=4, global_lock_seconds=300), clock
    )
    client, code = _trial_client(tmp_path, limiter, trust_proxy=True)
    for n in range(3):  # a distributed guess: every request from another address
        wrong = _start(client, "AIE-AAAA-BBBB-CCCC", **{"X-Forwarded-For": f"203.0.113.{n}"})
        assert wrong.status_code == 403
    # a guessed trial cookie is a guess too (and counts globally)
    client.cookies.set("aie_trial", "AIE-ZZZZ-ZZZZ-ZZZZ")
    assert client.get("/new", follow_redirects=False).headers["location"] == "/"
    client.cookies.clear()
    blocked = _start(client, code, **{"X-Forwarded-For": "198.51.100.7"})
    assert blocked.status_code == 429  # global lock: nobody can try a code now
    clock.now += 301
    assert _start(client, code, **{"X-Forwarded-For": "198.51.100.7"}).status_code == 303


def test_limiter_policy_validation_and_memory_bound() -> None:
    with pytest.raises(ValueError):
        LimitPolicy(ip_free_failures=0)
    clock = Clock()
    limiter = AttemptLimiter(LimitPolicy(ip_free_failures=1, ip_max_seconds=10), clock)
    assert limiter.failure("a") == 10  # backoff capped at ip_max_seconds (30 s base > 10)
    limiter.success("a")
    assert limiter.retry_after("a") == 0


# --------------------------------------------------------------------------- VAD + Studio


def test_vad_is_on_by_default_and_can_be_turned_off_per_project(tmp_path: Path) -> None:
    fake = FakeTranscriber()
    app, client = _app(tmp_path, fake)
    new = client.get("/new").text
    assert 'name="vad" value="1" checked' in new and "VAD" in new
    _project_id(_upload_media(client))  # browsers without the field: server default (on)
    _wait(app)
    off = _upload_media(client, vad_choice="1")  # checkbox unticked
    pid_off = _project_id(off)
    _wait(app)
    assert fake.vads == [True, False]
    source = app.state.store.meta(pid_off)["source"]
    assert source["vad_method"] is None  # the producer facts say VAD was off
    _app2, client2 = _app(tmp_path / "noenv", FakeTranscriber(), asr_vad=False)
    assert 'name="vad" value="1">' in client2.get("/new").text  # unchecked by setting


def test_studio_wording_matches_edition_strategy(tmp_path: Path) -> None:
    client = _client(tmp_path)
    studio = client.get("/studio").text
    assert STUDIO_STATUS_EN in studio
    assert "네이티브 검증 대기" in studio and "tier 1" in studio and "검증 중" in studio
    landing = client.get("/").text
    assert "현재 타임라인</b>에 바로 적용" not in landing
    assert "색보정 전" in landing
