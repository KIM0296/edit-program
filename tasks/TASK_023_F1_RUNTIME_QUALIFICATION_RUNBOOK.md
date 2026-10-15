# TASK-023 F1 Runtime Qualification Runbook

Status: C01/C02/I0/I1 runbook previously APPROVED; C03 protocol addition DRAFT FOR CHAT GATE.
This revision writes a protocol only; it executes nothing and records no C03 result.
Base: 75cf16717666c5ed725c92b64ce32695aa21356e, PR #50, feat/free-in-resolve-bridge-feasibility.
Authoritative design: [Phase 1](TASK_023_F1_SEMANTIC_QUALIFICATION_PHASE_1.md), now Chat APPROVED.
ADR-041/042/043, shared ADR-008/015/016/021/022 and OPEN-001/006/008/012 remain unchanged.
C01/C02/C03 and I0/I1 are operationalized for later reviewed operator execution. Each case requires
Chat approval of its bounded case packet before action. This document grants no blanket execution,
fixture automation, probe extension, mutation, transport or distribution permission.

## Five separate evidence stages

A. **Fixture source oracle**: approved package bytes/hash, exact source rate/count, generator contract.
B. **Operator-prepared Resolve state**: independent preparation receipt, intended visible spans, rate/base,
   roles and placement provenance. Source correctness does not establish native materialization.
C. **Native read capture**: exact commands/arguments and unedited raw returns, errors and context.
D. **Semantic comparison**: explicit hypotheses against A+B, never a getter against itself.
E. **Gate result**: PASS / CONFLICT / UNKNOWN / INCOMPLETE for this case and declared scope only.

A getter-under-test cannot be its own oracle. Canonical source length/hash is independent source
truth, not proof of Resolve placement length, endpoint convention, coordinate basis or import fidelity.
Do not conflate E PASS with VERIFIED_EXACT, MappingStatus.EXACT, identity scope, Safety PASS or Apply.
No case below is pre-filled PASS. All new record templates are empty/unobserved.

## Canonical readiness checklist — before any future case

Operator must preserve evidence references for each item; absence/mismatch stops that case.
No media verification, copying, publication or materialization is performed by this Codex task.

- Sealed local package location exists; record actual location, not a invented release URL.
- Package canonical-fixture-assets / 1.0.0; digest must be
  17b5b007df4f328a414505e68b395bab4f466b72a207e93a4f006595cbc375de.
- Verify SHA-256 of exact checksums.sha256 bytes against that digest, then verify its manifest,
  generator lock and six asset entries; do not hash a differently normalized checksum file.
- Selected asset exists and its bytes match the approved SHA-256, not just filename/size.
- Record asset/package/recipe and ADR-036/037 contract versions from the approved manifest/index.
- No re-encoding or modification; if different bytes, stop, do not substitute or regenerate.
- Record Resolve product/version and operator-supplied edition separately: product string alone is not
  Free-edition proof. Record actual project/session/context; no production working project.
- Do not reuse an existing fixture unless independent preparation provenance is known and reviewed.
- Native Resolve import/materialization remains NOT QUALIFIED. Package verification is not its proxy.

Index: canonical_assets/first-package-candidate-v1/package-index.candidate.json.
Assets: alpha_v1.mov, beta_v1.mov, gamma_v1.mov, repeat_v1.mov, video_only_v1.mov, audio_only_v1.wav.
Video contract: 1280x720, exact 24/1 fps, 720 frames, 30 seconds. AUDIO_ONLY has no video-frame count;
it is a 30-second audio source. Do not treat source FPS as timeline FPS evidence.

C01 source: canonical:ASSET_VIDEO_ONLY:v1 / video_only_v1.mov,
SHA-256 51109edb40573bcf98c1373dae2e049c81da99db44186841779075624d650137.
C02 A uses that source; B uses canonical:ASSET_ALPHA:v1 / alpha_v1.mov,
SHA-256 67910939447e396ef0ce17d79d4303d223f20ca61b81337b034dfa8121d4d323.
C02 uses B's video only. Any unexpected audio placement is retained as a fixture deviation, not deleted
or silently omitted during capture. Filenames label receipts; they do not identify native objects.

## Common case packet and execution fence

Before execution, Chat reviews: one case/level, source verification receipt, fixture preparation plan,
independent oracle method, exact intended timeline rate/base, role-to-object binding method, allowed
reads/arguments, entry path, operator and stop conditions. Missing prerequisite -> HOLD, no native reads.
A run_id is an evidence label, never a native state token. One run per case attempt; sequence numbers
strictly increase. Never rewrite a failed run or reuse its ID for a clean-looking replacement.

Preparation is manual and separate from observation. The instructions below are for a later explicitly
approved operator session on a disposable project; no preparation is done now. Do not automate actions.
If the installed UI cannot unambiguously implement or independently document the stated preparation,
stop and report UNKNOWN/INCOMPLETE rather than improvise native commands or mutate a fixture to pass.

Record rate 24/1 and a selected explicit start label (proposed 01:00:00:00) in the preparation receipt.
Document the actual UI rate/label evidence and its interpretation; if only an ambiguous decimal or label
is available, rate/base evidence remains UNKNOWN. Do not derive native start=86400 or subtract 108000.
Getters may report a different origin. No native-frame expectation is precomputed from the label.

