# STYLE-001B — Immutable Style & Reference Domain Foundation

Status: **GO candidate for pure domain/contract review only.**
No commit/push. No media analysis, automatic learning, persistent profile update,
native integration, classifier change, or editing qualification.

## Base and worktree

- Verified current remote main SHA: `26c9574a1415807c7c33a6cd1eca4177e414d467`.
- Base tree: `eb7b1f83a70ab5e86ff04e2e8bc967c748ed5083`.
- Branch: `feature/style001b-reference-style`.
- Worktree: `C:/Users/c/source/repos/edit-program-style001b`.
- This independent domain task branches from main. The separate VS-001I branch
  at `e13b730c405468dcd09a8ceded13147f493f6d6a` was left untouched; it was not part
  of main when this task began. This task does not merge or depend on that branch.
- Exact new files:
  - `src/davinci_ai_editor/reference_style.py`
  - `tests/test_reference_style.py`
  - `docs/STYLE_001B_REFERENCE_STYLE_STATUS.md`

No existing production module, test, or configuration is edited. In particular,
pause.py, expected_diff.py, safety_preflight.py, authority.py and runtime modules
remain unchanged. Reference and style contracts fit in the one proposed module;
no additional file split was necessary.

## Public domain contract

The nine requested immutable records are implemented:

- ReferenceQuery
- ReferenceCatalog
- ReferenceRef
- ReferenceResolution
- StyleIntent
- StyleEvidence
- StyleProfile
- EffectiveStyleContext
- StyleProfileDeltaProposal

Supporting frozen values explicitly represent catalog/item/revision identity,
entries, aliases, predecessor relations, scope bindings, semantic preferences,
profile versions, supplied hard preference envelopes and consumer support,
per-dimension selection/problems, preference changes, profile approvals, and
profile-update results. Enums describe these domains only. There is no Candidate,
Safety, ExpectedDiff, transaction, or native-operation replica.

The only pure operations are:

- `resolve_reference(query, catalog)`
- `compose_style(intent, *, profiles, evidence, application_scopes,
  hard_constraints, capabilities, hard_constraint_refs, capability_refs, defaults)`
- `apply_profile_delta(profile, proposal, approval)`

Existing `ProducerRef`, `EvidenceStrength`, `EvidenceAssertion`, and `FeedbackEvent`
are reused. The evaluation module's ReferenceJudgment remains an evaluation
judgment, not a media reference. Frozen records normalize collections to tuples;
existing contained immutable objects remain retained rather than serialized.

## Reference resolution and identity

Resolution is deterministic over the supplied catalog; no I/O, search, LLM,
embedding retrieval, filesystem traversal, title similarity, or timestamp rule
is present. A proposed memory/chat candidate is diagnostic only: even if it exists
in the catalog, PROPOSED does not become a selected reference without a subsequent
explicit selection/query.

| Status | Meaning |
| --- | --- |
| EXACT | Explicit exact identity/revision matches an available supplied entry. |
| CONTEXT_RESOLVED | A declared alias or complete scoped predecessor relation yields one available entry. |
| AMBIGUOUS | More than one valid identity remains. |
| UNRESOLVED | No match, missing context/relation, incomplete relation coverage, or only proposed candidates. |
| STALE | Supplied catalog binding, alias, anchor, or revision has explicit stale evidence/state. |
| UNAVAILABLE | Supplied catalog/alias/anchor/target is unavailable. |

Only EXACT and CONTEXT_RESOLVED expose selected_ref. Non-success results retain
available candidates and reasons without selecting one. Unavailability/staleness
is not discarded to force uniqueness. Conflicting duplicate catalog identity or
ordering declarations are malformed contract inputs, not silently prioritized.

PREVIOUS requires an explicit scope, exact anchor item/revision, named ordering
relation, declared complete predecessor coverage, and exactly one available
predecessor. One visible candidate in an incomplete relation remains UNRESOLVED.
No supplied relation means UNRESOLVED, not inferred chronological ordering.

ReferenceRef retains CatalogRef, namespace/item/exact revision, source kind,
representation form, declared lifetime, provenance, and limitations. Locator and
title are descriptive. Allowed source categories include explicitly supplied
URL/file, authorized timeline, approved output, saved entry, and channel/project
catalog. Actual registration, read permission and provenance authenticity remain
producer responsibilities. Records do not fetch or authenticate their targets.

Historical age is not staleness. A pinned old revision can still resolve EXACT
while a newer revision exists or a separate mutable alias is stale.

