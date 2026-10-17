# WEB-002 — Media Upload, Local ASR and Trial Mode (Free web flow)

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**. Not native qualification.
Nothing here has been exercised against DaVinci Resolve. Builds on WEB-001
(docs/WEB_001_STATUS.md); the candidate → XML → approval → confirm → applied →
verify flow is unchanged.

## Purpose (user decisions 2026-10-17)

- Free is a **trial demo for external prospects** that shows the flow working
  end to end; the real product will be Studio-only. Every page carries a
  "Studio에서는 …" note linking to `/studio`, which compares Free and Studio
  (EDITION_DELIVERY_STRATEGY.md §3) and states the honest status: Studio path in
  development, native verification pending, grades/effects kept only "where
  Resolve supports it, after native verification"; until then "confirm cuts
  before grading".
- Media upload + local ASR (faster-whisper `small`, CPU, int8) replace the
  "bring your own transcript JSON" step. The JSON path stays for development
  (hidden in trial mode).
- Trial invite codes are **time-limited**: valid 72 h from first use, up to 5
  projects per code, each media ≤ 10 min, one active ASR job globally. When a
  code expires or is revoked, all its projects, media and results are deleted.

## Files

- `apps/web/aie_web/media.py` — PyAV demux-only probe (`read_streams`) + pure policy (`evaluate`), file-name/folder rules
- `apps/web/aie_web/asr.py` — `Transcriber` protocol, `FasterWhisperTranscriber` (offline, lazy, cached model), own 16 kHz decoder, `serialize_result`
- `apps/web/aie_web/jobs.py` — single worker thread, job state in `job.json`
- `apps/web/aie_web/trial.py` — invite codes (hash-only storage, 72 h window, project cap, revoke)
- `apps/web/aie_web/security.py` — CSRF double-submit cookie, Origin check, HTTPS detection (`X-Forwarded-Proto` only with `trust_proxy`)
- `apps/web/aie_web/admin.py` — `python -m aie_web.admin issue|list|revoke|sweep`
- `apps/web/aie_web/app.py`, `render.py`, `store.py`, `pipeline.py`, `__init__.py` — routes, pages, env settings, producer facts
- `tests/web/test_web_002.py` (new), `tests/web/test_web_001.py` / `web_fixtures.py` (CSRF tokens added)
- `pyproject.toml` — new optional extra `asr`
- `docs/WEB_002_STATUS.md` (this file)

The core package (`src/davinci_ai_editor`) is unchanged and stays
zero-dependency. ASR lives only in `apps/web` behind the optional extra:

```text
asr = ["faster-whisper==1.1.1", "requests==2.32.3", "av==19.0.1"]
```

`requests==2.32.3` is needed because faster-whisper 1.1.1 imports `requests`
without declaring it (the install fails without it). `av` is pinned to the
version validated here (see "Finding" below). CI's `web` job still installs
only `.[dev,web]`; no test needs the model or PyAV (those tests skip).

**Finding — faster-whisper 1.1.1 + PyAV ≥ 14:** faster-whisper's own
`decode_audio` calls `av.open(..., metadata_errors="ignore")`, a keyword PyAV 14
removed, so with the PyAV pip resolves today (19.0.1) every
`WhisperModel.transcribe(path)` raises `TypeError`. `aie_web.asr.decode_audio_16k`
decodes the same way (s16 mono 16 kHz resample, FIFO grouping, invalid frames
skipped) and passes the float32 array to `transcribe` instead.

## How to run locally

```text
pip install -e ".[dev,web,asr]"
# one-time model download (the only network use; the server never downloads):
python -c "from faster_whisper.utils import download_model; download_model('small')"
python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765
```

Open <http://127.0.0.1:8765/>. At runtime the server sets `HF_HUB_OFFLINE=1`,
`HF_HUB_DISABLE_TELEMETRY=1` and loads with `local_files_only=True`; a missing
model gives the Korean error `ASR_MODEL_MISSING` (no download).

## Settings (environment variables)