At the capture fence: preparation completed; no edits, playback, scrub, selection-based retargeting,
track toggles or Console-triggered state changes. Preserve pre-capture context. Human activity or drift
is recorded immediately and blocks currentness; it is never erased. Same values are not an atomic fence.
Switching fixtures is a separately reviewed preparation step outside each capture, not I2 qualification.

## Native read sheet (fixed candidates; no probe extension)

The existing allowlist is unchanged. The following are exact read expressions using explicitly bound
local context labels r, pm, p, t, item and mpi, not an executable generic dispatcher. Preserve the actual
assignment/command text used and its result in the manual transcript. r is the previously proven injected
global resolve. No dynamic method lookup, load/dofile, UI fallback, script loader or automatic control.

| Purpose | Exact read expression | Retained result / failure |
| --- | --- | --- |
| Runtime | r:GetProductName(); r:GetVersionString() | Raw strings or exact nil/error; no edition inference |
| Root traversal | r:GetProjectManager(); pm:GetCurrentProject(); p:GetCurrentTimeline() | Typed opaque handle availability only; no pointer text identity |
| Project context | p:GetUniqueId(); p:GetName() | Raw ID/name, independent lifetime status |
| Timeline context | t:GetUniqueId(); t:GetName() | Same; active does not mean authoritative |
| Timeline extent | t:GetStartFrame(); t:GetEndFrame() | Raw numbers, basis/endpoint NOT_ESTABLISHED |
| Track inventory | t:GetTrackCount("video"); t:GetTrackCount("audio"); t:GetTrackCount("subtitle") | Raw count/type; no invented zero |
| Candidate enumeration | t:GetItemListInTrack("video", 1) | All keys/values, including __flags; index only diagnostic |
| Placement | item:GetUniqueId(); item:GetName() | Distinguish placement from source; no filename fallback |
| Placement extent | item:GetStart(false); item:GetEnd(false); item:GetDuration(false) | Exact argument and Lua number, no cast |
| Source binding | item:GetMediaPoolItem(); mpi:GetUniqueId() | Opaque reference observation then source ID; no pointer identity |

Each semicolon-separated expression denotes a separate recorded read, not a supplied multi-call script.
Manually record type(value) together with the raw scalar result. Do not print opaque objects with tostring;
record raw_lua_type plus OPAQUE and separately read approved native IDs. Nil, false, empty string and empty
table remain distinct. Missing method vs lookup/call error vs missing parent must not be collapsed.
For lists preserve scalar metadata exactly (__flags=4194304 remains uninterpreted); positive integer
keys are candidate locators only. Malformed entries get individual diagnostics; keep other entries.
Bind item from the reviewed enumeration evidence and preparation receipt, not first numeric entry,
chronological rank, name, current position or media ID alone. If correspondence cannot be established,
stop that target as AMBIGUOUS. Source-ID linkage supplements explicit placement provenance.

Manual capture P3 requires exact commands and complete output, not a paraphrase. The existing P3
summaries remain historical summaries; do not manufacture a transcript to upgrade them. P2 requires
exact probe commit and SHA-256 plus full BOOT -> OBS -> END. Current approved Lua source hash:
86d4a843fe6ea11dd086feaa99ba035ce6dab0f554dd0c66e549ed3453cf58e3
(source present at approved base 75cf16717666c5ed725c92b64ce32695aa21356e).
Workspace launcher remains INCONCLUSIVE. No bypass is designed. If a directly evidenced one-shot
entry path cannot be supplied, P2 is blocked; use P3 only under its independently reviewed command packet.
No new true-argument calls are added to the probe. C07 and the Phase 1 extension proposal stay deferred.

## C01 — Known length single placement

**Purpose:** Distinguish source count from observed native placement duration, native origin and separate
timeline/item endpoint hypotheses using one independently prepared video placement.

**Prerequisites:** Common checklist and case packet reviewed; disposable project; C01 source hash valid;
manual preparation and observation boundaries recorded; no claim of native import qualification.

**Independent oracle:** 720 decoded source frames at 24/1, raster 1280x720, video only, approved bytes.
Separate receipt documents intended visible source frames 0000 through 0719 and a 720-frame visible span.
Use the canonical embedded frame counter and independent operator frame-by-frame review, not the five
getters under test, to document first/last visible source frame and uninterrupted frame count. If the
counter/readability or UI review cannot establish this, visible-length oracle is UNKNOWN, not assumed.

**Exact fixture preparation instructions:** In the later approved manual preparation session:
1. Open a dedicated disposable project; create a fresh named C01 timeline, not a working timeline.
2. Set intended timeline rate 24 fps and explicit start label 01:00:00:00 in the UI before placement;
   record screenshots/settings receipt and whether exact rational/base interpretation is established.
3. Manually import the hash-verified VIDEO_ONLY asset. Record import receipt tying verified local bytes
   to the actual pool object; filename resemblance is insufficient. Do not substitute/re-encode media.
4. Place its video once on V1 at the chosen timeline origin, intended full 0000..0719 source span, no
   retime, effect, transition or extra layer. Record every manual action; do not assume it succeeded.
