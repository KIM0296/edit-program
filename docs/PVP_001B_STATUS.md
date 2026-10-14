# PVP-001B — PRE-G2 harness implementation

## Verdict and qualification

PRE-G2 local implementation/validation complete; **TEST_ONLY_SUPPORT**.
G1 was confirmed separately. **Actual G2 acquisition and real-data G3–G6 remain
HOLD / NOT_RUN.** This document is not a G2, G3, G4, G5 or G6 PASS receipt.
No real recordings, PCM, annotation originals, validation set or holdout were opened.
No threshold is recommended or promoted by synthetic results. G7 belongs to Chat Gate.

The PRE-G2 harness is submitted for independent Chat Gate code review only.
Commit/push/PR are authorized; merge and real-data execution are not.
G2, G3, G4 real-data validation, G5, G6 and G7 all remain HOLD / NOT_PERFORMED.

## G1 baseline receipt

- Authoritative main: `0e727cb16af5538cc2bff977e4a495c603571699`.
- Tree: `0c133f4b74fa152e9efa942acc8a3d868bd3dabc`.
- PR #59 / PVP-001A merged; G1 accepted by the user.
- Main push CI: SUCCESS, [run 38510511770](https://github.com/KIM0296/edit-program/actions/runs/38510511770).
- Branch: `feature/pvp001b-pcm-calibration`.
- Worktree label: `edit-program-pvp001b` (personal local path omitted).
- Exact submission head SHA/tree and remote CI receipt are recorded in the PR.

## Exact changed-file allowlist

1. `tools/pcm_calibration.py`
2. `tests/test_pcm_calibration.py`
3. `tests/fixtures/pcm_calibration/README.md`
4. `tests/fixtures/pcm_calibration/receipt.schema.json`
5. `tests/fixtures/pcm_calibration/synthetic_receipt.json`
6. `docs/PVP_001B_STATUS.md`

No existing production module, dependency, test configuration, CI configuration,
classifier, Evidence, OBS, temporal mapping, TRUST, Safety or Authority contract changed.

## Implemented boundary

The module is an offline library, not an acquisition program or autonomous experiment
runner. Callers provide typed metadata and, for the pure producer adapter, an in-memory
buffer. It never reads a media file. The sole file-writing helper exclusively creates
a bounded TEST_ONLY_SUPPORT receipt and refuses overwrite.

| Contract / function | Purpose |
| --- | --- |
| `AcquisitionManifest`, `Extraction`, `validate_acquisition` | Audit permission/origin/channel metadata, timezone, exact origin/length, fixed original hashes, independent extraction and reviewer claims |
| `Session`, `Window`, `Split`, `Stratum`, `validate_splits` | Enforce bounded experiment allocation and detect declared original/take/derivative/channel-copy leakage and overlap |
| `Annotation`, `Region`, `Label`, `derive_truth` | Preserve both reviewers; derive only whole-frame agreed acoustic truth |
| `Counts`, `Rates`, `SessionScore`, `aggregate` | Exact integer confusion counts, micro, session macro and all four strata |
| `Interval`, `bootstrap_sessions` | Fixed-seed whole-session resampling, including N/A repetition counts |
| `Event`, `EventMetrics`, `match_events` | Maximum-total-IoU one-to-one matching and boundary/split/merge diagnostics |
| `Freeze`, `freeze_inputs` | Canonical split/annotation digests plus rubric/exclusion content digests and policy digest |
| `ConfigEvaluation`, `CalibrationReport`, `evaluate_calibration` | Retain all 40 evaluated configurations and apply the fixed selection rule |
| `evaluate_validation`, `HoldoutUse`, `audit_holdout_use`, `evaluate_holdout` | Exact selected-config gates and supplied-history misuse checks |
| `score_pcm_window` | Reuse the unchanged PVP producer / OBS path on caller-supplied buffers |
| `Reproduction`, `compare_reproduction` | Compare independently supplied original/PCM/channel/config/evidence/metrics/selection receipts |
| `Finding`, `Refusal`, `GateReceipt`, `receipt_json`, `write_receipt` | Machine-readable refusals, canonical bounded receipt schema and exclusive creation |

These types retain offline experiment inputs/results. They add no approval,
candidate, transaction, workflow or native timeline state machine.
Existing `AcousticConfig`, `PcmInput`, EvidenceRecord, OBS and `map_range()` remain
authoritative. The harness does not reimplement the detector or classifier.

## Exactness and annotation policy

- PCM16LE; selected channel explicit. `divmod(sample_rate * q, p)` must yield
  positive integer samples/frame and zero remainder. No rounding, resampling or repair.
- Acquisition metadata audits exact source/sample origins and byte counts. The pure
  scoring adapter accepts only the registered 48 kHz, 25/1, IDENTITY_1X profile.
  24/1 and 30/1 are tested for exact support, not independent measured examples.
- Annotation originals stay outside reports. Input schemas accept only quiet,
  activity and ambiguous acoustic labels, never editorial/semantic labels.
- Each reviewer must supply a complete, nonoverlapping partition of the window.
  Missing annotation is refused, not interpreted as activity.
- A frame is positive/negative only when wholly within both reviewers' matching
  quiet/activity regions. Boundary crossing and disagreement remain ambiguous.
  Explicit excluded intervals remain excluded; any intersecting frame is excluded.
- Confusion denominators omit ambiguous/excluded frames. Ambiguous percentage is
  `100 * ambiguous / (definite + ambiguous)`; excluded count is reported separately.
  `analyzed_seconds` reports the supplied window duration at the primary 25fps profile,
  including its ambiguous/excluded frames; it is not a claim of definite-label coverage.
- Empty denominators yield `None` / JSON null, never PASS. Session macro is N/A
  if any constituent session has an undefined rate; it does not silently drop sessions.
- Bootstrap seed `1001`, repetitions `1000`, 2.5/97.5 percentile nearest-rank endpoints.
  Resample whole sessions only. Undefined-rate draws are counted and omitted from
  endpoints; any resulting interval must be read with its valid/total draw counts.
- Event inputs must already be nonoverlapping, distinct, eligible acoustic runs
  from a frozen event/exclusion policy. The matcher does not invent reference runs
  from ambiguous annotation. IoU >= 1/2 is evaluation only. Optimize summed IoU;
  ties use start then stable ID. Signed errors are predicted minus reference.
  Absolute errors pool matched starts/ends; median, nearest-rank p95 and max are retained.
  Split/merge counts count reference/predicted events overlapping multiple other events.

## Calibration and one-shot contract

The fixed grid is thresholds `{0,16,64,256,1024,4096,16384,65536}` times minimum runs
`{1,2,3,5,10}`. Local timing uses radius 250 source frames, population 3 and ratios
`1/2,1,2`. This is an experiment policy, not editorial calibration.

`evaluate_calibration()` only requests CALIBRATION scores. It keeps rejected configs,
requires FPR <= 1% and precision >= 95%, maximizes recall, then favors lower threshold
and longer minimum run. No eligible config returns `NO_ACCEPTABLE_CONFIG`.
Validation requires the exact selected config, FPR <= 1%, precision >= 95%, recall >= 80%.
Holdout additionally requires each stratum FPR <= 5%, at least 250 definite quiet
and 250 definite activity frames, and <= 20% ambiguity. Missing sufficiency returns
`INSUFFICIENT_EVIDENCE`. Experiment scoring requires four strata/sessions and 3000
frames/session, corresponding to four 30-second windows at 25fps.

`audit_holdout_use()` must run **before** real data access. An attempted access must be
retained before evaluation, including failure/unknown attempts. It detects missing or
changed freeze/policy/config, failed validation, reused access/experiment or previously
consumed lineage in supplied history. Freeze retains original hashes as well as declared
lineage. Changing rubric/exclusion content invalidates the old frozen use.

This is an offline consistency contract, not a secure ledger, filesystem lock or
cross-process exactly-once mechanism. Omitted history, forged provenance or falsely
declared independent recordings/reviewers cannot be discovered from strings alone.
`evaluate_holdout()` is arithmetic, not data access authorization or G7 qualification.
The caller must retain evaluator failures/partial attempts and must not retune under
the same experiment. A changed policy requires a new experiment and untouched holdout.

## Receipt/privacy boundary and real-data inputs still required

The JSON schema and synthetic failure example contain only pseudonymous refs,
digests, bounded numeric aggregates and diagnostic codes. Raw bytes, sample arrays,
annotation text and arbitrary report strings are not receipt payloads. Hashes prove
byte consistency only, not recording authenticity, permission, honesty, native identity
or currentness. Exclusive creation prevents accidental overwrite, not external tampering.

Required before real G2–G6: authorized immutable originals in restricted external storage;
permission/expiry/retention evidence; recorder/device/processing/channel/origin metadata;
bounded extraction and independent re-extraction/reviewer receipts; independent session
lineage; two blind acoustic annotations per preselected window; frozen rubric/exclusions
and split; sealed untouched holdout/history; and an independent reproduction process.
The retained experiment inputs must be linked and reviewed before a real run. Current
schemas cannot authenticate those claims and do not autonomously open those inputs.

Retention is bounded by the earlier of 90 days after final Gate, permission expiry or
a shorter owner requirement. Withdrawal/deletion/unavailability requires a receipt and
reuse/reproduction HOLD. No raw media or real annotation originals go to Git or CI.

## Local validation receipt — not G4 gate execution

Environment: existing `vs001e-validation-env`; `PYTHONPATH=.;src;tests`.
No new dependency or suppression was added.

| Check | Result |
| --- | --- |
| `pytest tests/test_pcm_calibration.py -q -p no:cacheprovider` | 105 passed after PR #60 correction (original submission: 75) |
| Related PVP/OBS/Evidence/mapping/native/pause/planning/TRUST/orchestration | 584 passed |
| `pytest -q -p no:cacheprovider` | 2009 passed, 1 existing intentional-red opt-in skip after correction (original: 1979 / 1) |
| `ruff check .` | PASS |
| repository `mypy` | PASS, 41 source files |
| `mypy --strict --explicit-package-bases tools/pcm_calibration.py tests/test_pcm_calibration.py` | PASS, 2 files |
| Expanded legacy strict before/after | 840 errors in 4 files in both; diagnostic delta 0 |
| Whitespace / exact file allowlist | Checked locally; only six files above |
| Submission remote CI | Reported in PR against the exact submitted head; synthetic checks only |

The expanded baseline check used the identical base tree in the existing PVP-001A
worktree (commit `afbd20291bf518957053d4573c575af96475a4f9`). Base checked 21 files;
current checked the same 21 plus two new Python files, with
`--strict --explicit-package-bases --follow-untyped-imports`.
Counts: `test_execution_ir.py` 164, `test_expected_diff.py` 178,
`test_safety_preflight.py` 273, `test_transaction.py` 225. Both exits were 1;
expanded strict is **not green**. Unrelated baseline files were not changed.

Development receipts: initial targeted run had 66 passed / 1 failed due to the new
test using the wrong existing OBS field name; fixed in this PR's test only.
Initial new-file lint/type diagnostics were corrected. The first related-test command
used a nonexistent filename and ran no tests; corrected command passed 584 tests.
These failures were not real-data experiment runs. No hooks were invoked.
`git diff --check` exited 0. Each new/untracked file was additionally checked with
`git -c core.autocrlf=false diff --no-index --check -- NUL <file>`: exit 1 means
the files differ (the new file differs from NUL), as expected; whitespace diagnostics
were empty for all six files. This is separate from the disclosed legacy mypy failures.

## NOT_IMPLEMENTED / open items

- Actual G2 acquisition, real annotations, real calibration/validation/holdout or G6 reproduction.
- Extraction/decoder integration, actual recording authenticity, secure holdout ledger,
  trusted chronology, cross-process locking or automatic retention enforcement.
- Production config promotion, G7 decision, VAD/STT, transcript/semantic/breath/emotion/
  dead-air/failed-take/content-mode inference, confidence/editor calibration.
- Resolve access, native read qualification, native mutation, staging, approval UI,
  delegated request parsing, automatic REMOVE, DP001 validation or Net Time Saved proof.

OPEN-009 remains open beyond the PVP-001A deterministic acoustic baseline. Acquisition
authenticity, semantic producers, confidence calibration and real human value are unproven.
OPEN-002 / OPEN-008 and all native qualification HOLDs remain unchanged.
No REAL_MEDIA_PRODUCER_QUALIFIED, NATIVE_READ_QUALIFIED, NATIVE_MUTATION_QUALIFIED,
EDITOR_QUALITY_QUALIFIED or VERIFIED_LIVE claim is made.

Next action: independent Chat Gate code review, then an approved real-data input packet.
After PR submission and CI receipt, STOP; do not merge or start G2/another milestone.

## PR #60 narrow correction

Only this status document and the existing harness/test module change in this correction.

1. Freeze now retains exact immutable session/window manifests and annotation inputs,
   and recomputes their canonical digests. Each ConfigEvaluation retains its freeze,
   exact split input manifests and annotations. Calibration, validation and holdout
   verify the same frozen content, session IDs/strata, original hashes, windows,
   selected channels, PCM digests, annotation versions and records. Matching totals
   alone cannot bind a foreign dataset. Identical canonical reconstruction is allowed;
   Python object identity is not required. These are input-correlation checks, not
   authentication or proof that a supplied evaluator honestly computed its counts.
2. Acquisition validation requires explicit timezone-aware `experiment_use_at` and
   `permission_valid_from`; valid acquisition in the past is insufficient. Require
   valid_from <= acquisition <= declared use < expiry. Missing/invalid/naive times
   fail closed; no wall-clock default or silently assumed permission extension.
3. An explicit independent reviewer identity must equal the second extraction operator
   and differ from the first operator and recorder. The review receipt reference is
   not an authenticated identity; it must also not collide with either the recorder
   or first extraction operator reference. Dataset annotations must consistently use the declared two
   reviewer identities throughout, with both present for every window. This detects
   inconsistent supplied identities, not aliases or dishonest independence claims.

Thirty added synthetic regressions cover all three evaluation gates with substituted
sessions/channels/PCM/annotations, missing input and foreign freeze, immutable digest
tampering, permission-use boundaries/timezones and reviewer consistency. No real
acquisition or annotation was performed. Legacy expanded strict remains 840 / delta 0.

### Follow-up narrow regression receipt (2026-10-14)

Starting remote head: `15af3bc1a2f5432583e0c539decfcac4ed6b1889`, tree
`90450e21ad89fe9b94f92ef76a25ee8f2ef1f890`. Remote main still matches the G1 base
`0e727cb16af5538cc2bff977e4a495c603571699`. Its existing PR CI run 38525076829
was independently rechecked as completed/success before this follow-up.

The requested `independent_review_ref` collision check is now explicit in addition
to the existing `independent_reviewer_ref` identity check. Two new regressions
failed on the starting head and pass with the check; distinct recorder and first
extractor identities are tested independently. These are supplied-reference
consistency checks only, never authentication or proof of human independence.

Thirteen additional synthetic cases exercise both reviewer fields, complete foreign
datasets with perfect calibration/holdout scores, calibration membership relabelled
as validation, and unchanged session IDs with changed source digest/window bounds
at all three gates. Existing cases retain canonical PCM digest substitution and
permission valid-at-acquisition but expired-at-declared-use refusal coverage.

Fresh local verification: targeted **118 passed**, related **584 passed**, full
**2022 passed / 1 existing intentional-red opt-in skip**. Ruff, repository strict
mypy (41 files), and explicit strict (2 files) PASS. Expanded strict against the
exact main base: **840 before / 840 after**, zero new or removed normalized
diagnostics, both exit 1 (NOT green). This run explicitly includes the legacy
safety-preflight test module: 22 base files / 24 current files, compared with the
previous receipt's 21 / 23. The same four legacy modules account for all errors:
execution_ir 164, expected_diff 178, safety_preflight 273, transaction 225.
Environment: Python 3.11, pytest 9.1.1, Ruff 0.17.0, mypy 2.4.0;
`PYTHONPATH=.;src;tests`, `MYPYPATH=src;tests`. No configuration or suppression changes.

The correction changes only this document, the harness and its tests within the
original six-file PR allowlist. No production modules or real media were accessed
for modification; all test PCM is synthetic. The expanded 23-source acquisition
proposal is a separate Chat Gate deliverable, not implemented in this PR. The
older 15-source proposal below is historical and does not qualify the new inventory.
Exact follow-up head/tree and CI are retained in the external correction receipt.
G2-G7 HOLD; no merge, acquisition, real window selection or qualification.

## Separate future amendment proposal — NOT APPROVED / NOT IMPLEMENTED

Proposed scope: **bounded compressed-source acquisition -> canonical PCM16LE**.
This is a design proposal for a later Chat Gate, not permission to decode or run ffprobe.
No decoder, subprocess path, FFmpeg dependency or media access is implemented here.

Inventory facts below are user-supplied and accepted as inventory only, not independently
inspected or qualified by this correction:

- Conditional long sources: 02, 05, 06, 07, 09, 10, 11.
- Too short for four 30-second windows: 01, 04, 12, 13, 14, 15.
- Suspected duplicate/re-export pairs: 03/04 and 08/09.
- Independence of 10/11 unresolved; compressed inputs currently have no approved decode path.
- This inventory does not establish 12 independent eligible sessions. G2-G7 remain HOLD.

Proposed future procedure, only after separate approval:

1. Obtain explicit source/permission references, scope, expiry and declared use time.
   Keep originals immutable in restricted external storage. Record pseudonymous asset,
   byte length and SHA-256, then re-read/hash the original after extraction to detect
   changes. A hash demonstrates byte consistency only, not origin/authenticity.
2. Retain a bounded ffprobe metadata receipt: pinned executable/build hash and version,
   container, exact stream index/ID, codec, sample rate, channel layout/order, time base,
   start timestamps, duration and available priming/padding/edit-list information.
   Unknown origin metadata stays unknown. No filename/title/first-audio-stream selection.
3. Pin decoder/build/library versions, build options and relevant platform behavior.
   Record exact extraction parameters and a preregistered deterministic PCM16LE conversion
   policy, including sample quantization/dither behavior. Do not normalize, filter, resample,
   time-stretch, downmix or silently discard channels. Keep the declared channel order;
   select the analysis channel explicitly and separately. Non-48-kHz primary-profile
   sources remain unsupported under this proposal unless separately approved.
4. Decode only an approved bounded source/stream/window procedure. Establish codec delay,
   priming, padding and source-to-decoded-sample origin before accepting a window. Fast seek
   timestamps alone do not prove sample origin. If exact bounded decoding requires an
   unapproved larger decode or origin cannot be proven, STOP. Never round/clamp/repair an
   offset. Use exact sample counts and the existing frame/profile mapping checks.
5. Retain original input hash, canonical PCM output hash, output bytes, sample-frame count,
   stream/channel facts and exact sample interval/origin. Required PCM length is exactly
   frames * samples_per_frame * channels * 2. Canonical PCM remains external, never in
   Git, CI, EvidenceRecord, candidate or public logs. Public receipts contain pseudonymous
   references and digests only. Originals are not modified.
6. A genuinely independent reviewer/process re-extracts from the same immutable original
   with the pinned procedure, then compares bytes/digests/counts/channel/origin. It must
   not copy the first PCM or first report. Retain both pre-comparison receipts and any
   mismatch; seal only after independent review. Cross-platform divergence is HOLD,
   not permission to accept tolerance or choose the convenient result.

Proposed STOP conditions: unclear/expired permission; uncertain source lineage or stream/
channel; malformed/encrypted/unsupported codec; unknown priming/origin; nonintegral frame
alignment; non-48-kHz primary input; byte/sample/digest mismatch; source mutation;
unapproved processing or decode expansion; reviewer inconsistency; independent reproduction
failure; privacy leak; resource-cap breach; or need for Resolve/native access. A failed
extraction is retained as failure evidence, not retried with a changed policy to obtain PASS.

Before implementation the amendment must approve exact bounded decode limits, supported
codec/container profiles, canonical conversion rules, sample-origin evidence and fixture
tests. It does not authorize acquisition now, establish session independence, open any
validation/holdout, grant G2 qualification, or change production detector configuration.