| Variable | Default | Meaning |
|---|---|---|
| `AIE_WEB_ROOT` | `<temp>/aie-web-projects` | project directories (+ `invites.json`) |
| `AIE_WEB_MAX_AGE_HOURS` | 24 | retention for non-trial projects |
| `AIE_WEB_ALLOWED_HOSTS` | `127.0.0.1,localhost` | accepted Host headers (add the tunnel/proxy hostname) |
| `AIE_WEB_TRUST_PROXY` | 0 | honour `X-Forwarded-Proto` (cookie `Secure` flag) |
| `AIE_WEB_SECURE_COOKIES` | 0 | always mark cookies `Secure` |
| `AIE_WEB_MAX_MEDIA_MB` | 1024 | upload byte cap — set **95** behind the Cloudflare quick tunnel (100 MB request-body cap on the free plan) |
| `AIE_WEB_MAX_MEDIA_MINUTES` | 10 | media duration cap |
| `AIE_ASR_MODEL` / `AIE_ASR_LANGUAGE` / `AIE_ASR_VAD` | `small` / `ko` / 1 | faster-whisper model, language, default `vad_filter` (INT-002: the upload form has a per-project VAD checkbox, ticked by default) |
| `AIE_ASR_DEVICE` / `AIE_ASR_COMPUTE_TYPE` / `AIE_ASR_MODEL_DIR` | `cpu` / `int8` / HF cache | model loading |
| `AIE_WEB_TRIAL` | 0 | trial mode on |
| `AIE_WEB_TRIAL_CODE_HOURS` | 72 | code validity from first use |
| `AIE_WEB_TRIAL_MAX_PROJECTS` | 5 | projects per code |
| `AIE_WEB_INVITE_CODES` | — | comma list of codes seeded at startup (label `env`) |
| `AIE_WEB_INVITES_FILE` | `<root>/invites.json` | invite store |
| `AIE_WEB_TRIAL_IP_FAILURES` | 5 | INT-002: wrong codes per client before exponential lockout (30 s doubling, max 1 h) |
| `AIE_WEB_TRIAL_GLOBAL_FAILURES` | 50 | INT-002: wrong codes from all clients in 10 min before a 5-min global lock |

## Flow additions

| Page | What happens |
|---|---|
| `/` (trial, no session) | Korean consent notice — **"업로드한 영상은 전사·후보 생성에만 사용되며 코드 만료(72시간) 시 자동 삭제됩니다"** — code field and a required checkbox → `POST /trial/start` sets an HttpOnly SameSite=Strict cookie |
| `/new` → `POST /media` | upload (streamed to `media.bin`, byte cap) → PyAV probe → refusals → project; storage/deletion notice with the deletion time |
| `/p/{id}/facts` | asked only when needed: start timecode (no tag; never assumed 0; "일반" profile allowed), frame rate (audio-only files), timeline start |
| `/p/{id}/status` | QUEUED / RUNNING (progress %, meta refresh, no JS) / DONE / FAILED (friendly message + codes) |
| `/p/{id}` … | unchanged WEB-001 flow |
| `/studio`, `/guide` | Free vs Studio + honest status; Resolve Free tester guide |

Media probe (`media.evaluate`): audio required (`NO_AUDIO`); frame rate =
stream `avg_frame_rate`, must equal `r_frame_rate` and the PTS deltas of the
first 600 video packets must all be one frame in `time_base` ticks, else
`VFR_DETECTED` with "CFR로 변환 후 다시 올려 주세요"; rate must be exactly on the
SMPTE whitelist (`RATE_NOT_WHITELISTED`); duration in frames from the stream
frame count (else floor of duration × rate); `MEDIA_TOO_LONG`; start timecode
only from a `timecode` tag parsed with the core parser (else asked); audio
starting ≥ 1 frame after video becomes the transcript offset, audio starting
before video is refused (`AUDIO_BEFORE_VIDEO`). Extensions are an allow-list;
the original name is text only. XML media path = user folder (absolute, as
Resolve sees it) + original name; without a folder the path is
`/AIE-RELINK/<name>` on purpose so Resolve shows it offline and the user relinks.

ASR: `WhisperModel.transcribe(audio, language="ko", word_timestamps=True,
vad_filter=<setting>)`; the result is serialized to the exact
`ingest_faster_whisper` shape and stored as `transcript.json` **only after**
the full WEB-001 build accepts it. `TranscriptProducerRef` records tool version
(`faster_whisper.__version__`), model id (`small (cpu, int8)`), model revision
(HF snapshot hash), VAD method and a SHA-256 of the effective `VadOptions`, and
the requested language. Any failure (model missing, decoder error, TXE refusal
such as `NOT_ON_RESOLUTION_GRID`) → FAILED with a friendly Korean message;
transcript and media are deleted, no partial project state, and a trial
project is given back to its code.