5. Independently document visible source counter traversal, displayed timeline labels and intended
   placement length. Record trim/rate/import surprises as deviations. Preserve this receipt before C.
6. Freeze preparation. Acquire and bind native IDs by the approved read sheet; if preparation-to-native
   correspondence is ambiguous, stop. Do not repair the placement after observing a discrepancy.

**Allowed operator actions:** Only the approved manual preparation above before the fence, then fixed
read-sheet capture. Record context and scalar types. No state-changing actions within the read attempt.

**Forbidden operator actions:** Working-project use, automatic creation/import/trim, settings repair,
retime, guessed end adjustment, unreviewed getter, pointer targeting, repeated attempts until green.

**Exact native reads:** Entire common read sheet, one bound placement. Keep t start/end separate from
item start/end/duration. Record false argument explicitly. Other-than-one expected video item or unexpected
tracks/items is evidence of a fixture deviation, not permission to omit or delete anything.

**Raw output retention requirements:** Complete unedited command/return sequence, errors, metadata,
preparation receipt, source checksum proof and context fence; P2/P3 remain distinct.

**Expected evidence schema:** Common append-only schema; case_id C01; one observation record per getter;
separate A/B/C/D/E records and links. No values pre-filled from source expectations.

**Allowed conclusions:** Report observed numbers and candidate hypotheses. Compare duration to independent
visible count; compare item and timeline ends separately against known visible last frame and extent.
Test absolute-vs-relative native origin as alternatives, never assume the UI label's arithmetic origin.
A coherent hypothesis may be CORRESPONDENCE_CANDIDATE within this fixture only.

**Forbidden conclusions:** Imported duration=720 by default; end exclusive; start/base zero; equal native
and source coordinate bases; equal timeline/item endpoint convention; single-case VERIFIED_EXACT.

**PASS / CONFLICT / UNKNOWN / INCOMPLETE conditions:** PASS means complete bounded evidence agrees with
an explicitly stated hypothesis and independent A+B oracle, not global correspondence. CONFLICT means a
comparable native value contradicts the declared hypothesis/oracle; retain it. UNKNOWN means basis,
rate, role binding or independent visible span cannot be established. INCOMPLETE means missing required
reads, transcript/END, context or oracle receipt. Record all findings; no PASS if any blocking finding.

**Cleanup / stop point:** Preserve evidence and unchanged fixture; stop for Chat review. No delete, undo,
repair or next-case action. Cleanup itself requires a later approved operator action.

## C02 — Two adjacent controlled placements

**Purpose:** Test endpoint/adjacency hypotheses using two explicitly bound placements and an independent
zero-gap oracle; do not infer a layout from getter equality.

**Prerequisites:** Common checklist, approved C02 packet, both selected source hashes, exact timeline
rate/base evidence and independently prepared layout receipt. C01 is evidence, not automatic authorization.

**Independent oracle:** Intended A=VIDEO_ONLY and B=ALPHA video, each full source 0000..0719 / 720 frames.
Intended adjacency: A's last visible frame is immediately followed by B's first visible frame with zero
intervening timeline frames at the independently recorded timeline rate/base. Operator records a native
UI frame-step sequence around the junction before getter comparison: A frame 0719 then B frame 0000 on
consecutive timeline positions, plus visible full-span/source receipts. No gap/transition/overlap should
be hidden. Snap-to-edge alone is intention, not proof. If UI/independent observation cannot establish the
junction, adjacency oracle is UNKNOWN. GetEnd(A) == GetStart(B) is not an adjacency oracle.

**Exact fixture preparation instructions:** In a separately approved manual preparation session:
1. Use a fresh disposable C02 timeline, intended 24/1 and start label 01:00:00:00; preserve setting proof.
2. Import hash-verified VIDEO_ONLY and ALPHA with separate source-to-pool import receipts.
3. Place A once on V1 at the intended origin, full source span, no effects/retime/transition.
4. Place B's video only on V1 immediately after A, full source span. Do not insert B audio. Document
   source selection and action; do not rely on auto-ripple or linked selection as semantic proof.
5. Record independent first/last source counter checks and frame-step junction sequence with actual
   timeline labels, before API comparison. If unintended audio/gap/overlap/trim appears, preserve and stop.
6. Bind A/B to concrete observed placement IDs through the separate preparation and source receipts.
   Native source links confirm the recorded bindings, not filename/position/first-match guesses.
7. Freeze preparation; no further layout changes. Ambiguous A/B binding blocks the case.

**Allowed operator actions:** Approved preparation and independent junction observations before the fence;
fixed read capture for A and B after the fence. No operator retargeting/edit during capture.

**Forbidden operator actions:** Inferring adjacency from endpoints; repairing a gap/overlap to fit native
returns; flattening; normalizing duration; adding reads; copying a successful run over a failed run.

**Exact native reads:** Common read sheet once for context and inventory; placement/source reads for
both bound A and B. Preserve raw collection keys and unexpected members. No chronological key assumption.

**Raw output retention requirements:** Complete original commands/lines for both objects, exact ID binding
receipts, source hashes, independent junction sequence and all deviations. No hand-normalized transcript.

