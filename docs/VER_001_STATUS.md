# VER-001 — Plan-vs-Actual Verification Report (File Round-Trip)

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Evidence class: `FILE_ROUNDTRIP` — explicitly not native evidence and not
VERIFIED_LIVE. A report never satisfies a Safety gate, never promotes a
candidate and never replaces native postflight verification.

## Base and boundary

- Base: RT-001 commit on `wip/rt-001-roundtrip-diff` (stacked on HANDOFF-001
  `e80f46e7928d79e1e6c43fcf1a3a8a35ae935516`), not pushed.

Files added (no existing file modified):

1. `src/davinci_ai_editor/roundtrip_verification.py`
2. `tests/test_roundtrip_verification.py`
3. `docs/VER_001_STATUS.md`

## API

`verify_roundtrip(approved, expected, diff, *, provenance, baseline=None, acknowledged_change_ids=()) -> VerificationReport`

- `approved` is a `trust_evidence.PreparedArtifactRevision` of the Expected
  `HandoffTimeline`. Approval, Expected and the RT-001 diff must share one
  content digest, else `ValueError` (stale plans are never verified). A
  baseline diff must be bound to the same Expected.
- The intended cut list is `intended_cut_list(expected)`: every clip
  (`E:<KIND>:<n>:<index>`, equal to RT-001 change IDs) and every gap
  (`G:…`) in Expected coordinates.

Per-item status: `MATCH`, `MISSING_CUT` (removed, merged-away cut point,
replaced, or clip disabled), `EXTRA_CUT` (split, added clip, gap filled, or
disabled clip enabled), `FRAME_DRIFT` (timeline/source deltas; exact, no
tolerance; `delta` = timeline start shift), `MARKER_LOST` (an Expected marker
— range, name, note — missing in Actual; colors are not compared because
xmeml cannot carry them), `TRACK_FLATTENED` (cross-track move while Actual has
fewer tracks of that kind; gaps on a vanished track), `HUMAN_CHANGED`,
`UNKNOWN`. Every item records `observed` (the geometry code), `attribution`,
`basis`, ranges, RT-001 change IDs and identity strength.

Overall: any UNKNOWN item, any UNSUPPORTED region or a whole-UNKNOWN diff →
`UNVERIFIED` (never MATCH); else any defect → `MISMATCH`; else `MATCH`.
HUMAN_CHANGED is not an error (`human_changed_count`).

## Human change vs handoff loss

Only explicit evidence decides; otherwise the item is UNKNOWN:

| provenance | evidence | result |
|---|---|---|
| `IMMEDIATE_REEXPORT` (user declared no hand edits) | — | defect, `HANDOFF_LOSS`, `USER_DECLARED_NO_EDITS` |
| `AFTER_HUMAN_EDIT` | baseline (immediate re-export) shows MATCH | `HUMAN_CHANGED`, `BASELINE_REEXPORT` |
| `AFTER_HUMAN_EDIT` | baseline shows the same discrepancy | defect, `HANDOFF_LOSS` |
| `AFTER_HUMAN_EDIT` | baseline differs otherwise / UNKNOWN | `UNKNOWN` |
| `AFTER_HUMAN_EDIT`, no baseline | all change IDs acknowledged by the user | `HUMAN_CHANGED`, `USER_ACKNOWLEDGED` |
| otherwise (incl. provenance `UNKNOWN`) | — | `UNKNOWN` |

Actual-only extra clips are matched against the baseline by track, media id,
source range and observed code. A user declaration or acknowledgement is
recorded as its basis; it is not proof and is never upgraded to native
evidence.

## Render

`render_report(report, *, korean=False)` produces deterministic plain text for
a review UI: evidence line ("FILE_ROUNDTRIP (file round-trip; not native, not
live)"), overall status, artifact ref + digests, provenance, human change
count, reasons, and one line per item. Codes stay English; `korean=True`
appends labels (e.g. `FRAME_DRIFT (프레임 어긋남)`).

## Tests

Exact match; 1-frame drift; lost marker; lost cut (merge); extra cut (split,
added clip, gap filled); track flattening; transition → UNVERIFIED; rate
change and unreadable file → UNVERIFIED; human change vs loss with baseline
(deleted clip HUMAN_CHANGED, marker loss HANDOFF_LOSS, added clip
HUMAN_CHANGED); no evidence → UNKNOWN / acknowledged → HUMAN_CHANGED; stale
approval / mismatched Expected / foreign baseline refused; deterministic
render and digest.

## Validation

Python 3.12.10 `.venv` with `PYTHONPATH=<worktree>/src` (import path verified
inside this worktree); CI target 3.11, no 3.12-only syntax.

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_roundtrip_verification.py   13 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                                       2246 passed, 2 skipped
python -m ruff check src tests tools                                                               All checks passed
python -m ruff format --check <7 RT-001/VER-001 .py files>                                         already formatted
python -m mypy                                                                                     Success, 49 source files
MYPYPATH=tests python -m mypy --strict --explicit-package-bases <3 new src> <3 new tests> tests/support/roundtrip_fixtures.py   Success, 7 files
git diff --check                                                                                   clean
```

## Identity rule for MATCH (follow-up decision 3, user-approved)

An item may be MATCH only with STRONG identity (OTIO metadata), or with WEAK
identity (xmeml display name + path, or OTIO path fallback) that is unique.
WEAK identity is unique when no *other* clip of the same track kind, in the
Expected or in the Actual, has the same media path **with an overlapping
source range** (the WEAK key is path + source range, the same key the RT-001
matcher uses). Otherwise the item is `UNKNOWN` with detail
`IDENTITY_AMBIGUOUS`, the report gets reason `IDENTITY_AMBIGUOUS` and the
overall status is `UNVERIFIED` (never MATCH). Example: a dual-mono export with
the same file and range on A1 and A2 is ambiguous over FCP7 XML; the same
timeline over OTIO with metadata (STRONG) can be MATCH.

Interpretation note: same-path clips with disjoint source ranges (every
ordinary cut of one interview file, and every split APPLY-001 produces) are
distinguishable by source range and stay unique. Requiring a globally unique
path would make FCP7 XML (the default format) unable to ever report MATCH for
a timeline that uses one source file twice; that reading is recorded as an
open question rather than implemented.

## Limits and open questions

- The baseline approach needs the editor to export once right after import;
  the review UI must ask for that file (or for acknowledgements).
- Open: whether WEAK uniqueness should be the stricter "no other clip with the
  same path at all" (see the interpretation note above).
- Gap items may double-report a drift already reported on the neighbouring
  clip (by design: the cut list is verified item by item).
- Not wired into orchestration, candidate authority or promotion.
- LAYER-001 adds layer items (track set/state, pass-through presence:
  `LAYER_LOST`, `LAYER_ADDED`, `TRACK_STATE_CHANGED`); see
  `docs/LAYER_001_STATUS.md`.