## Intent and modification scope

StyleIntent retains request provenance, target scope, explicit
modification_scope_ref, preference scope, requested dimensions, explicit semantic
preferences, optional query/resolution, comparative baseline, and unresolved
interpretation/dimensions.

PreferenceScope means applicability: ONE_EDIT, PROJECT, CONTENT_TYPE, CHANNEL,
USER_DEFAULT, TEAM. It is not permission to change the whole project/channel.
The opaque modification_scope_ref states the supplied modification boundary.
EffectiveStyleContext must retain exactly the intent's binding. Substitution is
rejected; a new scope requires a new intent/context value.

Accepted/frozen work remains user-owned. This module neither checks nor implements
freezing/locking and does not certify the supplied scope as authorized. It never
expands scope or reopens accepted work. Actual scope enforcement remains outside
the style domain.

## Evidence and reference-dimension selection

StyleKnowledge (OBSERVED, INFERRED, UNKNOWN) is separate from the existing
EvidenceAssertion axis. Unknown knowledge cannot carry a known value or an ABSENT
assertion. Missing evidence is the absence of a record, not an UNKNOWN record.
All records retain the reference revision, observed scope, existing producer and
strength, typed feature/value, basis references and limitations.

Rendered or unknown representations cannot assert hidden source removals, rejected
takes, hidden tracks, or editor intention; these must remain UNKNOWN. Editable
reference forms can carry richer read evidence. Machine-read project structure
still cannot directly establish an editor's intention; human-supplied evidence
is required for an OBSERVED intention claim. No analyzer is implemented.

Reference evidence never becomes preference by its mere presence. Inheritance is
restricted to the intent's explicit inherit_dimensions. Reference requests lacking
dimension selection remain unresolved rather than inheriting everything or
silently falling back to defaults. Explicit preference plus inheritance for the
same dimension is preserved as a conflict.

For a reference-selected dimension, SelectedStyle retains the exact observed
descriptors and origin REFERENCE; its preference field is None. A brisk reference
does not automatically mean "make this target faster." No conversion from reference
descriptors to target-relative numeric or semantic directives is invented. Inferred,
unknown, missing, conflicting, or wrongly bound reference observations prevent
selection for that dimension. Evidence strength does not resolve disagreement.
When a hard preference envelope cannot be checked against a descriptor, composition
blocks that dimension rather than converting the descriptor to satisfy the policy.

## Profile, precedence and constraints

StyleProfile retains exact ID/version, schema, parent version, owner/scope,
applicability/exclusions, typed preferences, provenance, approved-delta/approval
references, and limitations. Opaque learned representations are not profile values.
Only PACING and PAUSE_PRESERVATION are supported dimensions. Values remain semantic
directions (calmer/balanced/faster and preserve-more/balanced/tighten-more).
No frames, pause signals, confidence, cut geometry, or commands are produced.

Per dimension, precedence is explicit current request, PROJECT, tied
CHANNEL/CONTENT_TYPE, USER_DEFAULT, TEAM soft default, and supplied zero-shot
defaults. ONE_EDIT is supported on intent/scope records, but an applicable ONE_EDIT
profile is not implicitly promoted to an explicit request or assigned an extra
priority tier. Without an explicit current value/inheritance request, such a
dimension remains unresolved. No default values are invented by the module. Applicability conditions
must match explicit supplied scope bindings; exclusions prevent profile use.

Higher-priority sources override only dimensions they actually specify. Equal-tier
conflicts remain StyleProblem(CONFLICT); no averaging or latest-wins. Matching
equal-tier values retain all supplying profiles. Multiple versions of the same
profile at the selected tier are not resolved by version sorting.

HardStyleConstraint represents a supplied allowable preference envelope, not a
new Safety evaluator or Team policy engine. All applicable hard envelopes must
permit a preference; missing/unknown restriction information blocks. StyleCapability
retains supplied support for consuming the dimension, not verified native editing
capability. Missing, unknown or false support cannot be enabled by style.
Hard policy/Safety/capability references remain distinct retained context inputs.
No positive style result certifies Safety PASS, Apply permission, or native support.

EffectiveStyleContext retains the exact intent, supplied profile versions,
resolutions/evidence, scopes, per-dimension sources, conflicts/unresolved dimensions,
constraints/capability references, defaults, modification binding and rule version.
It has no edit-authority or quality-success flag. Updating a profile does not change
an existing context or candidate.

## Feedback, approval and version creation