**Expected evidence schema:** case_id C02, preparation roles A/B in evidence notes with explicit binding
references; separate record per object/method. Source hashes and native IDs are distinct fields.

**Allowed conclusions:** Compare competing endpoint hypotheses against independent adjacency and both
visible lengths. Retain shared or differing timeline/item endpoint behavior as observed, not normalized.

**Forbidden conclusions:** Getter equality proves adjacency; array order identifies A/B; source media ID
alone identifies placement; C01+C02 certify all bases/rates/trim/precision; automatic VERIFIED_EXACT.

**PASS / CONFLICT / UNKNOWN / INCOMPLETE conditions:** PASS only for complete bounded hypothesis evidence
against the independent junction oracle; CONFLICT for a demonstrated contradiction; UNKNOWN for unresolved
junction, role/basis/rate meaning; INCOMPLETE for missing object/receipt/read/transcript. Multiple findings
stay separate; no PASS despite blocking evidence or missing declared coverage.

**Cleanup / stop point:** Preserve fixture and all evidence; stop for Chat. No automatic progression C03.

## C03 - One independently verified timeline-frame gap

Protocol revision base: 5ad09de305b9dfb690fc838dbcbfc758d6fcea4c. Only C03 is newly operationalized.
C01/C02 bounded PASS and I0/I1 observations remain as previously reviewed; I1's 9h30m interval grants
no further lifetime claim. Current coordinate status CORRESPONDENCE_CANDIDATE, endpoint NOT_ESTABLISHED,
FrameRange construction NOT AUTHORIZED. C03 runtime NOT EXECUTED by this task; result unfilled.

**Purpose:** Determine whether exact native observations distinguish the independently verified C02
zero-gap from an independently verified C03 one-frame gap, without selecting an endpoint convention
in advance. The two 720-frame sources do not themselves prove a native gap or native placement length.

**Prerequisites:** C03 case packet reviewed by Chat; disposable preparation context; common canonical
checklist satisfied; A/B independently bound; exact timeline rate/base evidence and preparation receipt.
C02 attempt 2 comparison evidence and its limitations must be linked, not reconstructed as a transcript.
No old C02 timeline is repaired or reused without provenance. Missing required oracle -> HOLD.

**Independent oracle:** A=canonical:ASSET_VIDEO_ONLY:v1 and B=canonical:ASSET_ALPHA:v1 video only.
Each source has 720 frames at exact 24/1. Use the common source hashes; confirm byte identity and visible
0000..0719 spans independently. The gap oracle is a native UI observation sequence, not a native getter,
endpoint subtraction, snap behavior, array ordering or a calculated FrameRange.

At the junction, the operator must record THREE distinct consecutive timeline positions:

| UI position label | Required observation (not a pre-filled result) | Evidence to retain |
| --- | --- | --- |
| U0 | A last visible source frame 0719 | Actual timeline timecode/frame label, A role receipt, source counter and timeline-view evidence |
| U1 | Exactly one manual timeline-frame step from U0: EMPTY_GAP | Actual position label and visible absence of any covering placement/layer; viewer state and timeline gap |
| U2 | Exactly one manual timeline-frame step from U1: B first visible source frame 0000 | Actual position label, B role receipt, source counter and timeline-view evidence |

UI labels U0/U1/U2 are evidence labels, not native coordinates. Actual displayed labels and observation
references are unfilled until capture. Preserve all three positions separately, not just a sentence that
there was a gap. Record each single-frame step action and whether the timeline viewer had focus.
Black output alone is insufficient (it could be black media, a hidden/disabled layer or display state).
The U1 receipt must independently show an empty interval on the controlled track and no other placement
covering that position. A held viewer frame, unclear focus, fractional scrub, hidden structure, unexpected
layer or inability to inspect the UI position means UNKNOWN/INCOMPLETE. Do not infer blankness from API.
This is manual operator observation, never UI automation or native capability fabrication.

**Exact fixture preparation instructions:** For a later separately reviewed operator preparation only:
1. Prepare a fresh disposable C03 timeline, e.g. C03_GAP1_24_ATTEMPT1; name is descriptive, not authority.
   Leave C01/C02 and every prior failed attempt unchanged. Record actual project/timeline identity later.
2. Before placements, select intended timeline rate 24/1 and start label 01:00:00:00 via native UI;
   preserve actual setting/rate evidence, not a guessed native numeric origin. If exact rate/base is
   unproven, stop; no automatic 86400 assumption or timecode-to-frame conversion.
3. Import/select the hash-verified A and B sources with separate pool/source receipts. Place A once on
   V1, full intended 0000..0719 visible span. Place B video only once on the same controlled track,
   intended full 0000..0719 span. No ALPHA audio, retime, effect, transition or covering layer intended.
4. Establish the intended layout manually before the capture fence: use native UI single-frame
   timeline navigation and a manual whole-placement B positioning action, without trimming either
   boundary, to leave exactly one timeline frame between the visible A and B spans. Record the exact
   UI action used on this installation. Do not prescribe an unverified keyboard shortcut or automate it.
   An intended one-frame move or snap is NOT the oracle. If that operation cannot be performed or
   documented unambiguously, HOLD; do not use API mutation, workaround or a guessed position.
