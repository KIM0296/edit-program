# TASK 완료 보고서

TASK: TASK-020 — Read-only Probe Adapter + Runtime Qualification
상태: **Phase A 구현 완료 / Phase B 미완료 / 전체 HOLD 요청**
브랜치: `feat/task-020-read-only-probe-adapter`
Base main: `98bffaf204b1ee94636213ea9cd60bf7dfa45b75`
구현 commit: `4d223ee`; 추가 경계 검증 및 최종 runtime 진단 기준: `858cc48`.
최종 제출 head / PR 링크 / CI는 PR 본문에 기록합니다.
근거: ADR-022/029/030/031/032/033/034/038/039 및 TASK-020 authoritative 문서.
요청 Gate: **HOLD**. Phase A 코드 검토와 Phase B runtime HOLD를 분리 요청합니다.
이는 Codex의 요청이며 Chat 판정이 아닙니다.

## 1. 구현 내용

설치된 Developer README와 `DaVinciResolveScript.pyi`를 코드 작성 전에 조사했습니다.
파일 버전 **21.1.1.10**은 실제 실행 중인 Resolve build 관측과 구분합니다.
실제 bridge 연결은 수행했으나 Resolve root가 없어 runtime build는 UNKNOWN입니다.

- 고정 read allowlist를 가진 실제 vendor bridge adapter와 explicit CLI를 추가했습니다.
  프로젝트/타임라인 활성화, 설정 변경, import, materialization, mutation은 없습니다.
- immutable raw type/value/error와 semantic 값을 분리했습니다. None/False/empty 구분,
  float/bool frame 거부, native ordering의 제한적 정렬, repeated-media placement 유지.
- fresh Resolve→ProjectManager→Project→Timeline root 재획득과 capture 전후 fence를 기록합니다.
  profile/library/project/timeline mismatch를 fixture enumeration 전에 차단합니다.
- 명시적 package/MPI/coordinate evidence와 catalog tuple로 role을 유일하게 bind합니다.
  first-match/filename/media-only fallback은 없습니다. F3 marker host도 explicit input입니다.
- 고정 10-pair S1, 외부 operator switch 기반 3-round F4 S2를 mock으로 검증했습니다.
  drift/실패/간섭 기록을 유지하고 반복 재시도로 qualification을 얻지 않습니다.
- capture 파일, per-pair/round result, RV-001..044, raw/semantic/report/checksum을 씁니다.
  봉인 전 누락/변경 파일을 거부하며 새 run만 허용합니다. 체크섬은 native authenticity가 아닙니다.
- capability stability와 fixture correctness는 별도입니다. 안정적인 잘못된 값은 fixture MISMATCH이며,
  missing/unknown 정보나 Tier C 위험은 safe/absent로 바꾸지 않습니다.

Phase B는 **미실행**입니다. 승인 package digest는 변경하지 않았습니다:
`17b5b007df4f328a414505e68b395bab4f466b72a207e93a4f006595cbc375de`.
준비된 registered F0–F4 입력이 없고 실제 연결에서 root가 없었습니다.
S1 **0/120** complete captures, F4 S2 **0/3**, S3/S4 미실행입니다.

## 2. 변경된 파일

| 파일 | 목적 |
| --- | --- |
| src/davinci_ai_editor/resolve_probe/ | typed evidence, installed read-only adapter, fixtures, protocol runner, writer, CLI |
| tests/read_probe_fakes.py | native read-only mock surface / catalog fixtures |
| tests/test_read_probe_values.py | immutability, types, shape, capability axes |
| tests/test_read_probe_adapter.py | read boundary, binding, fixture correctness, normalization |
| tests/test_read_probe_runner.py | S1/S2, drift retention, sealing, discovery report |
| docs/evidence/task020-installed/api_inventory.json | installed docs/stub signatures/hash/file-version discovery |
| docs/evidence/task020-runtime/ | two unchanged sealed real diagnostic attempts, no fixture captures |
| docs/TASK_020_ADAPTER_USAGE.md | prerequisites, closed config schema, CLI and limits |
| .gitattributes | preserve committed evidence bytes/checksums |
| tasks/TASK_020_READ_ONLY_PROBE_ADAPTER.md | implementation notes and Phase A/B status |
| DECISIONS.md / KNOWN_LIMITATIONS.md | OPEN-023 and unverified native boundaries |
| IMPLEMENTATION_STATUS.md / docs/TEST_MATRIX.md | status, requirement/test mapping |
| docs/reports/TASK_020_COMPLETION.md | this report |

### git diff --stat

Actual submission snapshot against base main is appended below; final documentation-only head is
identified in the PR. No large media or canonical package binary changed.

## 3. 테스트 결과

Windows / external **Python 3.11.9**. Installed Resolve file **21.1.1.10**; running product/build **UNKNOWN**.

