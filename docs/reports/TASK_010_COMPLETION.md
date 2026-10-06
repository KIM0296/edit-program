# TASK 완료 보고서

TASK: TASK-010 — Native Time & Snapshot Mapping Foundation

상태: 구현·로컬 검증 완료, Python 3.11 CI 및 Chat Gate 대기.
브랜치: `feat/task-010-native-time-mapping`.
Base main: `90bbe30d014436c1aa750114f526c3ae93ea5c6f`.
Spec/API notes: `5922433`, red tests: `a52d63b`, 구현: `0350554`.
후속 보고 commit은 문서 변경이며 최종 제출 head는 PR 본문에 기록합니다.

PR: 생성 후 기록.
근거: [TASK-010 spec](../../tasks/TASK_010_NATIVE_TIME_MAPPING.md),
[ADR-021 상세 계약](../NATIVE_TIME_SNAPSHOT_MAPPING.md).
요청 Gate: **APPROVED** (Codex 요청이며 Chat 판정 아님).

## 1. 구현 내용

명시적으로 공급된 placement correspondence를 양방향으로 검사하는 pure mapping을 구현했습니다.
FrameRate만으로 transform을 만들지 않으며, fractional boundary를 반올림하지 않습니다.

- Exact rational FrameRate는 양의 정수 numerator/denominator를 gcd로 canonicalize합니다.
  `30000/1001 != 30/1`을 유지합니다. 이 약분은 frame boundary rounding과 무관합니다.
- SourceFrameRange / TimelineFrameRange는 기존 integer half-open FrameRange의 서로 다른 wrapper입니다.
  같은 정수라도 의미가 다르며 binding/request에 잘못된 type을 넣으면 거절합니다.
- NativeSnapshotRef는 timeline ID/version/state token을 보유하고 실제 token 생성은 하지 않습니다.
- PlacementTemporalBinding은 opaque mapping ref, snapshot, placement/media, 두 span/rate 및 kind를 요구합니다.
- map_range는 요청 identity를 먼저 확인하고 한 concrete fragment의 explicit span으로만 계산합니다.
  Fraction은 내부 산술에만 사용하며 EXACT output은 integer FrameRange입니다.
- IDENTITY_1X는 explicit span 길이가 같아야 합니다. AFFINE_FORWARD의 slope는 두 span으로만 결정합니다.
- Source→Timeline 및 역방향 모두 start/end가 integral이어야 EXACT입니다. 실패 시 mapped pair는 없습니다.
- Snapshot mismatch는 STALE, unique binding 불가는 AMBIGUOUS, 범위 밖은 OUT_OF_RANGE,
  fractional boundary는 NON_INTEGRAL입니다. REVERSE/FREEZE/VARIABLE_RETIME/UNKNOWN은 lowering하지 않습니다.
- Raw request, current snapshot, candidate binding tuple을 결과에 보존합니다. EXACT만 선택 binding과
  완전한 source/timeline pair를 가집니다. Authority/approval/실행 진입점은 없습니다.

| Acceptance | 결과 및 근거 |
| --- | --- |
| Exact rational FPS / coordinate 분리 | PASS: canonicalization, NTSC distinction, invalid type/domain 거절 |
| Explicit identity/affine 양방향 | PASS: offset, ratio, inverse 및 full range |
| Mixed FPS exact/non-integral | PASS: 양쪽 endpoint 검사, fractional 출력 없음 |
| FPS-only mapping 금지 | PASS: binding 필수, rate 변경으로 mapping 산술 불변 |
| Snapshot binding / no rebase | PASS: 모든 snapshot 축, old+fresh 혼합도 STALE |
| Placement/media / fragment 구별 | PASS: repeated media, wrong ID, split boundary, overlap ambiguity, no union |
| Unsupported retime / no clamp | PASS: 4개 kind 및 한 frame 초과 range |
| Immutable / deterministic | PASS: frozen nested values, defensive tuple, permutation |
| No execution / evidence generation | PASS: monkeypatch와 pure import 경계 검사 |
| TASK-001~009 regression | PASS: 기존 source/test 변경 없음 |
| Python 3.11 CI | PR 생성 후 확인 예정 |
| Ruff / strict mypy | PASS: 12 source files |