5. Independently verify A and B visible spans and perform U0 -> U1 -> U2 as above. Record timeline labels,
   screenshots/observation refs and both one-frame actions, before reading endpoints under test.
   If audio, gap-length error, hidden layer, trim or another deviation is found, preserve and STOP.
   Do not move/trim/delete anything to turn that failed attempt into a clean attempt.
6. Freeze preparation. Link role A/B to explicit concrete placement/source evidence using the common
   approved read sheet and reviewed preparation receipts. Do not infer A/B from numeric keys, name,
   source ID alone, first-match or current position. Ambiguous correspondence blocks comparison.

Fixture preparation receipt fields: case/attempt evidence label; actual operator and preparation times
when supplied; project/timeline context; source asset IDs/hashes and native source bindings; exact
rate/base evidence; A/B intended spans and preparation actions; independently checked visible spans;
U0/U1/U2 records; track/layer inspection; deviations; capture-fence declaration and role-binding refs.
None is pre-filled as an observation. Receipt source expectations remain separate from observed state.

**Allowed operator actions:** Only later Chat-approved manual preparation and independent UI oracle
checks before the fence, then the existing bounded read sheet. Preserve observations without edits.
No playback/scrub/selection retargeting or UI preparation during native capture.

**Forbidden operator actions:** Resolve execution by Codex; preparation/mutation scripts; probe extension;
endpoint-driven gap adjustment; +/-1 repair; rounding, tolerance, clamping, rebase or endpoint normalization;
using snap/order as oracle; deleting unexpected audio/layers; retry-until-green; advancing to other cases.

**Exact native reads:** Existing common sheet only: r:GetProductName(), r:GetVersionString(),
r:GetProjectManager(), pm:GetCurrentProject(), p:GetUniqueId(), p:GetName(), p:GetCurrentTimeline(),
t:GetUniqueId(), t:GetName(), t:GetStartFrame(), t:GetEndFrame(); t:GetTrackCount for the existing video,
audio, subtitle arguments; t:GetItemListInTrack for each reported track/type/index using the already
approved enumeration method. No new native method or Lua implementation is added.
For each independently bound A/B: item:GetUniqueId(), item:GetName(), item:GetStart(false),
item:GetEnd(false), item:GetDuration(false), item:GetMediaPoolItem(), mpi:GetUniqueId().
Preserve exact arguments/track indices, native raw types and all mixed-key metadata. Enumerating all
reported tracks documents unexpected structure; it is not a completeness or participant-selection proof.
No true-argument extension, source-coordinate getter, settings dump or other read is authorized here.

**Raw output retention requirements:** Keep complete exact P3 commands/returned lines/errors and original
UI/source/preparation evidence, not a normalized transcript. P2 remains separate, requires exact reviewed
probe commit/hash and BOOT -> OBS -> END; Workspace launcher still INCONCLUSIVE with no bypass.
A partial transcript, failed binding or failed fixture is retained. No source hash or prior PASS fills a
missing C03 return. Opaque handles remain typed OPAQUE, never pointer identity. No invented dates/run IDs.

**Expected evidence schema:** Existing append-only record format with case_id C03, no new architecture
schema. Link the fixture receipt/U0/U1/U2 via fixture_oracle_ref/preparation_receipt_ref/transcript_ref;
record three separate UI observation records with their actual labels/raw observations in the existing
stage/raw_value fields (native_method unfilled for a UI-only record). UI evidence is not a native call.
Then separate native observations, hypothesis/comparison records and gate decision. Clearly mark planned
expectation versus observed value. Initial semantic status NOT_ESTABLISHED until evidence supports a
candidate; no native number is converted into FrameRange. Gate result remains null until review.

**Allowed conclusions:** Only AFTER U0/U1/U2 independently establishes the one-frame gap and bindings/
rate/base are adequate, compare these explicitly stated hypotheses without preselecting H1:

| Hypothesis | Stated interpretation to test, not conversion rule | Conditional prediction / discriminator |
| --- | --- | --- |
| H1 | Item start labels first included frame; item end labels first excluded boundary in a common unit/basis | C02 raw B.start minus A.end would be 0 and C03 would be 1; known visible lengths and GetDuration must also be consistent |
| H2 | Item start labels first included frame; item end labels last included frame in a common unit/basis | C02 raw B.start minus A.end would be 1 and C03 would be 2; compare lengths/duration independently, never add/subtract a frame to fix returned values |
| H3 | Getter endpoint or coordinate bases are not one unified item/timeline convention | Preserve a separate alternative; do not fit offsets to force agreement. If basis cannot be specified from independent evidence, comparison remains UNKNOWN/underdetermined |

These predictions are hypotheses, NOT gap oracles or repaired endpoints. Timeline.GetEndFrame has no
inherited item-end interpretation; test timeline extent separately against independent A/gap/B layout.
For each H record C02 evidence ref, C03 raw observations, independently observed gap (0 vs 1), whether
all stated predictions hold and counterevidence. Do not subtract absolute coordinates between different
timelines or silently align origins. Compare only within-case raw differences and qualified comparable
conditions; rate/base/placement mismatches stay explicit. Source/timeline identity is not assumed.
Ask: do native observations distinguish the independent zero-gap and one-frame-gap EXACTLY, and is one
explicit hypothesis consistent with all bounded evidence? If several interpretations survive, retain
ambiguity; no majority/ranking or automatic H1 selection. Historical C02 summaries are summaries; missing
comparison evidence remains missing. Current C01/C02 data do not pre-fill a C03 expected observation.

