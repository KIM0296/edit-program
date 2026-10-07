# TASK 완료 보고서 — 부분 구현 / HOLD

TASK: TASK-022 — Canonical Asset Generator & First Package Build
상태: **IN PROGRESS / TOOLCHAIN_UNSUPPORTED. TASK 완료 및 first-package acceptance 아님.**
브랜치: `feat/task-022-canonical-asset-generator`.
Base main: `7659aabe7dbb6a18ac4b1b940b809e08c424eef9`.
Spec notes: `b50da5f`, red-first: `47a8bbf`, 구현: `5f94f3f`, binding 보강: `b5870ce`.
최종 head / CI 근거는 Draft PR 본문에 기록합니다.
PR: [#48](https://github.com/KIM0296/edit-program/pull/48) — Draft 유지.
근거: ADR-034/036/037 및 [TASK-022 spec](../../tasks/TASK_022_CANONICAL_ASSET_GENERATOR_FIRST_PACKAGE.md).
요청 Gate: **HOLD** — 실제 full generation과 Run A/B 검증 전에는 APPROVED를 요청하지 않습니다.

## 1. 구현 내용

- `tools/canonical_assets`에 production adapter와 분리된 engineering tooling을 구현했습니다.
- 1280×720 RGB24, 720 frame의 integer pattern, embedded 5×7 glyph, frame/binary/second counter,
  moving bar, 지정 background/border를 생성합니다. 시스템 font나 antialiasing을 사용하지 않습니다.
- 48k/stereo/24-bit, 1,440,000 sample/channel의 integer triangle/envelope, signed 24-bit LE packing과
  deterministic RIFF/WAVE writer를 구현했습니다. Literal sample/pixel golden tests가 있습니다.
- Python 3.11 / NumPy 2.3.5 / 명시적 FFmpeg·ffprobe 경로를 요구하는 preflight와 frozen profile을 추가했습니다.
  실제 executable hash와 capability/build evidence를 기록하도록 구현했지만 이번 환경에서는 확보하지 못했습니다.
- DNxHR LB encode/PCM stream-copy mux의 closed token builders, observed stream parser, frame count/raster,
  full video decode 및 PCM exact decode 비교 경로를 구현했습니다. 실제 FFmpeg 실행 검증은 미완료입니다.
- Canonical manifest/lock/checksum writer, safe paths, 정확한 9개 파일 A/B byte 비교와 collision-safe sealing을
  구현했습니다. Sealing은 실제 media 검증과 exact lock/toolchain binding을 요구합니다.
- Generator CLI는 두 개의 fresh staging run 후 local sealing 및 작은 index candidate를 작성하도록 구현했습니다.
  현재 toolchain preflight에서 중단되므로 이 경로의 실제 성공을 주장하지 않습니다.

## 2. 변경된 파일

| 파일/영역 | 변경 목적 |
| --- | --- |
| tools/canonical_assets/{model,glyphs_5x7,video_pattern,audio_pattern,wav}.py | fixed recipe / integer source / WAV |
| tools/canonical_assets/{ffmpeg,validate}.py | typed preflight / recipes / observed structure and decode validation |
| tools/canonical_assets/{checksums,manifest,package,generate}.py | serialization / hashing / A/B comparison / sealing / explicit CLI |
| tools/canonical_assets/recipe.v1.json, README.md, __init__.py; tools/__init__.py | locked source recipe, usage, tooling package |
| tests/test_canonical_patterns.py, test_canonical_tooling.py, test_canonical_package.py | red-first 및 65개 신규 테스트 |
| pyproject.toml, .github/workflows/ci.yml | NumPy 2.3.5 pin, tools strict mypy/lint 범위 |
| .gitignore, .gitattributes | media 제외 및 recipe LF |
| task spec / DECISIONS / IMPLEMENTATION_STATUS / KNOWN_LIMITATIONS / TEST_MATRIX / 이 보고서 | 상태 및 미완료 근거 |

### git diff --stat

비교 기준: `40b27c2`. 시작 base는 `7659aab`이며, 이후 추가된 native 환경 계약 문서만 동기화했습니다.

```text
 .gitattributes                                     |   2 +
 .github/workflows/ci.yml                           |   2 +-
 .gitignore                                         |   6 +
 DECISIONS.md                                       |  11 +-
 IMPLEMENTATION_STATUS.md                           |  14 +
 KNOWN_LIMITATIONS.md                               |  15 +
 docs/TEST_MATRIX.md                                |  19 ++
 docs/reports/TASK_022_COMPLETION.md                | 172 +++++++++++
 pyproject.toml                                     |   3 +-
 ..._022_CANONICAL_ASSET_GENERATOR_FIRST_PACKAGE.md |  13 +-
 tests/test_canonical_package.py                    | 197 ++++++++++++
 tests/test_canonical_patterns.py                   | 165 ++++++++++
 tests/test_canonical_tooling.py                    | 319 +++++++++++++++++++
 tools/__init__.py                                  |   1 +
 tools/canonical_assets/README.md                   |  39 +++
 tools/canonical_assets/__init__.py                 |   1 +
 tools/canonical_assets/audio_pattern.py            |  59 ++++
 tools/canonical_assets/checksums.py                |  98 ++++++
 tools/canonical_assets/ffmpeg.py                   | 274 ++++++++++++++++
 tools/canonical_assets/generate.py                 | 104 +++++++
 tools/canonical_assets/glyphs_5x7.py               |  26 ++
 tools/canonical_assets/manifest.py                 | 211 +++++++++++++
 tools/canonical_assets/model.py                    |  69 +++++
 tools/canonical_assets/package.py                  | 344 +++++++++++++++++++++
 tools/canonical_assets/recipe.v1.json              |   1 +
 tools/canonical_assets/validate.py                 | 158 ++++++++++
 tools/canonical_assets/video_pattern.py            |  65 ++++
 tools/canonical_assets/wav.py                      |  23 ++
 28 files changed, 2407 insertions(+), 4 deletions(-)
```

## 3. 테스트 결과

- 로컬: Windows, Python **3.14.6**, NumPy **2.3.5**. 이것은 unit 환경이며 canonical generation 환경이 아닙니다.
- 신규: **64 passed / 1 skipped**. 전체: **1411 passed / 2 skipped**.
- Skip: Windows symlink 생성 권한 1개, 기존 naive INV-001 opt-in red demo 1개.
- Ruff: PASS. Strict mypy: PASS, **33 files** (generator tooling 포함).
- Python 3.11.16 CI: [run 37584653152](https://github.com/KIM0296/edit-program/actions/runs/37584653152) **1412 passed / 1 skipped**, Ruff / strict mypy PASS.
  Linux CI에서는 symlink 테스트도 통과했습니다. 최종 head CI는 PR 본문 참조. 실제 FFmpeg generation은 CI에서도 실행하지 않았습니다.
- Red-first: module 없음 실패를 먼저 확인했고 이후 metadata contradiction / binding 실패도 추가 재현했습니다.

### Toolchain / 실제 generation 상태

| 항목 | 실제 확인 결과 |
| --- | --- |
| Python 3.11 generation interpreter | 확인되지 않음. 확인된 다른 interpreter는 3.12.14 / 3.13.15 / 3.14.6 |
| NumPy | 로컬 unit 환경 2.3.5 |
| FFmpeg version/build/config/executable SHA-256 | 미확보 — 경로 미확인, 실행하지 않음 |
| ffprobe version/executable SHA-256 | 미확보 — 경로 미확인, 실행하지 않음 |
| 실제 preflight | local Python 3.14에서 TOOLCHAIN_UNSUPPORTED 반환; generation 폴더/미디어 생성 전 중단 |
| full six-asset build / full decode | 미실행 |
| Run A/B exact equality | 미실행 |
| sealed package location | 없음 |
| package-index candidate | 없음; 실제 binary hash 없이는 생성하지 않음 |
| publication/storage reference | 없음 |

실제 명령 recipe는 `encode_tokens`, `mux_tokens`, `probe_tokens`, `decode_tokens`와 README에 있습니다.
실행된 canonical encode/mux 명령은 **없습니다**. 첫 successful run에서 exact normalized token arrays를
`generator.lock.json`에 기록해야 합니다. 현재 코드에는 fallback이나 arbitrary extra flags 인터페이스가 없습니다.
FFmpeg 명령 의미 참고: [공식 CLI 문서](https://ffmpeg.org/ffmpeg.html),
[공식 format 문서](https://ffmpeg.org/ffmpeg-formats.html). 설치된 build 검증을 대체하지 않습니다.

### 실제 package identity

| 예정 asset | 실제 SHA-256 |
| --- | --- |
| assets/alpha_v1.mov | 미생성 |
| assets/beta_v1.mov | 미생성 |
| assets/gamma_v1.mov | 미생성 |
| assets/repeat_v1.mov | 미생성 |
| assets/video_only_v1.mov | 미생성 |
| assets/audio_only_v1.wav | 미생성 |
| manifest.v1.json | 미생성 |
| generator.lock.json | 미생성 |
| package_digest | 미생성 |

Unit-test fake bytes의 hash를 canonical hash로 보고하지 않습니다. 실제 binary는 Git에 추가되지 않았습니다.

### Safety Gate

| Invariant | 결과 | 범위 |
| --- | --- | --- |
| Wrong target edit | 기존 domain 회귀 PASS; native 미검증 | Resolve/target lookup 호출 없음 |
| Protected range violation | 기존 domain 회귀 PASS; native 미검증 | 편집 기능 변경 없음 |
| Silent timeline damage | 기존 domain 회귀 PASS; native 미검증 | generator는 synthetic tooling만 수행 |
| A/V sync regression | 기존 domain 회귀 PASS; native 미검증 | 실제 A/V package 검증도 아직 미실행 |
| Failed rollback | 해당 없음; 기존 domain 회귀 PASS | Undo/rollback 구현·실행 없음 |

## 4. 구현 과정에서 발견한 설계 문제

현재의 차단 사유는 계약의 모호함이 아니라 필요한 생성 toolchain의 부재입니다.
Python 3.11/FFmpeg/ffprobe 경로를 사용자에게 요청했습니다. 자동 다운로드 금지 조건에 따라
다른 FFmpeg 설치나 codec/profile/raster fallback을 하지 않았습니다.
Unit 성공을 actual build 성공으로 간주할 수 없으므로 이번 제출은 Draft/HOLD입니다.

## 5. DECISIONS.md OPEN

OPEN-021의 generator implementation 진행만 기록하고 first package는 미완료로 유지했습니다.
실제 6개 binary, toolchain lock, real hashes, two-run equality, package index, Chat approval이 남았습니다.
OPEN-020 native registration authenticity는 변경하거나 해결하지 않았습니다.
새 Architecture Decision은 만들지 않았습니다.

## 6. KNOWN_LIMITATIONS.md

Toolchain availability, actual encode/mux/decode 미검증, 실제 hash/package/index 없음,
local cooperative sealing과 native 보장의 경계를 기록했습니다. Binary publication도 수행하지 않았습니다.

## 7. ADR-036/037 차이

Source 의미를 바꾸는 의도적 deviation은 없습니다. Recipe가 허용한 implementation detail인 glyph table,
one-cell 문자 간격, endpoint-inclusive ramp 분모 239를 고정했습니다.
다만 mandatory **실제 full generation / A/B acceptance가 충족되지 않았으므로 TASK는 미완료**입니다.
Unit 실행의 Python 3.14를 required generation Python 3.11의 대체로 취급하지 않았습니다.

## 8. 다음 단계

사용 가능한 Python 3.11, FFmpeg, ffprobe 실행 파일을 지정한 후 preflight를 다시 수행합니다.
검증된 toolchain으로 실제 두 full runs → 9개 파일 exact comparison → local seal → actual index/hash 보고를
완료해야 TASK-022 Chat Gate APPROVED를 요청할 수 있습니다. TASK-020/021은 착수하지 않습니다.

## 9. Chat 검토란

- 판정: Chat 작성 대기. 현재 제출 상태는 **HOLD / Draft**.
- 필수 잔여 작업: toolchain 확보 및 실제 first-package acceptance 전체.
- Merge / release / publication: 수행하지 않음.
- 다음 TASK: 자동 착수 없음.