- 신규 unit/mock: **55 passed**.
- 전체 Python 3.11: **1472 passed, 0 failed, 2 skipped** (15.82 seconds).
- Ruff: PASS. strict mypy: PASS, 44 source files.
- Python 3.11 CI: 제출 PR의 workflow 결과로 별도 확인합니다. 아래 native 결과와 혼동하지 않습니다.
- skip: Windows symlink 생성 권한 없음 1개, opt-in naive INV-001 intentional red demo 1개.
  실제 INV-001 회귀는 실행/통과했습니다.
- red-first: missing-module 실패 및 잘못된 timeline end/F0 links/F3 host/mutable evidence/
  누락된 capture 파일 봉인 문제를 실제 실패로 재현하고 수정했습니다.

```powershell
& 'C:\Users\hellj\AppData\Local\Programs\Python\Python311\python.exe' -m pytest -q --basetemp C:\Users\hellj\Projects\edit-program-canonical\pytest-task020-final-20261007 -p no:cacheprovider
.venv\Scripts\python.exe -m ruff check src tests tools
.venv\Scripts\python.exe -m mypy
```

### 실제 연결 / runtime evidence

1. Installed ResolvePython로 CLI 실행: repository module import 실패. Resolve read 이전의 환경 실패이며
   installed interpreter 설정을 변경하지 않았습니다. native capture로 계산하지 않습니다.
2. 외부 Python 3.11 / `4d223ee`: 공식 bridge 로딩 후 root 없음. RUNTIME_UNAVAILABLE, sealed diagnostic 보존.
3. 외부 Python 3.11 / `858cc48`: 최종 report writer로 독립 diagnostic. root 없음, RUNTIME_UNAVAILABLE.
   qualifying pair 재시도가 아니며 두 실패 기록을 모두 보존합니다.

최종 diagnostic run: `task020-discovery-py311-858cc48`.
UTC: `2026-10-07T09:24:57.434542+00:00`.
Adapter fingerprint: `sha256:a6ed646390ebaab0cbb350e3eed7baac6639836903909584f5e4c35d14469bd7`.
Root 부재로 product/version/version-string reads는 OBJECT_UNAVAILABLE이며 실제 native 값이 아닙니다.
RuntimeProfile/project generation은 없는 그대로 기록했고 가짜 qualification binding을 만들지 않았습니다.

[실제 runtime report](../evidence/task020-runtime/task020-discovery-py311-858cc48/summary/TASK_020_RUNTIME_REPORT.md)
및 [raw observations](../evidence/task020-runtime/task020-discovery-py311-858cc48/connection-observations.raw.json).
모든 RV **UNKNOWN**, 여섯 S1 표 모두 NOT_EXECUTED, S2 세 round 모두 NOT_EXECUTED.
복사한 두 evidence bundle의 exact SHA-256 inventory 검증 PASS.

### Safety Gate

| Invariant | 결과 | 근거 / 범위 |
| --- | --- | --- |
| Wrong target edit | domain/mock PASS; native 미검증 | 정확한 binding / ambiguity 차단; 실제 edit 없음 |
| Protected range violation | 기존 회귀 PASS; native 미검증 | mutation / Safety 실행 없음 |
| Silent timeline damage | domain/mock PASS; native 미검증 | read-only 표면, drift/unknown 보존; native qualification 미실행 |
| A/V sync regression | 기존 회귀 PASS; native 미검증 | linked reads만 수행하도록 구현; 이동/정렬 없음 |
| Failed rollback | 기존 회귀 PASS; native 미검증 | Undo/rollback 호출 없음 |

## 4. 구현 과정에서 발견한 설계 문제

ADR-034는 F0–F3를 별도 project로 정의하지만 ADR-038은 run을 단일 project generation에 bind합니다.
전체 F0–F4를 묶는 parent campaign identity/aggregation 계약은 명시되지 않았습니다.
별도 run을 하나의 generation으로 합치지 않고 전체 gate를 HOLD로 유지했습니다.

Installed stub은 item frame getter에 float annotation을 사용합니다. False mode의 실제 반환과
source/end convention은 아직 증명되지 않았습니다. 숫자 변환 없이 UNKNOWN으로 보존합니다.
F3 item marker HOST의 video/audio 선택도 caller의 explicit identity를 요구합니다.

## 5. DECISIONS.md에 추가한 OPEN 항목

**OPEN-023 — cross-project qualification report grouping**.
권고: 개별 sealed run의 binding을 유지하고 별도 reviewed aggregate가 refs만 모으도록 계약 확정.
장점은 원래 generation/currentness 증거 유지, 비용은 aggregate schema와 validation 추가입니다.
승인 전에는 aggregate PASS를 구현하지 않았습니다.
OPEN-019/011 endpoint/shape 질문과 OPEN-020 native authenticity 한계도 유지합니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