**Forbidden conclusions:** C03 PASS is not VERIFIED_EXACT globally, global half-open parity, allowed
FrameRange construction, source/timeline coordinate identity, C04-C07 coverage, identity promotion or
mutation readiness. Do not turn a hypothesis-specific arithmetic prediction into endpoint normalization.

**PASS / CONFLICT / UNKNOWN / INCOMPLETE conditions:**
- PASS: complete bounded observations agree with one explicitly stated hypothesis AND the independent
  one-frame-gap oracle, with comparable C02 evidence and no unresolved blocking ambiguity. Bounded only;
  coordinate conclusion at most CORRESPONDENCE_CANDIDATE, endpoint convention still NOT_ESTABLISHED.
- CONFLICT: comparable observations contradict a declared hypothesis or independent oracle; retain the
  exact failed prediction and all evidence. Do not repair/retry to remove it. Rejected competing hypotheses
  remain recorded even if another hypothesis fits; case gate must explain its scoped conclusion.
- UNKNOWN: gap, empty UI position, focus, coordinate basis/rate, identity correspondence or discrimination
  among surviving hypotheses cannot be established. Black output or getter equality alone is insufficient.
- INCOMPLETE: any U0/U1/U2 record, command/output, source/preparation receipt, required read or context is
  missing/truncated, or fixture deviation stops capture. Preserve all findings; never force PASS.

**Cleanup / stop point:** Preserve unchanged fixture and all attempts/observations; stop for Chat Gate.
No automatic deletion, undo, repair, further case or lifetime experiment. C04-C07, I2-I4, F2/F3, IPC,
persistence, mutation automation, parity runner and distribution remain NOT AUTHORIZED/HOLD.

## I0 — Immediate reread in unchanged context

**Purpose:** Measure same-context immediate equality field by field without identity/currentness promotion.

**Prerequisites:** Reviewed I0 packet; explicitly bound project/timeline/placement/source; no edits or
operator activity across read A/read B; same Resolve session recorded. No whole-level pass from old P3.

**Independent oracle:** Operator session/context/activity record and previously reviewed role/source
binding. It establishes intended comparison, not an atomicity guarantee. No pointer identity oracle.

**Exact fixture preparation instructions:** Use one independently prepared reviewed C01/C02 fixture;
no new preparation. Record actual current context and target binding. If provenance is missing, HOLD.

**Allowed operator actions:** Two immediate bounded read sets A then B; record actual timestamps and
any interference. No deliberate wait criterion or third read to replace an inconvenient result.

**Forbidden operator actions:** Edit, playback/scrub, switch context, rebind heuristically, implicit retry,
state-token synthesis, shared IdentityScope promotion.

**Exact native reads:** r product/version; root traversal and p/t IDs/names; item GetUniqueId,
GetStart(false), GetEnd(false), GetDuration(false); item GetMediaPoolItem then mpi GetUniqueId in both
sets. Reacquire p/t via approved roots for B, and re-enumerate the same explicitly bound target via common
inventory reads. Do not compare only cached handles. Ambiguous rebinding -> AMBIGUOUS, not first match.

**Raw output retention requirements:** Both full sequences and exact commands, context/target evidence,
wall-clock times and operator interference. No printout of handle address as identity.

**Expected evidence schema:** identity_level I0; pair refs A/B; one per-field outcome; project ID, timeline
ID, placement ID, source ID, ranges and context each retain their own result and any missing evidence.

**Allowed conclusions:** STABLE_OBSERVED_AT_LEVEL for directly comparable equal fields; CHANGED for
comparable differences; NOT_OBSERVED for absent comparison; AMBIGUOUS for unbound correspondence; ERROR
for failed read. A changed range is not automatically changed identity.

**Forbidden conclusions:** I0 implies I1/I2; stable source implies stable placement; equality establishes
atomic snapshot, freshness, persistent native handle or SESSION_LOCAL_VERIFIED/PERSISTENT_VERIFIED.

**PASS / CONFLICT / UNKNOWN / INCOMPLETE conditions:** PASS = complete declared field comparison with
stable values at I0 only. CONFLICT = directly comparable change against declared no-change condition;
UNKNOWN = ambiguous correspondence/currentness; INCOMPLETE = any absent/error comparison or transcript.
These gate findings do not replace per-field outcomes; required currentness may remain UNKNOWN even if
all observed fields match. Existing P3 has only partial video-field I0 evidence, not whole-case PASS.

**Cleanup / stop point:** Retain pair, no retries; stop for Chat review without extending to I1.

## I1 — Later reread in the same session

**Purpose:** Measure equality across a recorded elapsed interval without inventing a stability threshold.

**Prerequisites:** Reviewed I1 packet; same session and explicit target; independently documented no-edit
interval. No I0 result authorizes I1. Actual interval is recorded, not a prescribed minimum wait.

