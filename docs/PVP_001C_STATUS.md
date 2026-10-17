# PVP-001C — Derived cut-candidate geometry from silence regions

## Verdict and qualification

**CODE_COMPLETE / TEST_ONLY_SUPPORT.** Pure, stdlib-only integer geometry over
hand-built boolean sequences and `FrameRange` regions. No real media, no PCM, no
Resolve, no calibration data was opened or used.

- Base: authoritative main `7949c8b7fcb1a17fa612a6cd4279de6f3b245031`.
- Branch: `wip/pvp-001c-cut-geometry`.

## Purpose

Given raw SILENCE_REGION frame ranges inside an analysis window, derive a
separate, explicitly-derived geometry artifact showing where a cut *candidate's*
interior would lie after keep handles, short-gap bridging and a minimum-length
filter. Every transformation is listed per source region. The raw regions are
never modified.

## Changed files

1. `src/davinci_ai_editor/pause_cut_geometry.py`
2. `tests/test_pause_cut_geometry.py`
3. `licenses/auto-editor-LICENSE.txt`
4. `docs/PVP_001C_STATUS.md`

No existing module, dependency or configuration changed.

## Layer 1 — ported auto-editor algorithm

Adapted from auto-editor `src/lib/editutil.nim` (`mutMargin`, `smoothing`) and
the order in `src/conductor.nim` (margin first, then smoothing on the binary
active mask). auto-editor is Unlicense (public domain); its license text is in
`licenses/auto-editor-LICENSE.txt`.

| Function | Port of | Semantics kept |
| --- | --- | --- |
| `apply_margin(active, start_margin_frames, end_margin_frames)` | `mutMargin` | Transitions found once on the input; positive start margin activates frames before each inactive→active edge, negative shrinks the active run's head; positive end margin activates frames after each active→inactive edge, negative shrinks the run's tail; start margins applied before end margins; sequence edges are not transitions; clamping at bounds. |
| `smooth_runs(active, min_cut_frames, min_clip_frames)` | `smoothing` | Each iteration reads the previous state: active runs `< minclip` → inactive, inactive runs `< mincut` → active, edge runs included (with the `+1` inclusive-length edge rule); fixed-point loop with the "two states back" 2-cycle guard. |

### Intentional differences

1. Pure: input copied, new `tuple[bool, ...]` returned (auto-editor mutates in place).
2. Integer frames only; no seconds, no `toTb` rounding, no default arguments.
3. Strict types: elements must be `bool`; counts must be `int` (`bool` rejected).
4. `smooth_runs` refuses negative thresholds (auto-editor: silent no-op).
5. `smooth_runs` raises `RuntimeError` after `4*len+8` iterations instead of
   looping forever should a longer-than-2 cycle exist. Exhaustive checks
   (all sequences of length ≤ 12, thresholds 0–4) never reach the bound.

## Layer 2 — project contract

- `CutGeometryPolicy(head_keep_frames, tail_keep_frames, max_bridge_frames, min_cut_frames)`:
  frozen, ints ≥ 0, bool rejected, deterministic `policy_ref`
  (`cut-geometry-policy:` + SHA-256 of the canonical JSON values and derivation).
- `bridge_short_active_gaps(regions, window, max_bridge_frames)`: one ordered
  left-to-right pass; joins the next region when the gap from the current group's
  last member is `≤ max_bridge_frames`; returns `BridgedGroup(members, span,
  bridged)` listing every bridged gap. Bridged frames were non-silent; no claim is
  made that they are not speech.
- `derive_cut_candidate_geometry(regions, window, policy) -> CutGeometryResult`:
  1. Handles: head kept unless the region touches the window start, tail kept
     unless it touches the window end (`clamped_at_window_start/end`). Empty
     remainder → `DroppedRegion(DROPPED_EMPTY_AFTER_HANDLES)`.
  2. Bridging of surviving interiors (single pass). Later members become
     `DroppedRegion(MERGED_INTO_PRECEDING_SPAN, merged_into=<first source>)`; the
     first yields `DerivedCutSpan` with `merged_regions`, `bridged` (gaps between
     interiors, including re-absorbed handles) and `bridged_active` (raw non-silent
     frames).
  3. Groups whose joined interior `< min_cut_frames` → every member
     `DroppedRegion(DROPPED_TOO_SHORT)`.
- Inputs must be `FrameRange`s inside the window, ordered, nonoverlapping and
  non-touching (maximal runs); otherwise `ValueError`/`TypeError`.
- `CutGeometryResult` carries one outcome per source region in input order, the
  untouched `source_regions`, `policy`, `policy_ref`,
  `derivation="PVP-001C-geometry-v1"` and the fixed `authorization`
  statement `AUTHORIZATION_STATEMENT`; all are validated in `__post_init__`.

### Mapping to auto-editor and proven equivalence

| Contract | auto-editor |
| --- | --- |
| `head_keep_frames` | end margin (`margin[1]`) |
| `tail_keep_frames` | start margin (`margin[0]`) |
| `min_cut_frames` | `mincut` |
| `max_bridge_frames` | `minclip - 1` |

Exhaustive tests over all boolean sequences of length 1–10 (window offset 100):

- Margin ≡ keep handles: contract == `apply_margin(a, tail, head)` for six handle pairs.
- min_cut ≡ mincut: contract == `smooth_runs(apply_margin(a, tail, head), cut, 0)`.
- Bridge ≡ minclip: contract == `smooth_runs(apply_margin(a, tail, head), 0, bridge + 1)`
  for every sequence where auto-editor's edge-run minclip rule does not fire.

Documented contract differences: active runs touching the window edges are never
bridged (their length beyond the window is unknown); with both `max_bridge_frames`
and `min_cut_frames` nonzero the sequential contract is not claimed equivalent to
auto-editor's simultaneous fixed-point smoothing.

## What this does NOT authorize

- No edit action (no REMOVE/TIGHTEN), no cut decision, no ContentMode, no
  semantic or speech label. Silence ≠ editorial meaning; non-silence ≠ speech.
- No change to raw SILENCE_REGION evidence; the result is a separate derived artifact.
- No calibration. auto-editor's defaults (margin 0.2s, mincut 0.2s, minclip 0.1s)
  are **not** adopted; policies are explicit, uncalibrated caller inputs.
- No execution, transaction, Resolve or real-media qualification.

## Validation

Python 3.11 venv, `PYTHONPATH=<worktree>/src`, pytest with
`-p no:cacheprovider --basetemp=<fresh scratch dir>`.

| Command | Result |
| --- | --- |
| `python -m pytest -q tests/test_pause_cut_geometry.py` | 33 passed |
| `python -m pytest -q` | 2143 passed, 2 skipped (pre-existing host/opt-in skips) |
| `python -m ruff check src tests tools` | All checks passed |
| `python -m ruff format --check <new files>` | already formatted |
| `python -m mypy` | no issues (42 files) |
| `python -m mypy --strict --explicit-package-bases <new src> <new test>` | no issues |
| `git diff --check` | clean |

## Provenance

- auto-editor (`oss/auto-editor-master_1/auto-editor-master`), files read only:
  `src/lib/editutil.nim`, `src/conductor.nim`, `src/cli.nim`, `src/edit.nim`,
  `LICENSE` (Unlicense). Nothing was executed, imported or installed.
- Attribution comments in `pause_cut_geometry.py`: "Adapted from auto-editor
  src/lib/editutil.nim (Unlicense)" and "Adapted from auto-editor
  src/conductor.nim (Unlicense)".