## Security

- CSRF: every state-changing form carries `csrf_token` (double-submit cookie
  `aie_csrf`, HttpOnly, SameSite=Strict, constant-time compare); a present
  `Origin` must match the Host. Missing/invalid → 403 `CSRF_INVALID` /
  `ORIGIN_MISMATCH`.
- Host allow-list is configurable (default loopback only). Trial projects are
  visible only to the browser holding the code that created them.
- Upload caps: request `Content-Length` checked per route (media: cap + 1 MiB),
  file streamed in 1 MiB chunks to `media.bin.part` and refused above the cap.
  python-multipart spools the upload to the system temp dir first (deleted when
  the request ends).
- Invite codes: 12 random characters from a 31-letter alphabet (~59 bits),
  stored only as SHA-256 (fixed prefix); wrong codes get one generic message.
  INT-002 adds brute-force protection (per-client and global attempt limits with
  backoff, in memory; a guessed trial cookie counts too) — see docs/INT_002_STATUS.md.
- Retention: sweep at startup and at most once a minute on requests; non-trial
  projects after `AIE_WEB_MAX_AGE_HOURS`, trial projects when their code
  expires or is revoked. Revoke via CLI deletes immediately.

## Admin CLI

```text
set PYTHONPATH=apps/web   (PowerShell: $env:PYTHONPATH="apps/web")
python -m aie_web.admin issue --hours 72 --max-projects 5 --label "kim"   # prints the code once
python -m aie_web.admin list      # id, status, label, used/max, remaining time, first use
python -m aie_web.admin revoke AIE-XXXX-XXXX-XXXX   # or the id; deletes its projects now
python -m aie_web.admin sweep     # delete projects of expired/revoked codes now
```

Use the same `AIE_WEB_ROOT` / `AIE_WEB_INVITES_FILE` as the server.

## Hosting options for a 3-day external trial (nothing deployed)

**(1) This PC + Cloudflare quick tunnel** (fastest; PC must stay on, awake and online for 3 days)

```text
winget install --id Cloudflare.cloudflared
cloudflared tunnel --url http://127.0.0.1:8765        # prints https://<random>.trycloudflare.com
# in another terminal, with that hostname:
$env:AIE_WEB_TRIAL="1"; $env:AIE_WEB_ALLOWED_HOSTS="<random>.trycloudflare.com,127.0.0.1,localhost"
$env:AIE_WEB_TRUST_PROXY="1"; $env:AIE_WEB_SECURE_COOKIES="1"; $env:AIE_WEB_MAX_MEDIA_MB="95"
$env:AIE_WEB_ROOT="D:\aie-trial"; python -m aie_web.admin issue --label tester1
python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765
```

Risks: the quick-tunnel URL is random, changes on every restart and has no
uptime guarantee; Cloudflare's free plan caps a request body at 100 MB (hence
`AIE_WEB_MAX_MEDIA_MB=95` — a 10-min 1080p file may need re-encoding smaller);
the PC's CPU runs the ASR for every tester (one job at a time); the PC is
exposed through the tunnel (keep the server bound to 127.0.0.1, keep the OS
updated, use a data folder with nothing else in it; the 23 G2 source files must
not be under `AIE_WEB_ROOT`). Whether cloudflared forwards the public Host
header unchanged is UNVERIFIED here: if the first page returns 400, check the
Host it sends and adjust `AIE_WEB_ALLOWED_HOSTS`.

**(2) Small temporary cloud VM** (4 vCPU / 8 GB, Ubuntu; delete it after the trial)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir -e ".[web,asr]" \
 && python -c "from faster_whisper.utils import download_model; download_model('small')"