**Independent oracle:** Session/context and complete intervening-activity log; this remains operator
provenance, not native no-edit proof or state-token authority.

**Exact fixture preparation instructions:** Existing provenance-qualified fixture only. Record baseline A
using I0 field set; later record B in same session/context. No fixture changes between reads.

**Allowed operator actions:** Approved read A and later B, with wall-clock timestamp/timezone and actual
elapsed time evidence. Log intervening activity explicitly, including no activity if that is reported.
If clocks change or elapsed time cannot be established, preserve uncertainty; do not invent seconds.

**Forbidden operator actions:** Edit/switch/reopen/restart, persistent loop, timer listener, retry-until-green,
minimum-wait rule, extrapolation to other intervals/lifetime levels.

**Exact native reads:** Same approved I0 read set and fresh root/target reacquisition for A/B. No new getter.

**Raw output retention requirements:** Exact commands/returns for A/B plus actual elapsed time and
intervening activity. A missing activity log is missing evidence, not an assumed clean interval.

**Expected evidence schema:** identity_level I1; A/B refs, elapsed_time_evidence and activity_log refs;
per-field outcomes remain independent of I0 and other fields.

**Allowed conclusions:** The five I0 per-field outcomes at I1 for this observed interval only.

**Forbidden conclusions:** I1 implies I2-I4, supports a new persistent process, proves freshness or a
minimum safe duration, promotes identity scope or qualifies untested builds/objects.

**PASS / CONFLICT / UNKNOWN / INCOMPLETE conditions:** Same evidence rules as I0, scoped to recorded I1
interval; unknown clock/context/activity -> UNKNOWN/INCOMPLETE, observed drift -> retained CHANGED/CONFLICT.
No automatic retry or semantic repair.

**Cleanup / stop point:** Preserve baseline/later evidence; stop. No timeline switch, reopen or restart.

## Deferred cases — skeletons only, not authorized for execution

The following rows are case packets to be completed at a later Chat review, not operational steps.

| Case ID | Purpose | Independent oracle / prerequisite | Exact preparation and native reads |
| --- | --- | --- | --- |
| C04 | Naturally permitted one-frame overlap | Independently verified overlap/track layout; no forced transition | NOT SPECIFIED FOR EXECUTION; conditional availability |
| C05 | Trimmed placement | Independent visible/source span and trim receipt | NOT SPECIFIED FOR EXECUTION |
| C06 | Different timeline start/base | Independent layouts and base/rate evidence | NOT SPECIFIED FOR EXECUTION |
| C07 | false/true and fractional behavior | Exact precision arguments and independent fractional oracle | NOT SPECIFIED FOR EXECUTION; probe extension not approved here |
| I2 | Timeline switch and return | Explicit A/B/A context correspondence | NOT SPECIFIED FOR EXECUTION; switching NOT AUTHORIZED |
| I3 | Project close/reopen | Independent project/reopen boundary evidence | NOT SPECIFIED FOR EXECUTION; reopen NOT AUTHORIZED |
| I4 | Resolve restart/reopen | Independent new session/build/project binding | NOT SPECIFIED FOR EXECUTION; restart NOT AUTHORIZED |

For EACH skeleton the remaining required sections are fixed as follows:
- Allowed operator actions: planning/receipt review only; no runtime action.
- Forbidden operator actions: all execution/preparation/switch/reopen/restart until case review.
- Raw output retention requirements: none fabricated; future exact transcripts/errors required.
- Expected evidence schema: common schema with its case ID/level; no pre-filled results.
- Allowed conclusions: NOT_OBSERVED / not operationalized only.
- Forbidden conclusions: PASS, VERIFIED_EXACT, cross-level stability or implied authorization.
- PASS / CONFLICT / UNKNOWN / INCOMPLETE conditions: PASS unavailable before a reviewed bounded protocol;
  record missing protocol/evidence as INCOMPLETE, not a runtime failure or native UNSUPPORTED claim.
- Cleanup / stop point: no cleanup actions; STOP at design.

## Append-only evidence format (operator-maintained, no writer implemented)

Use one versioned record format, one record per observation/preparation/comparison/gate event. Link records
by ID; never overwrite/delete a prior record. Unique record IDs and strictly increasing sequence_no per
run are mandatory; duplicates/out-of-order numbering -> INCOMPLETE. A correction is a new record with
supersedes_record_id and reason; original and failure remain visible. New attempt -> new run_id, never
retry-until-green. Source receipt, prep, raw transcript and comparison are separate refs, not substitutions.

Null template fields mean unfilled, not native nil, zero, false or default. read_outcome explicitly
separates VALUE/NIL/UNAVAILABLE/UNKNOWN/ERROR. raw_value for opaque objects is OPAQUE with raw_lua_type;
never store an address/pointer text as identity. Preserve typed scalar strings/numbers without coercion.
If transcript unintentionally contains handle text, retain original transcript securely as raw evidence,
but never index/use that text as identity or propagate it into identity fields. No hand-editing transcript.
P3 exact_command and unedited complete returned lines required; P2 exact probe commit/hash and complete
BOOT/OBS/END required. Truncation/errors/missing END -> incomplete capture, not invented replacement.