Resolve API, SMPTE parser, native discovery, persistent ID 해결, media 분석, Evidence 생성,
StableTarget/EditPlan lowering, retime execution, DB/network/UI 및 TASK-011은 구현하지 않았습니다.

## 2. 변경된 파일

| 파일 | 목적 |
| --- | --- |
| src/davinci_ai_editor/temporal_mapping.py | Immutable mapping domain / pure 양방향 계산 |
| tests/test_temporal_mapping.py | 71개 red-first 및 회귀 테스트 |
| tasks/TASK_010_NATIVE_TIME_MAPPING.md | 기존 spec 유지, 사전 구현 notes 및 상태 |
| DECISIONS.md | 기존 OPEN에 TASK-010 적용 범위 기록 |
| IMPLEMENTATION_STATUS.md | 구현·검증 상태 |
| KNOWN_LIMITATIONS.md | Fake identity / caller snapshot / unsupported 범위 |
| docs/TEST_MATRIX.md | 요구별 검증 근거 |
| docs/reports/TASK_010_COMPLETION.md | 표준 보고서 |

### git diff --stat

위 base main 대비 제출 tree (보고서 포함):

```text
 DECISIONS.md                              |  12 +
 IMPLEMENTATION_STATUS.md                  |  21 ++
 KNOWN_LIMITATIONS.md                      |  30 ++
 docs/TEST_MATRIX.md                       |  24 ++
 docs/reports/TASK_010_COMPLETION.md       | 173 +++++++++++
 src/davinci_ai_editor/temporal_mapping.py | 322 +++++++++++++++++++++
 tasks/TASK_010_NATIVE_TIME_MAPPING.md     |  26 +-
 tests/test_temporal_mapping.py            | 464 ++++++++++++++++++++++++++++++
 8 files changed, 1071 insertions(+), 1 deletion(-)
```

## 3. 테스트 결과

환경: Windows, CPython 3.14.6, repository .venv. Resolve 미사용.

- Passed: 486개 (신규 TASK-010 71개), Ruff PASS, strict mypy PASS (12 files).
- Failed: 최종 로컬 검사 0개.
- Skipped: 1개 — test_naive_inv001.py의 opt-in intentional red demo. 일반 INV-001 회귀는 실행/PASS.
- CI: Python 3.11 PR run 대기.
- 미실행: 실제 Resolve/native token/mapping 정확성 및 retime/A/V/rollback 통합 검증. 범위 밖입니다.

Red-first: 신규 테스트를 source 작성 전에 실행하여 `davinci_ai_editor.temporal_mapping`이 없는
ModuleNotFoundError / collection error 1개를 확인하고 `a52d63b`로 commit했습니다.

```text
.venv\Scripts\python.exe -m pytest tests/test_temporal_mapping.py -q
  before source: 1 collection error (missing module)
.venv\Scripts\python.exe -m pytest -q
  486 passed, 1 skipped
.venv\Scripts\python.exe -m ruff check src tests
  All checks passed!
.venv\Scripts\python.exe -m mypy
  Success: no issues found in 12 source files
```

별도 산술 검증: source/timeline span 길이 1~8의 모든 비율과 모든 subrange를 양방향으로 순회하여
정수 divisibility oracle과 EXACT/NON_INTEGRAL을 대조하고 exact 결과는 inverse roundtrip을 검사합니다.
`10**30` origin도 검증해 float precision에 의존하지 않음을 확인했습니다.

### Safety Gate

| Invariant | 결과 | 검증 범위 |
| --- | --- | --- |
| Wrong target edit | PASS (fake domain) | INV-001 회귀, explicit identity/range 및 stale 차단; 실제 edit 없음 |
| Protected range violation | PASS (기존 fake 범위) | INV-003 회귀, 신규 mapper 실행 호출 없음 |
| Silent timeline damage | PASS (domain 범위) | INV-002/019 회귀, immutable raw input, no mutation 경계 |
| A/V sync regression | 미검증 (실행) | 기존 relationship foundation 회귀만 PASS |
| Failed rollback | 미검증 | transaction/rollback은 미구현 |

