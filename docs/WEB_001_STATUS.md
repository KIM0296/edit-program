# WEB-001 — Free Web Flow (Local Development Server)

> **WEB-002 update:** media upload, local ASR, trial mode and CSRF tokens on all forms are
> described in docs/WEB_002_STATUS.md. The "no media upload / no ASR" statements below
> describe WEB-001 as it was committed.

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**. Not native qualification.
Nothing here has been exercised against DaVinci Resolve. In the tests, every
"editor" action is a text edit of our own XML output.

## Purpose

Phase 1 of the Free edition (docs/EDITION_DELIVERY_STRATEGY.md §5): a browser
flow that shows every core outcome of the product through a file round-trip
with Resolve Free (persuasion checklist §4), with a "Studio에서는 …" note on
each page where Studio differs (§3).

It is a **local development server only**: it binds `127.0.0.1`, accepts only
`127.0.0.1` / `localhost` Host headers, has no deployment, no auth and no
database. There is no media upload, no ASR, no LLM call and no network call.

## Files

- `apps/web/aie_web/__init__.py`, `__main__.py` — package, `python -m aie_web [port]` (loopback only)
- `apps/web/aie_web/pipeline.py` — pure wiring of the public core modules (no web framework)
- `apps/web/aie_web/store.py` — `Settings`, per-project working directories, cleanup
- `apps/web/aie_web/render.py` — stdlib HTML (`html.escape`, `string.Template`), Korean UI, no JS
- `apps/web/aie_web/app.py` — FastAPI routes, size limits, security headers
- `tests/web/conftest.py`, `tests/web/web_fixtures.py`, `tests/web/test_web_001.py`
- `pyproject.toml` — new optional extra `web` (exact pins)
- `.github/workflows/ci.yml` — new `web` job (existing `domain` job unchanged)
- `docs/WEB_001_STATUS.md` (this file)

The core package stays zero-dependency. Web dependencies live only in the
`web` extra: `fastapi==0.115.6`, `uvicorn==0.32.1`, `python-multipart==0.0.20`,
`httpx==0.28.1` (TestClient). No template engine. `apps/web` imports only the
public core modules (`transcript_evidence`, `korean_text_candidates`,
`handoff_model`, `candidate_markers`, `xmeml_writer`, `xmeml_reader`,
`otio_json`, `subtitle_io`, `roundtrip_diff`, `apply_cuts`,
`roundtrip_verification`, `timecode`).

## How to run locally

From the repository root:

```text
pip install -e ".[dev,web]"
python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765
```

Then open <http://127.0.0.1:8765/>. Optional environment variables:
`AIE_WEB_ROOT` (project root directory; default `<system temp>/aie-web-projects`)
and `AIE_WEB_MAX_AGE_HOURS` (default 24). This exact command was started once
during validation (see below). `python -m aie_web` (with `apps/web` on
`sys.path`) does the same on port 8765.

## Flow

| Page | What happens | Axis |
|---|---|---|
| `/` | Free vs Studio value, flow overview | — |
| `/limits` | honest limits | — |
| `/new` → `POST /projects` | transcript JSON (faster-whisper or whisperX serialized shape) + media facts form → TXE ingest → frame projection → KOR-001 filler/repetition candidates + transcript-gap candidates → candidate list | proposal |
| `/p/{id}` | candidate list with reasons; downloads: FCP7 XML with `AIE-xxxx ?` markers (default), OTIO (optional), SRT; Resolve Free import steps; marker rename convention; approval upload; delete button | proposal |
| `POST /p/{id}/approval` | Resolve-exported FCP7 XML → `read_xmeml` (hardened) → RT-001 diff → `read_marker_selections` | SELECTION |
| `/p/{id}/confirm` | `build_apply_confirmation`: cut count, frames/seconds removed, per-cut list, skipped items with codes (`REJECTED`, `PENDING`, `UNKNOWN`, `HUMAN_EDIT_LOCKED`, `MARKER_CONFLICT`), shifted HARD_LOCK content, deterministic summary text; the 확인 button posts the exact `confirmation_digest` | CONFIRMATION |
| `POST /p/{id}/confirm` | `apply_approved_cuts(confirmation, confirmed_digest=…)`; a wrong digest is refused (HTTP 400) and nothing is applied | APPROVAL |
| `/p/{id}/applied` | new Expected timeline `<name> AIE v2` (video + audio cut at identical frames, ripple, linked A/V) as FCP7 XML; labelled unverified | apply (artifact) |
| `POST /p/{id}/verify` | re-exported FCP7 XML → VER-001 report: MATCH / MISMATCH / UNVERIFIED with per-item codes; provenance is a user declaration (`IMMEDIATE_REEXPORT` or `AFTER_HUMAN_EDIT`) | VERIFICATION |

Inputs and policy details:

- Media facts are never guessed: media path as Resolve sees it (not a URL),
  frame rate from the SMPTE whitelist only, media duration in frames, and media
  start timecode/frame. The **Resolve profile requires the media start**
  (`MEDIA_START_UNKNOWN` refusal otherwise); the generic profile keeps it
  UNKNOWN (no file timecode in the XML, OTIO `DEFAULT` profile).
- The Expected timeline is one clip of the whole media on `V1` and `A1`
  starting at timeline frame 0, so source frames equal timeline frames.
- Projection: transcript time 0 = media start (+ optional offset in ms);
  tolerance = max(1 frame, producer resolution).
- Candidates (all proposals, never auto-applied; IDs `AIE-0001…` in timeline order):
  - repetition (KOR-001 `EXACT_REPEAT` / `PREFIX_RESTART`): from the first
    word's start to the second word's start;
  - filler (KOR-001 lexicon, always AMBIGUOUS): the word's range;
  - transcript gap (`WEB-001-TRANSCRIPT-GAP-V1`): between two consecutive
    timed words when the gap ≥ the threshold (default 1.0 s, form field), keeping
    `max(tolerance, 0.1 s)` padding on both sides. Labelled **"전사 공백 (음향
    무음 아님)"**: it is a gap between transcript word timings, not acoustic
    silence. A gap overlapping a transcript segment without word timings is
    shown but not marked.
  - Untimed, zero-length, out-of-media and overlapping candidates are listed
    as "마커로 만들지 않은 후보" with the reason (priority on overlap:
    repetition > filler > gap).
- State: no database. Each project is a directory named by 32 random hex
  characters under the root, holding the transcript, the facts/policy, the
  last approval XML and the confirmed digest. Everything (candidates, digests,
  applied timeline) is re-derived deterministically on each request. A new
  approval upload removes any earlier confirmed digest (stale). Projects older
  than `AIE_WEB_MAX_AGE_HOURS` are deleted at startup and after each project
  creation; the delete button removes a project immediately.

## Security

- Upload limits: transcript 5 MiB, XML 8 MiB (file read capped at limit+1
  bytes), whole request limit checked from `Content-Length` (requests without
  it are refused, 411). Oversize → 413.
- XML only through `read_xmeml` (refuses entities, DTD subsets, external
  DOCTYPEs, oversize, malformed documents). JSON through `json.loads` with
  NaN/Infinity rejected, then TXE typed ingest. Errors are friendly Korean pages
  with English diagnostic codes.
- Project IDs must match `^[0-9a-f]{32}$` and resolve to a direct child of the
  root; anything else is 404. Download names are a fixed allow-list.
- Every user-derived value is HTML-escaped. CSP `default-src 'none'; style-src
  'unsafe-inline'; form-action 'self'; frame-ancestors 'none'; base-uri 'none'`,
  `nosniff`, `same-origin` referrer policy (browsers then send the real `Origin` on same-site form posts; `no-referrer` made Safari/Firefox send `Origin: null`, which the CSRF origin check refused), `no-store`. Trusted Host guard against DNS rebinding.

## What it does NOT do

- No deployment, auth, database, media upload, ASR, LLM, network call or
  rendering. No Resolve API call and no UI automation: importing every file
  into Resolve is a manual user step.
- No auto-apply. A marker rename is a selection; the confirmation page is not
  an approval; only the posted digest is. Generated files are Expected
  artifacts (`authorizes_import = False`, applied `verified = False`).
- UNKNOWN is never shown as success (malformed or moved markers, whole-UNKNOWN
  diffs, identity ambiguity and missing provenance evidence stay UNKNOWN /
  UNVERIFIED).
- One round-trip per project: re-running candidates on the applied `AIE v2`
  timeline (a second approval round) is not wired. Human-edit protection is
  shown on the approval upload (RT-001 HARD_LOCK from edits made in Resolve
  before export).
- No baseline re-export or per-change acknowledgement in the verification UI:
  `AFTER_HUMAN_EDIT` without evidence yields UNKNOWN items → UNVERIFIED.

## Tests (`tests/web/test_web_001.py`, guarded by `pytest.importorskip("fastapi")`)

- End to end through TestClient: create project → candidate page (3 candidates
  with reasons, transcript gap labelled) → download FCP7 XML and parse the
  markers (and OTIO, SRT) → rename markers in the XML text (OK / 승인 / X) →
  upload → confirmation page (2 cuts, 44 frames, 1.760 s, REJECTED listed) →
  nothing applied before confirming → wrong digest refused (400) → correct
  digest → applied XML parsed: video and audio cut at identical frames, links,
  remaining marker → simulated immediate re-export (renumbered clipitem ids) →
  **MATCH**; an edited re-export is not MATCH.
- Human-added marker → `HUMAN_EDIT_LOCKED`, no confirm button; malformed marker
  name → `UNKNOWN` / `MALFORMED`.
- HTML escaping of transcript text and form values (XSS); oversize upload and
  oversize request refused (413); malformed JSON, wrong JSON shape, malformed
  XML and an XXE document refused with friendly errors; path traversal on
  project IDs and download names refused (404); delete and age-based cleanup;
  missing media start refused for the Resolve profile (generic profile allowed,
  no file timecode written); non-whitelisted rate refused; foreign Host header
  refused.