No learning algorithm or background collection is implemented. Existing immutable
feedback is an input to a supplied StyleProfileDeltaProposal, which retains exact
base version, before/after values, scope, supporting feedback/proposal refs,
contrary evidence and generalization limitations.

One correction without explicit approval returns APPROVAL_REQUIRED, not a new
profile. StyleProfileApproval binds the entire delta, explicit owner/approver,
new version, and approval provenance. This is not authority.ApproveCandidate.

apply_profile_delta returns:

- CREATED: a new in-memory immutable profile, exact parent, new preferences,
  approved delta/approval/provenance refs, and retained generalization limitations.
- APPROVAL_REQUIRED: no new profile.
- STALE: supplied current base version differs; no auto-merge/rebase.
- CONFLICT: approval/owner/scope/before-value/version mismatch; no repair.

Approval authenticity and actor permission are supplied external obligations. Root
profile provenance, globally unique version allocation, history-wide version reuse
checks, concurrent publication, and durable selection of a current version require
a future store/governance boundary. Value creation here is not a durable update.

## Product and host boundaries

Existing Editing Environment First; No New Editing Surface; native NLE remains the
source of truth. The public domain has no host-specific identifiers or APIs. No
reference media is modified. Reference ranges are not automatically mapped to
target timeline coordinates.

Style can only supply context for a future proposal policy. Pause classifier
behavior, confidence routing, Safety, Candidate Authority, ExpectedDiff/ActualDiff
separation and Human Edit Wins remain unchanged. A future change to a proposal must
still pass existing geometry/planning, Safety, approval and runtime boundaries.
Shadow Learning does not imply profile mutation, telemetry consent or training consent.

Personalization is not a quality metric. Product success must eventually be tested
against Human Review Time, Human Correction Time, Decision Count and Revert Count.
This task adds no review queue, automatic gate, metric threshold, or claim that more
personalized edits are better.

## Verification receipts

All synthetic observations, catalog identities and approvals are TEST_ONLY_SUPPORT.
They do not qualify native reads, mutations, identity authenticity or learning quality.

Environment: existing vs001e-validation-env; PYTHONPATH/MYPYPATH=src;tests;
PYTHONDONTWRITEBYTECODE=1.

| Check | Result |
| --- | --- |
| `python -m pytest -q -p no:cacheprovider tests/test_reference_style.py` | 73 passed, 0 failed |
| `python -m pytest -q -p no:cacheprovider` | 1600 passed, 0 failed, 1 skipped |
| `python -m ruff check .` | All checks passed |
| `python -m mypy` | Existing strict configuration: 36 source files passed |
| `python -m mypy --strict --follow-untyped-imports --explicit-package-bases src/davinci_ai_editor/reference_style.py tests/test_reference_style.py` | 2 explicit new Python files passed |
| Existing tracked-file diff and exact new-file allowlist | PASS: only the three declared new files |
| Whitespace / final newline | PASS: no diagnostics. New-file `git diff --no-index --check -- NUL <file>` exit 1 means expected "files differ", not whitespace failure |

The existing skip is tests/test_naive_inv001.py:27, an opt-in intentional red test;
its normal regression runs. The full count is based on main, not the unmerged
VS-001I integration tests.

Coverage includes all six reference statuses, complete/incomplete PREVIOUS,
multiple/missing predecessor and anchor context, stale alias/revision/catalog,
pinned historical revisions, locator/title/order independence, memory-only proposals,
source retention, precedence/ties/defaults, hard constraints and unavailable support,
modification scope, selective inheritance, all knowledge states and missing evidence,
rendered hidden-decision rejection, explicit delta approval/stale rejection,
immutable old contexts, contrary evidence, and AST/import/type separation.

## Open dependencies and decision

- Catalog identity/access/provenance authentication, completeness and ordering producers.
- Actual read-only reference analysis and evidence calibration.
- Relative-style baseline interpretation and any target-specific proposal policy.
- Team policy governance and authority of profile approvers.
- Feedback attribution/generalization, OPEN-010 episode semantics and consent.
- Profile persistence/version allocation, concurrent approval/publication and scope enforcement.
- OPEN-002/008 and existing native currentness/identity/atomicity dependencies.

Contract mismatch requiring existing semantic changes: **none**. Descriptor-to-target
preference/geometry conversion and durable profile updates are deliberately outside
this foundation, not claimed implementations.

Next recommended task: Chat review of these contracts and receipts. Only after
approval should a separate task select any proposal-policy or persistence integration.
Stop before commit/push.