INV-007 retime safety 또는 전체 production P0 인증을 주장하지 않습니다.

## 4. 발견한 설계 문제

Opaque token과 explicit spans는 수학적 mapping 검증에 충분하지만 실제 native state와 correspondence의
진실성을 증명하지 않습니다. Caller가 오래된 current snapshot을 공급하는 것도 pure mapper 혼자 알 수 없습니다.
Native discovery/token 생성이나 persistent identity를 임의 구현하지 않았습니다.

같은 lineage에 여러 fragment가 있으므로 identity만으로 한 mapping을 선택할 수 없습니다.
요청 identity를 고정한 뒤 concrete span containment를 확인하고, unique하지 않으면 AMBIGUOUS입니다.
같은 media라는 이유로 다른 placement를 선택하거나 여러 fragment를 합치지 않습니다.

## 5. DECISIONS.md OPEN 항목

새로운 architecture 결정을 확정하지 않았습니다. 기존 **OPEN-001 / OPEN-006 / OPEN-008 / OPEN-012**에
TASK-010 적용 기록을 추가했습니다. OPEN-011의 v1 계약은 ADR-021로 해결된 상태를 유지합니다.

- 문제: production identity/correspondence, live state token realization, scope-aware reuse.
- 대안: FPS/filename/timecode로 추론하거나 explicit caller proof만 검증. 전자는 ADR-021 위반입니다.
- 권고: 후자를 유지하고 native runtime 검증은 별도 승인된 adapter 작업에 맡깁니다.
- Trade-off: 실제 Resolve truth/live freshness는 이번 결과로 보장할 수 없습니다.
- 의존 작업: production adapter 및 partial refresh. Pure foundation 완료를 막지는 않습니다.

## 6. KNOWN_LIMITATIONS.md 변경 사항

- Single supplied concrete segment만 lowering합니다. Unsupported kind를 1:1로 간주하지 않습니다.
- Unsupported FREEZE 등의 descriptor도 기존 nonempty FrameRange를 사용하며 완성된 retime 모델이 아닙니다.
- Missing binding은 UNSUPPORTED, identity mismatch/중복 mapping ref는 AMBIGUOUS입니다.
- Relevant binding이 하나라도 stale이면 최신 후보를 자동 선택하지 않고 STALE입니다.
- Containing span이 없고 여러 supplied span과 overlap하면 보수적 AMBIGUOUS, 그 외 OUT_OF_RANGE입니다.
- Exact result는 data contract이며 Safety/Authority permission이 아닙니다.
- 한계 해소에는 별도 approved native/runtime evidence가 필요합니다. No production quality claim.

## 7. Specification과 다르게 구현한 부분

승인된 의미·범위와의 차이 없음. 기존 spec을 교체하지 않고 구현 전 API notes를 추가했습니다.
좌표 type 명칭과 pure 함수 signature를 구체화했으며 Fraction은 mapper 내부에서만 사용합니다.
새 글로벌 시간 primitive, FPS 추론, rounding, silent rebase, production identity 정책은 없습니다.

## 8. 다음 TASK 제안

준비된 TASK-011 / ADR-022 Read-only Resolve Snapshot Contract를 다음 Chat Gate 이후 검토할 수 있습니다.
현재 main에 문서가 있다는 사실을 구현 승인으로 취급하지 않았습니다.
선행 검토: OPEN-012 runtime capability/state identity realization 및 명시된 adapter 경계.
Acceptance 초안은 준비된 TASK-011 spec을 기준으로 별도 승인합니다. **TASK-011 미착수**.

## 9. Chat 검토란

- 요청: TASK-010 Chat Gate Review / APPROVED.
- 판정: Chat 작성 대기.
- 필수 수정·재검증: Chat 판정 후 반영.
- 다음 TASK / 병행 범위: 미승인.
- 승인 기록: 없음. PR merge하지 않음.