## Validation

Python 3.12.10 `.venv` with `PYTHONPATH=<worktree>/src` (verified
`davinci_ai_editor.__file__` inside this worktree); CI target 3.11, no
3.12-only syntax. Web deps installed into the venv at the pinned versions
(pydantic 2.14.1 and starlette 0.41.3 resolved transitively).

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/web            12 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                      2539 passed, 2 skipped
python -m ruff check src tests tools apps                                         All checks passed
python -m ruff format --check apps tests/web                                      9 files already formatted
python -m mypy                                                                    Success, 58 source files
MYPYPATH=src;apps/web;tests/web python -m mypy --strict --explicit-package-bases apps/web/aie_web tests/web   Success, 9 files
git diff --check                                                                  clean
python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765  started; GET / -> 200 text/html; Host: evil.example -> 400; stopped
```

## Open questions

- Whether Resolve Free imports SRT relative to the timeline start, honours the
  FCP7 `<link>` groups and keeps marker comments on export is UNVERIFIED (same
  as RT-001 / APPLY-001 open questions on source in/out convention).
- Should the transcript-gap padding and the repetition range (first word start
  to second word start) be user-tunable per project?
- Should a second approval round on the applied `AIE v2` timeline be supported
  in the Free web flow (re-anchoring remaining candidates), or left to Studio?
- Before any public deployment: ASR hosting, retention policy for uploads,
  auth, CSRF tokens (today the only state-changing protection beyond the
  loopback host guard is that the apply step requires the exact digest).

---

## 사용 안내 (DaVinci Resolve 무료 버전으로 직접 해 보기)

1. **준비**: 인터뷰 영상 파일 하나와, 그 영상을 faster-whisper(단어 타임스탬프 켬)
   또는 whisperX로 전사한 결과 JSON을 준비합니다. 이 웹은 영상을 업로드받지 않습니다.
2. **서버 실행**: 저장소 루트에서 `pip install -e ".[dev,web]"` 후
   `python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765`
   를 실행하고 브라우저에서 `http://127.0.0.1:8765/` 를 엽니다.
3. **새 프로젝트**: 전사 JSON을 올리고, Resolve에서 보이는 그대로 미디어 경로,
   프레임레이트, 길이(프레임), **미디어 시작 타임코드**(클립 속성의 Start TC)를 입력합니다.
   시작 타임코드는 0으로 가정하지 않으므로 Resolve 프로필에서는 꼭 입력해야 합니다.
4. **후보 확인**: 반복·필러·전사 공백 후보와 이유가 표시됩니다. 전사 공백은 소리를
   분석한 무음이 아니라 단어 타이밍 사이의 빈 구간입니다.
5. **다운로드 → Resolve**: FCP7 XML을 받아 **File > Import > Timeline…** 으로 가져오고,
   오프라인이면 Relink로 원본을 연결합니다. 자막은 SRT를 **File > Import > Subtitle…**
   로 가져와 타임라인에 놓습니다.
6. **마커로 선택**: 적용할 후보는 마커 이름을 `AIE-0012 OK`(또는 `AIE-0012 승인`)로,
   제외할 후보는 `AIE-0012 X`(또는 `AIE-0012 제외`)로 바꿉니다. 마커를 옮기거나
   복사·삭제하지 마세요. 이름 변경은 선택일 뿐 승인이 아닙니다.
7. **내보내기 → 승인 업로드**: **File > Export > Timeline…** 에서 FCP 7 XML로 내보내
   업로드하면 확인 요약(컷 수, 제거 초, 건너뛴 항목과 이유)이 나옵니다. 사람이 고친
   구간은 `HUMAN_EDIT_LOCKED`로 보호되어 건너뜁니다.
8. **확인 버튼**: 내용을 확인하고 **확인 — 승인한 컷 적용**을 누르면 비디오와 오디오가
   같은 프레임에서 잘린 새 타임라인(`… AIE v2`) XML을 받을 수 있습니다. Resolve로
   가져오기는 직접 합니다. **새 타임라인이므로 이전 타임라인의 색보정·이펙트·믹스는
   넘어오지 않습니다 — 컷 승인은 마무리 작업 전에 하세요.**
9. **검증**: 가져온 새 타임라인을 아무것도 고치지 않고 다시 FCP 7 XML로 내보내 올리면
   MATCH / MISMATCH / UNVERIFIED 리포트를 받습니다. UNVERIFIED는 성공이 아닙니다.
10. **정리**: 프로젝트 페이지의 **이 프로젝트 삭제** 버튼으로 즉시 지울 수 있고,
    오래된 프로젝트는 자동으로 삭제됩니다.

Studio에서는 같은 후보와 같은 승인 규칙이 Resolve 안에서 파일 없이 현재 타임라인에
바로 적용되며, 그레이드·이펙트·믹스가 유지됩니다.