실제 runtime unavailable, fixture 부재, atomic snapshot 보장 없음, operator interference 완전 탐지 불가,
external package/MPI/coordinate/registration evidence 필요, F3 explicit host, Tier C unknown,
opaque native handles, OPEN-023, S3/S4 미실행, native attestation/permission 미생성을 기록했습니다.

## 7. Specification과 다르게 구현한 부분

Phase B 필수 runtime qualification을 완료하지 못했습니다. 테스트로 대체하지 않았으며 **미충족**입니다.
OPEN-023 해결 전 전체 completion gate는 HOLD입니다. 이는 승인된 aggregate 정책이 아니라 fail-closed 보류입니다.
실제 runtime behavior/Resolve support/production identity에 대한 새로운 보장은 없습니다.
Read-only/금지 범위에 대한 의도적 예외는 없습니다.

## 8. 다음 TASK 제안

다음 TASK로 넘어가지 말고 **TASK-020 Phase B 재개**를 권고합니다.
선행 조건: 외부에서 준비된 approved-package disposable F0–F4와 정확한 등록/role/coordinate evidence,
실행 중이며 scripting 접근 가능한 Resolve, OPEN-023 Chat 결정.
이후 S1 120 captures, F4 S2 3 rounds, RV-001..044를 실제 근거로 분류해 재검토합니다.
TASK-021은 미착수이며 이번 보고서는 fixture materialization 승인 요청이 아닙니다.

## 9. Chat 검토란

- 요청: Phase A 코드 검토 + Phase B **HOLD**.
- 판정: Chat 작성 대기.
- 필수 확인: OPEN-023 aggregate 계약과 외부 fixture 준비 상태.
- 다음 TASK / 병행 허용 범위: 없음. merge 및 TASK-021 시작하지 않음.

### 제출 diff snapshot

```text
 .gitattributes                                     |   1 +
 DECISIONS.md                                       |  21 ++
 IMPLEMENTATION_STATUS.md                           |  15 +
 KNOWN_LIMITATIONS.md                               |  21 ++
 docs/TASK_020_ADAPTER_USAGE.md                     |  78 +++++
 docs/TEST_MATRIX.md                                |  24 ++
 docs/evidence/task020-installed/api_inventory.json | 378 ++++++++++++++++++++
 .../connection-observations.raw.json               |   1 +
 .../evidence.sha256                                |   4 +
 .../installed_api/api_inventory.json               |   1 +
 .../task020-discovery-py311-4d223ee/run.json       |   1 +
 .../summary/TASK_020_RUNTIME_REPORT.md             |  59 ++++
 .../connection-observations.raw.json               |   1 +
 .../environment/currentness_preflight.json         |   1 +
 .../evidence.sha256                                |  13 +
 .../findings/findings.json                         |   1 +
 .../fixtures/F0_BASIC/fixture-summary.json         |   1 +
 .../F1_REPEATED_MEDIA/fixture-summary.json         |   1 +
 .../fixtures/F2_TRACK_STATE/fixture-summary.json   |   1 +
 .../F3_MARKER_SUBTITLE/fixture-summary.json        |   1 +
 .../timeline-A/fixture-summary.json                |   1 +
 .../timeline-B/fixture-summary.json                |   1 +
 .../installed_api/api_inventory.json               |   1 +
 .../task020-discovery-py311-858cc48/run.json       |   1 +
 .../runtime_profile.json                           |   1 +
 .../summary/TASK_020_RUNTIME_REPORT.md             | 161 +++++++++
 docs/reports/TASK_020_COMPLETION.md                | 158 +++++++++
 src/davinci_ai_editor/resolve_probe/__init__.py    |   1 +
 src/davinci_ai_editor/resolve_probe/__main__.py    | 384 +++++++++++++++++++++
 src/davinci_ai_editor/resolve_probe/adapter.py     | 306 ++++++++++++++++
 src/davinci_ai_editor/resolve_probe/connection.py  |  24 ++
 src/davinci_ai_editor/resolve_probe/fixtures.py    | 380 ++++++++++++++++++++
 src/davinci_ai_editor/resolve_probe/model.py       | 215 ++++++++++++
 .../resolve_probe/qualification.py                 | 181 ++++++++++
 src/davinci_ai_editor/resolve_probe/runner.py      | 219 ++++++++++++
 src/davinci_ai_editor/resolve_probe/surface.py     | 142 ++++++++
 src/davinci_ai_editor/resolve_probe/values.py      |  89 +++++
 src/davinci_ai_editor/resolve_probe/writer.py      | 309 +++++++++++++++++
 tasks/TASK_020_READ_ONLY_PROBE_ADAPTER.md          |  18 +-
 tests/read_probe_fakes.py                          | 163 +++++++++
 tests/test_read_probe_adapter.py                   | 295 ++++++++++++++++
 tests/test_read_probe_runner.py                    | 203 +++++++++++
 tests/test_read_probe_values.py                    | 107 ++++++
 43 files changed, 3983 insertions(+), 1 deletion(-)
```
