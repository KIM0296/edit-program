# TASK 완료 보고서

TASK: TASK-022 — Canonical Asset Generator & First Package Build
상태: **구현 및 실제 first-package candidate 생성 완료 / Chat Gate 대기**
브랜치: `feat/task-022-canonical-asset-generator`
시작 base: `7659aabe7dbb6a18ac4b1b940b809e08c424eef9`
동기화한 documentation main / diff 기준: `40b27c2457b086a9d05b47e30b21e70aff5c346e`
실제 generator build head: `8f57179ee226c08581ddaf416ed79bafd00b29c3`
최종 review head / CI: [PR #48](https://github.com/KIM0296/edit-program/pull/48) 본문에 기록.
근거: ADR-034/036/037, [TASK-022 spec](../../tasks/TASK_022_CANONICAL_ASSET_GENERATOR_FIRST_PACKAGE.md).
요청 Gate: **APPROVED** — 검토 요청이며 Chat의 승인 선언이 아닙니다.

## 1. 구현 내용

- `tools/canonical_assets`에 production adapter와 분리된 synthetic engineering tooling을 구현했습니다.
- 1280×720 RGB24, 24/1 fps, 720 frames: integer pixel, 지정 배경, 8px border, embedded 5×7 glyph,
  role/frame/second counter, MSB-first binary code, moving bar, second indicator.
- Integer triangle/envelope, 48kHz/stereo/signed 24-bit PCM, 1,440,000 samples/channel와 deterministic
  RIFF/WAVE writer. Literal golden pixel/sample tests가 있으며 font lookup/float trig/resampling이 없습니다.
- Frozen toolchain preflight와 closed token recipes: software DNxHR LB/yuv422p MOV encode,
  explicit stream mapping 및 PCM/video stream-copy mux. Codec/profile fallback 없음.
- 실제 stream 구조, zero-error full video decode, 모든 720 frames의 raster/non-interlace,
  final MOV PCM exact equality, WAV header/data equality를 검증합니다.
- Canonical manifest/lock/checksums와 real digest, 두 fresh run의 9개 파일 byte equality,
  local collision-safe sealing, actual-hash package index까지 완료했습니다.
- Spec 1–59의 근거는 [TEST_MATRIX](../TEST_MATRIX.md)의 TASK-022 영역에 연결했습니다.

## 2. 변경된 파일

| 파일/영역 | 목적 |
| --- | --- |
| tools/canonical_assets/model.py, glyphs_5x7.py, video_pattern.py, audio_pattern.py, wav.py | fixed recipe, integer source, deterministic WAV |
| tools/canonical_assets/ffmpeg.py, validate.py | typed preflight/commands, structural/full decode validation |
| tools/canonical_assets/checksums.py, manifest.py, package.py, generate.py | canonical bytes/hash, full two-run build, validation/seal/CLI |
| tools/canonical_assets/recipe.v1.json, README.md, __init__.py; tools/__init__.py | recipe lock와 tooling boundary |
| tests/test_canonical_patterns.py, test_canonical_tooling.py, test_canonical_package.py | 71개 신규 test cases |
| canonical_assets/first-package-candidate-v1/* | 실제 manifest/lock/checksums/index/comparison의 작은 evidence 사본 |
| pyproject.toml, .github/workflows/ci.yml | NumPy pin, Python 3.11 CI, tooling Ruff/strict mypy |
| .gitignore, .gitattributes | media Git 제외와 canonical evidence bytes 보존 |
| TASK spec, DECISIONS, IMPLEMENTATION_STATUS, KNOWN_LIMITATIONS, TEST_MATRIX, 보고서 | 상태/결과/미검증 경계 |

### git diff --stat

비교 기준 `40b27c2`. 실제 생성 source는 위 build head이며 이후 변경은 테스트/문서/증거입니다.

<!-- DIFFSTAT_START -->
```text
 .gitattributes                                     |   3 +
 .github/workflows/ci.yml                           |   2 +-
 .gitignore                                         |   6 +
 DECISIONS.md                                       |  32 +-
 IMPLEMENTATION_STATUS.md                           |  17 +
 KNOWN_LIMITATIONS.md                               |  18 +
 .../first-package-candidate-v1/checksums.sha256    |   8 +
 .../comparison-report.json                         |   1 +
 .../first-package-candidate-v1/generator.lock.json |   1 +
 .../first-package-candidate-v1/manifest.v1.json    |   1 +
 .../package-index.candidate.json                   |   1 +
 docs/TEST_MATRIX.md                                |  17 +
 docs/reports/TASK_022_COMPLETION.md                | 271 +++++++++++++++
 pyproject.toml                                     |   3 +-
 ..._022_CANONICAL_ASSET_GENERATOR_FIRST_PACKAGE.md |  14 +-
 tests/test_canonical_package.py                    | 256 ++++++++++++++
 tests/test_canonical_patterns.py                   | 165 +++++++++
 tests/test_canonical_tooling.py                    | 373 +++++++++++++++++++++
 tools/__init__.py                                  |   1 +
 tools/canonical_assets/README.md                   |  39 +++
 tools/canonical_assets/__init__.py                 |   1 +
 tools/canonical_assets/audio_pattern.py            |  59 ++++
 tools/canonical_assets/checksums.py                |  98 ++++++
 tools/canonical_assets/ffmpeg.py                   | 286 ++++++++++++++++
 tools/canonical_assets/generate.py                 | 104 ++++++
 tools/canonical_assets/glyphs_5x7.py               |  26 ++
 tools/canonical_assets/manifest.py                 | 211 ++++++++++++
 tools/canonical_assets/model.py                    |  69 ++++
 tools/canonical_assets/package.py                  | 350 +++++++++++++++++++
 tools/canonical_assets/recipe.v1.json              |   1 +
 tools/canonical_assets/validate.py                 | 195 +++++++++++
 tools/canonical_assets/video_pattern.py            |  65 ++++
 tools/canonical_assets/wav.py                      |  23 ++
 33 files changed, 2706 insertions(+), 11 deletions(-)
```
<!-- DIFFSTAT_END -->

## 3. 테스트 결과

- Local Windows / Python **3.11.9** / NumPy **2.3.5**.
- 신규: **70 passed / 1 skipped**. 전체: **1417 passed / 2 skipped**.
- Skip: Windows symlink 생성 권한 1개, 기존 naive INV-001 opt-in intentional red demo 1개.
- Ruff **PASS**. Strict mypy **PASS**, 33 files.
- Python 3.11 CI: [run 37591852493](https://github.com/KIM0296/edit-program/actions/runs/37591852493) **1418 passed / 1 skipped**, Ruff / strict mypy PASS.
  검증 head: `993f96bba75fb90d11a2b9aebf50b9bffeb49695`. Linux에서는 symlink 테스트도 통과했습니다.
  이후 CI 근거만 추가한 최종 문서 head의 검사 상태는 PR 본문에서 확인할 수 있습니다.
- Red-first: missing module, metadata contradiction, missing field_order의 explicit decoded-frame proof,
  FFmpeg 9 decode syntax, missing WAV channel_layout의 canonical header proof 실패를 재현한 뒤 수정했습니다.
- Source PCM/RGB digest mismatch, encoder failure/no retry도 별도 테스트했습니다.
- 기존 pytest temp/cache의 Windows 권한 충돌은 새 basetemp 및 cacheprovider 비활성화로 분리했고,
  동일 Python 3.11.9 전체 회귀가 위 수치로 통과했습니다.
- Native Resolve integration은 **미실행**이며 unit/mock 성공을 Resolve support로 보고하지 않습니다.

최종 regression 명령:

```powershell
& "C:UsershelljAppDataLocalProgramsPythonPython311python.exe" -m pytest -q -p no:cacheprovider --basetemp "C:UsershelljProjectsedit-program-canonicalpytest-task022-final"
python -m ruff check src tests tools
python -m mypy
```

### Locked toolchain evidence

| 항목 | 실제 값 |
| --- | --- |
| Python | 3.11.9 |
| NumPy | 2.3.5 |
| Fixed release | autobuild-2026-10-06-13-06 |
| ZIP | ffmpeg-n9.0.2-22-g46d8f462ee-win64-gpl-9.0.zip |
| ZIP SHA-256 (추출 전 검증) | bf721765dbb181cd7a076bdd53c2665fa2c371dac07472b461fd7f357b1f2057 |
| FFmpeg SHA-256 | 406b6aae37d0783336c61d87a8dc720d8e8585685eee46ce403dc9a093127bc0 |
| ffprobe SHA-256 | bffaf8571a5fcac42c6c10427145cc8533377c5a881481b51c2135e2f3a5e576 |
| Configuration/capability digest | a4e240f89cdfb244b80babb8d4c2d4b49a9eb9b188ba7dc4d60bfc2a61b9d667 |

FFmpeg: `ffmpeg version n9.0.2-22-g46d8f462ee-20261006 Copyright (c) 2000-2026 the FFmpeg developers`.
ffprobe: `ffprobe version n9.0.2-22-g46d8f462ee-20261006 Copyright (c) 2007-2026 the FFmpeg developers`.
Build: `built with gcc 16.2.0 (crosstool-NG 1.29.0.7_b1a94f6)`.

전체 version/build/config/library 문자열과 capability evidence는
[generator.lock.json](../../canonical_assets/first-package-candidate-v1/generator.lock.json)에 보존했습니다.
TOOLCHAIN_READY 후에만 실제 생성했습니다. 다른 Downloads ZIP은 사용하지 않았습니다.
사용자 지정 ZIP 다운로드는 환경 준비이며 generator 자체에는 network/downloader가 없습니다.

실제 실행:

```powershell
$python311 = "C:UsershelljAppDataLocalProgramsPythonPython311python.exe"
$toolBin = "C:Tools
fmpeg-n9.0.2-22-g46d8f462ee
fmpeg-n9.0.2-22-g46d8f462ee-win64-gpl-9.0in"
& $python311 -m tools.canonical_assets.generate verify-reproducible --ffmpeg "$toolBin
fmpeg.exe" --ffprobe "$toolBin
fprobe.exe" --workspace "C:UsershelljProjectsedit-program-canonical	ask022-run-8f57179" --sealed-destination "C:UsershelljProjectsedit-program-canonicalsealedcanonical-fixture-assets-1.0.0"
```

### Exact command recipes

실제 lock의 고정 token arrays입니다. `$FFMPEG` / `$FFPROBE`는 위 실행 파일,
`$STAGING`은 각 independent run root입니다. Shell 문자열이 아닌 normalized recipe 표시입니다.
Video-only는 validated MOV, audio-only는 직접 생성한 WAV를 사용합니다.

```text
audio_decode: ["$FFMPEG","-hide_banner","-loglevel","error","-nostdin","-n","-xerror","-i","$STAGING/package/assets/output.mov","-map","0:a:0","-c:a","pcm_s24le","-flags:a","+bitexact","-f","s24le","pipe:1"]
encode: ["$FFMPEG","-hide_banner","-loglevel","error","-nostdin","-n","-xerror","-f","rawvideo","-pixel_format","rgb24","-video_size","1280x720","-framerate","24/1","-i","pipe:0","-map","0:v:0","-an","-c:v","dnxhd","-profile:v","dnxhr_lb","-pix_fmt","yuv422p","-frames:v","720","-r","24/1","-enc_time_base","1:24","-threads","1","-filter_threads","1","-vf","scale=in_range=full:out_range=limited:out_color_matrix=bt709,setsar=1","-color_primaries","bt709","-color_trc","bt709","-colorspace","bt709","-color_range","tv","-map_metadata","-1","-map_chapters","-1","-fflags","+bitexact","-flags:v","+bitexact","-metadata","creation_time=","-metadata","encoder=","-metadata:s:v","encoder=","-metadata:s:v","language=und","-write_tmcd","0","-f","mov","$STAGING/work/video.mov"]
frames: ["$FFPROBE","-v","error","-select_streams","v:0","-show_frames","-show_entries","frame=media_type,width,height,interlaced_frame","-of","json","$STAGING/package/assets/output.mov"]
mux: ["$FFMPEG","-hide_banner","-loglevel","error","-nostdin","-n","-xerror","-i","$STAGING/work/video.mov","-i","$STAGING/work/audio.wav","-map","0:v:0","-map","1:a:0","-c:v","copy","-c:a","copy","-map_metadata","-1","-map_chapters","-1","-fflags","+bitexact","-flags:v","+bitexact","-metadata","creation_time=","-metadata","encoder=","-metadata:s:v","encoder=","-metadata:s:v","language=und","-write_tmcd","0","-metadata:s:a","language=und","-f","mov","$STAGING/package/assets/output.mov"]
structure: ["$FFPROBE","-v","error","-show_streams","-show_format","-of","json","$STAGING/package/assets/output.mov"]
video_decode: ["$FFMPEG","-hide_banner","-loglevel","error","-nostdin","-n","-xerror","-i","$STAGING/package/assets/output.mov","-map","0:v:0","-an","-fps_mode","passthrough","-f","null","-"]
```

### Actual full generation / validation

| 검증 | Run A | Run B |
| --- | --- | --- |
| Six assets full generation | PASS | PASS |
| 4 A/V: exactly 1 video + 1 audio | PASS | PASS |
| VIDEO_ONLY 1 video / 0 audio; AUDIO_ONLY 0 video / 1 audio | PASS | PASS |
| DNxHR LB / 1280×720 / yuv422p / 24/1 / progressive | PASS | PASS |
| Each video: zero-error full decode, 720 frames, all 1280×720/non-interlaced | PASS | PASS |
| Final MOV PCM decode == source PCM; 48k/24-bit/stereo; 1,440,000 samples/channel | PASS | PASS |
| AUDIO_ONLY WAV data == source PCM; 8,640,000 PCM bytes | PASS | PASS |
| Source RGB/PCM digest revalidation before seal | PASS | PASS |
| Canonical metadata/checksums and real digest | PASS | PASS |

Fresh directories:

- Run A: `C:\Users\hellj\Projects\edit-program-canonical\task022-run-8f57179\run-a\package`
- Run B: `C:\Users\hellj\Projects\edit-program-canonical\task022-run-8f57179\run-b\package`

**9 / 9 authoritative files exact byte equality PASS**, including six assets, manifest, generator lock and checksums.
[Comparison evidence](../../canonical_assets/first-package-candidate-v1/comparison-report.json).
Sealing returned **SEALED**, process exit code **0**. Semantic equivalence was not substituted.
Earlier failed staging directories were not reused.

### Real package hashes

| Relative package path | SHA-256 |
| --- | --- |
| assets/alpha_v1.mov | `67910939447e396ef0ce17d79d4303d223f20ca61b81337b034dfa8121d4d323` |
| assets/audio_only_v1.wav | `f82f9cdeb70e7ef34f7bfb07158708549593e56bb73a1add6a5d5155c1692e9b` |
| assets/beta_v1.mov | `fdbf8c87dfd1c1dcdf6e702e3da99565eef9e7c64a2cfeded60b5100843de13a` |
| assets/gamma_v1.mov | `ec0fea668d05116d6429fcf8c982bd07aad3f64164cbcabffa5c8e59258a1f93` |
| assets/repeat_v1.mov | `2b76b4102e1b8de3f838b1fb19a0d9dd4181be85e1ec9af7c2624f950c00488f` |
| assets/video_only_v1.mov | `51109edb40573bcf98c1373dae2e049c81da99db44186841779075624d650137` |
| generator.lock.json | `846ebb969c1ef54d89bd44e82f23b9e1ce075f433fdb38aee117f0f15e68f0a7` |
| manifest.v1.json | `8ccfe25399f35c9d49c63e30efd0ef2ac0c75a0c34dc615ef1687e2b7645e499` |

`package_digest = SHA256(exact checksums.sha256 bytes)`:

```text
17b5b007df4f328a414505e68b395bab4f466b72a207e93a4f006595cbc375de
```

Package: `canonical-fixture-assets` / `1.0.0`. Catalog, ADR-036/037 and recipe: `v1`.

Local sealed location:
`C:\Users\hellj\Projects\edit-program-canonical\sealed\canonical-fixture-assets-1.0.0`.

[Package-index candidate](../../canonical_assets/first-package-candidate-v1/package-index.candidate.json):
actual six asset IDs/hashes, manifest/lock hashes and digest; `chat_approval = pending`;
`publication_reference = null`. No fake release URL or media Git blob.

### Safety Gate

| Invariant | 결과 | 근거와 범위 |
| --- | --- | --- |
| Wrong target edit | domain regression PASS; native 미검증 | Resolve lookup/mutation 없음 |
| Protected range violation | domain regression PASS; native 미검증 | safety/executor 변경 없음 |
| Silent timeline damage | domain regression PASS; native 미검증 | synthetic tooling only |
| A/V sync regression | domain regression PASS; native 미검증 | generated frames/PCM exact 검증; Resolve sync qualification 아님 |
| Failed rollback | 해당 없음; existing domain regression PASS | Undo/rollback 구현·호출 없음 |

## 4. 구현 과정에서 발견한 설계 문제

Architecture 변경은 필요하지 않았습니다. 실제 toolchain의 세 차이를 fail-closed로 재현하고 보완했습니다.

1. DNxHR stream `field_order` 누락: missing만으로 progressive를 가정하지 않습니다.
   720 decoded frames가 모두 명시적 `interlaced_frame=0`일 때만 검증합니다.
   상충하는 stream metadata는 계속 reject합니다.
2. FFmpeg 9의 `-vsync` 제거: fixed decode recipe를 `-fps_mode passthrough`로 기록했습니다.
   Codec/profile/encode fallback이 아닙니다.
3. PCM WAV `channel_layout` 누락: exact canonical PCM stereo WAV header/data 증거를 검증합니다.
   Invalid header, missing evidence, 명시적 mono contradiction은 reject합니다.

각 실패에서 STRUCTURE_MISMATCH / FRAME_COUNT_MISMATCH로 중단했고 incomplete package를 봉인하지 않았습니다.
계약의 pixel/PCM algorithm이나 profile을 encode 결과에 맞춰 변경하지 않았습니다.

## 5. DECISIONS.md OPEN

- **OPEN-021 유지**: actual generation, hashes, two-run equality와 local seal은 완료.
  First-package Chat Gate 승인과 이후 binary publication/storage 결정은 남았습니다.
- RESOLVED FOR FIRST PACKAGE GENERATION으로 변경하지 않았습니다.
- **OPEN-020 변경 없음**. Native registration authenticity를 주장하지 않습니다.
- 새로운 architecture OPEN은 없습니다. Toolchain 차이는 explicit validation evidence로 처리했습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- Toolchain 부재와 actual media 미생성 한계는 해소했습니다.
- 재현성은 exact locked Windows toolchain의 두 clean run에서 확인한 범위이며 cross-build/OS 보장이 아닙니다.
- Sealing은 local cooperative reservation과 collision 검사입니다. Hostile filesystem modification 방어나
  OS 수준 immutable storage를 주장하지 않습니다.
- Binary publication/release는 수행하지 않았습니다. Local sealed evidence와 작은 metadata만 PR에 포함합니다.
- Resolve import/read/materialization은 미검증입니다. Generator 성공은 Resolve support가 아닙니다.

## 7. ADR-036/037과 다르게 구현한 부분

의미를 변경한 deviation은 없습니다. Recipe에 고정하도록 허용한 glyph bitmap, one-cell spacing,
endpoint-inclusive ramp denominator 239를 명시했습니다.
Missing metadata의 explicit frame/WAV proof와 현재 passthrough 문법 사용은 위에 기록했습니다.
System font, float trig, random, resampling, codec/profile/raster fallback, arbitrary flags는 없습니다.
Chat Gate 전 publication은 하지 않았습니다.

## 8. 다음 TASK 제안

TASK-022 first-package Chat Gate를 마치고 승인된 digest의 보관/publication 경로를 확정하는 것을 권장합니다.
이후 별도 승인 시 TASK-020 read-only Resolve Adapter runtime validation에서 import/read qualification을 검토합니다.
TASK-020/021은 착수하지 않았습니다. 이 제안은 다음 구현 승인을 대신하지 않습니다.

## 9. Chat 검토란

- 판정: **Chat 작성 대기**.
- 요청: TASK-022 generator, exact toolchain, actual binaries/hashes, A/B determinism 및 package index의 Chat Gate Review.
- 승인 전 OPEN-021 resolution, merge, release/publication 없음.
- TASK-020/021 자동 착수 없음.