ENV AIE_WEB_ROOT=/data AIE_WEB_TRIAL=1 AIE_WEB_TRUST_PROXY=1 AIE_WEB_SECURE_COOKIES=1
EXPOSE 8765
CMD ["python", "-m", "uvicorn", "aie_web.app:app", "--app-dir", "apps/web", "--host", "0.0.0.0", "--port", "8765"]
```

Steps: create the VM with a firewall allowing only 22/80/443 → install Docker
and Caddy → `docker build -t aie-trial .` → `docker run -d -p 127.0.0.1:8765:8765
-e AIE_WEB_ALLOWED_HOSTS=demo.example.com -v /srv/aie:/data aie-trial` →
`caddy reverse-proxy --from demo.example.com --to 127.0.0.1:8765` (automatic
HTTPS) → issue codes with `docker exec … python -m aie_web.admin issue` →
after 3 days revoke all codes and **delete the VM and its disk**. The model is
downloaded at build time only. Cost and provider choice are open.

## What it does NOT do

- No public deployment (only the local server was started), no accounts or
  auth beyond invite codes, no database, no LLM, no network call at runtime,
  no Resolve API / UI automation, no rendering.
- No acoustic silence detection (transcript gaps only), no diarization, no
  model other than the configured faster-whisper model; no GPU path tested.
- No virus scanning of uploads (invite-code rate limiting: INT-002)
  (files are only demuxed/decoded by PyAV/FFmpeg, never executed), no
  multi-process deployment (single worker thread and in-process locks).
- The user's own test video was not processed here (only synthetic media).

## Tests (`tests/web/test_web_002.py`)

Upload → mocked transcriber (fixed faster-whisper-shaped result) → full flow to
MATCH; producer facts recorded; relink placeholder and relative-folder refusal;
VFR refusal (avg≠base and irregular PTS); non-whitelisted rate, no audio,
audio-before-video, audio offset, NTSC drop-frame tag; missing start timecode
prompt (refused empty for Resolve, accepted after entry); audio-only asks for
rate; oversize / too long / bad extension / oversize request refused;
transcriber failure (generic and model-missing) friendly, no transcript, no
media; TXE refusal after ASR = failure; one job at a time (409); CSRF missing,
invalid, foreign Origin, other browser's token; cleanup deletes media; HTML
escaping of file name and timeline name; trial consent required, invalid code,
JSON path disabled, N-project cap, cross-code isolation, failed ASR gives the
project back, expiry deletes all projects of the code, admin issue/list/revoke
(deletes now), env-seeded codes; allowed hosts configurable; `X-Forwarded-Proto`
only with trusted proxy; Studio and guide pages; serialized result ingestible;
PyAV probe on generated CFR / untagged / VFR / junk files (skips without PyAV);
**opt-in** real `small` model on a generated 2-second tone+silence WAV
(`AIE_REAL_ASR=1`, skipped by default). WEB-001 tests now send CSRF tokens.

## Validation

Python 3.12.10 `.venv` with `PYTHONPATH=<worktree>/src` (verified
`davinci_ai_editor.__file__` inside this worktree); faster-whisper 1.1.1,
PyAV 19.0.1, `small` model from the local cache.

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/web            37 passed, 1 skipped
AIE_REAL_ASR=1 python -m pytest ... tests/web/test_web_002.py -k real             1 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                      2564 passed, 3 skipped
python -m ruff check src tests tools apps                                         All checks passed
python -m ruff format --check apps tests/web                                      16 files already formatted
python -m mypy                                                                    Success, 58 source files
MYPYPATH=src;apps/web;tests/web python -m mypy --strict --explicit-package-bases apps/web/aie_web tests/web   Success, 16 files
git diff --check                                                                  clean
uvicorn on 127.0.0.1:8766: GET / -> 200, /studio -> 200, Host evil.example -> 400; a generated
3-second CFR .mov (tone, timecode tag) uploaded through the real probe + real small model -> DONE,
candidate XML with file:///D:/Footage/tone.mov; project deleted; server stopped
```

## Open questions

- "Tier 1: confirm only before grading" was referenced as being in
  EDITION_DELIVERY_STRATEGY.md, but this branch's copy has no tier list; the
  Studio page uses §3 plus the explicit "native verification pending / confirm
  cuts before grading" wording. Please confirm or add the tier text.
- Invite-code brute-force rate limiting and per-IP limits before any public URL?
- Retention for trial projects is the code window (72 h from first use), not
  `AIE_WEB_MAX_AGE_HOURS`; should there also be a shorter per-project cap?