All future observations distinguish coordinate basis, endpoint, exact rate evidence, source/timeline
domain and qualification status. Even a case PASS cannot construct FrameRange. Only a later reviewed
qualification satisfying Phase 1's full approved gate could permit that in a separate task.
Known snapshot/base mismatch -> STALE in the existing shared contract; missing currentness remains
BLOCKED_UNKNOWN. No synthesized state_token, no silent rebase. Coordinate status and currentness are
separate; human changes take precedence. Evidence records have no approval/apply semantics.

The machine-checkable design below is a schema/template, not an executed record or runtime validator.

```json
{
  "schema_version": "f1-runtime-runbook-v1",
  "package_digest": "17b5b007df4f328a414505e68b395bab4f466b72a207e93a4f006595cbc375de",
  "operational_coordinate_cases": ["C01", "C02", "C03"],
  "planned_coordinate_cases": ["C04", "C05", "C06", "C07"],
  "operational_identity_levels": ["I0", "I1"],
  "future_not_authorized_identity_levels": ["I2", "I3", "I4"],
  "execute_in_this_task": false,
  "future_case_requires_chat_review": true,
  "independent_oracle_required": true,
  "getter_under_test_is_oracle": false,
  "canonical_asset_proves_materialization": false,
  "coordinate_statuses": ["NOT_ESTABLISHED", "CORRESPONDENCE_CANDIDATE", "VERIFIED_EXACT", "CONFLICT", "UNKNOWN"],
  "frame_range_construction": false,
  "forbidden_repairs": ["round", "floor", "ceil", "clamp", "tolerance", "+1", "-1", "silent_rebase"],
  "pointer_handle_identity": false,
  "cross_level_inference": false,
  "retry_until_green": false,
  "append_only": true,
  "provenance_classes": {"P2": "reviewed_probe", "P3": "operator_manual_console"},
  "require_complete_probe_capture": ["BOOT", "OBS", "END"],
  "manual_transcript_editing": false,
  "not_authorized": ["F2", "F3", "IPC", "listener", "persistence", "mutation_automation", "UI_automation", "parity_runner", "distribution", "installer", "macOS_packaging"],
  "shared_core_changes": [],
  "lua_probe_changes": [],
  "record_template": {
    "record_id": null, "sequence_no": null, "run_id": null, "case_id": null,
    "identity_level": null, "stage": null, "operator": null, "wall_clock_timestamp": null,
    "session_ref": null, "resolve_version_string": null, "product_string": null,
    "project_id": null, "project_name": null, "timeline_id": null, "timeline_name": null,
    "source_asset_id": null, "source_sha256": null, "source_native_id": null, "placement_id": null,
    "track_type": null, "track_index": null, "native_method": null, "method_arguments": null,
    "raw_lua_type": null, "raw_value": null, "read_outcome": null, "error": null,
    "provenance": null, "fixture_oracle_ref": null, "preparation_receipt_ref": null,
    "coordinate_basis_status": "UNKNOWN", "endpoint_status": "NOT_ESTABLISHED",
    "coordinate_domain": "UNKNOWN", "rate_evidence": null, "snapshot_currentness_evidence": null,
    "semantic_qualification_status": "NOT_ESTABLISHED", "exact_command": null,
    "transcript_ref": null, "probe_commit": null, "probe_sha256": null,
    "comparison_record_refs": [], "per_field_identity_outcome": null,
    "elapsed_time_evidence": null, "activity_log_ref": null, "findings": [],
    "gate_result": null, "gate_scope": null, "supersedes_record_id": null, "correction_reason": null
  },
  "c03_protocol": {
    "source_roles": {
      "A": "canonical:ASSET_VIDEO_ONLY:v1",
      "B": "canonical:ASSET_ALPHA:v1"
    },
    "ui_position_sequence": [
      "A0719",
      "EMPTY_GAP",
      "B0000"
    ],
    "individual_ui_positions_required": 3,
    "native_getters_are_gap_oracle": false,
    "snap_or_collection_order_is_oracle": false,
    "comparison_requires_independent_gap_evidence": true,
    "hypotheses": [
      "H1",
      "H2",
      "H3"
    ],
    "selected_hypothesis": null,
    "gate_result": null,
    "pass_scope": "BOUNDED_CASE_ONLY",
    "endpoint_status": "NOT_ESTABLISHED",
    "frame_range_authorized": false,
    "native_methods_added": [],
    "compare_to_c02_without_rebase": true,
    "codex_executes_case": false
  }
}
```

No aggregate PASS masks a conflict, missing oracle, failed read or unknown correspondence. Preserve all
findings; final case result and reason must describe blocking evidence. A conflicted hypothesis remains
CONFLICT; incomplete collection is not made complete by dropping entries. Gate review may request a
new separately authorized case, never erase/relabel an old run. Full qualification is not achieved by
completing these bounded coordinate cases or two lifetime levels.

## Stop / submission checklist

Submit case packet, source receipt, preparation evidence, full raw transcript, schema records and all
findings to Chat; no new native facts asserted by this document. No Lua extension, native execution,
fixture mutation code, automatic Resolve control, persistence, IPC, UI fallback, parity, shared Core
change, Studio downgrade or installer/distribution work. Stop after reporting this runbook.