- Should a failed ASR still count against the code (now: given back)?
- Default `vad_filter=True`: faster-whisper maps timestamps back to the original
  timeline, but VAD can drop very quiet speech; keep it on?
- Hosting choice for the 3-day trial (tunnel vs VM) and the 100 MB tunnel cap.

---

## 사용 안내 — 내 테스트 영상으로 DaVinci Resolve 무료 버전에서 해 보기

1. **설치(한 번)**: 저장소 루트에서 `pip install -e ".[dev,web,asr]"` 후
   `python -c "from faster_whisper.utils import download_model; download_model('small')"`
   로 모델을 미리 받아 둡니다(서버는 실행 중에 내려받지 않습니다).
2. **영상 준비**: 1~10분 정도 말하는 영상. 23개 G2 원본 파일은 쓰지 말고 따로 찍은 영상을 씁니다.
   휴대폰 영상은 대개 가변 프레임레이트(VFR)이므로 **CFR로 변환**합니다(예: HandBrake의
   "Constant Framerate", 또는 Resolve에서 같은 프레임레이트로 렌더).
3. **서버 실행**: `python -m uvicorn aie_web.app:app --app-dir apps/web --host 127.0.0.1 --port 8765`
   후 `http://127.0.0.1:8765/` 를 엽니다.
4. **업로드**: **새 프로젝트 → A. 영상 올리기**에서 파일을 고르고, Resolve에서 보이는 원본
   폴더 경로(예: `D:\Footage`)를 적습니다(비우면 나중에 Relink). VFR이면
   "CFR로 변환 후 다시 올려 주세요"가 나옵니다.
5. **시작 타임코드**: 파일에 타임코드 태그가 없으면 Resolve 미디어 풀에서 클립의 **Start TC**를
   확인해 입력합니다. 0으로 가정하지 않습니다.
6. **전사 대기**: 상태 페이지가 3초마다 새로 고쳐집니다(CPU에서는 영상 길이 정도 걸릴 수 있음).
7. **Resolve 준비**: 새 프로젝트를 만들고 **File > Project Settings > Master Settings**의
   Timeline frame rate를 영상과 **같게** 맞춥니다(타임라인 만들기 전에).
8. **XML 가져오기**: 후보 목록에서 **FCP7 XML**을 받아 **File > Import > Timeline…** 으로 가져옵니다.
   클립이 오프라인(빨간색)이면 미디어 풀에서 우클릭 > **Relink Selected Clips…** 로 원본 폴더를 지정합니다.
9. **마커 이름 바꾸기**: `AIE-0001 ?` 마커를 적용할 것은 `AIE-0001 OK`, 뺄 것은 `AIE-0001 X`로
   바꿉니다. 마커를 옮기거나 지우지 않습니다.
10. **내보내기 → 업로드**: **File > Export > Timeline…** 에서 **FCP 7 XML**로 저장해 프로젝트
    페이지의 승인 업로드에 올립니다.
11. **확인**: 확인 요약(컷 수, 제거 초, 건너뛴 항목)을 읽고 **확인 — 승인한 컷 적용**을 누릅니다.
12. **적용된 XML 가져오기**: `… AIE v2` XML을 받아 다시 Import > Timeline 으로 가져옵니다(새
    타임라인이므로 색보정 전에 하세요).
13. **검증**: 가져온 새 타임라인을 고치지 않고 다시 FCP 7 XML로 내보내 올리면
    MATCH / MISMATCH / UNVERIFIED 리포트가 나옵니다. UNVERIFIED는 성공이 아닙니다.
14. **정리**: 프로젝트 페이지의 **이 프로젝트 삭제**로 영상과 결과를 즉시 지웁니다.

### 체험 모드 켜기 (외부 테스터용)

`AIE_WEB_TRIAL=1`로 서버를 띄우고 `python -m aie_web.admin issue --label 이름`으로 코드를
만들어 전달합니다. 테스터는 첫 페이지에서 동의 체크 후 코드를 입력합니다. 코드는 처음 쓴
때부터 72시간, 프로젝트 5개, 영상당 10분까지이며, 만료·회수 시 그 코드의 모든 프로젝트가
자동 삭제됩니다. 테스터용 Resolve 안내는 `/guide` 페이지에 있습니다.
