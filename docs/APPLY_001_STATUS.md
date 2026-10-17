# APPLY-001 — Marker Approval in the NLE → Approved Cuts on a New Expected Timeline

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Nothing here has been exercised against DaVinci Resolve. In the tests, every
"editor" action is a text edit of our own writer output.

## Base and boundary

- Base: RT/VER follow-up commit on `wip/apply-001-approved-cuts` (stacked on
  HANDOFF-001 → RT-001 → VER-001), not pushed.

Files:

1. `src/davinci_ai_editor/candidate_markers.py` (new) — candidate tokens,
   marker writing, `read_marker_selections`
2. `src/davinci_ai_editor/apply_cuts.py` (new) — `build_apply_confirmation`,
   `apply_approved_cuts`
3. `src/davinci_ai_editor/xmeml_writer.py` (changed) — FCP7 A/V `<link>` groups
4. `tests/test_apply_001.py` (new)
5. `docs/APPLY_001_STATUS.md` (new), `docs/HANDOFF_001_STATUS.md` (one line)

Zero runtime dependencies. No rendering anywhere, no media access, no Resolve
API. Every generated file is an Expected artifact. Importing it into Resolve is
a manual user action.

## Product flow

1. We hand off a timeline with candidate markers (`attach_candidate_markers`,
   then `write_xmeml`; FCP7 XML is the default format).
2. The editor imports it by hand and approves or rejects each candidate inside
   Resolve by renaming the marker.
3. The editor exports the timeline (FCP7 XML) and we read it back
   (`read_xmeml` → `ReimportedTimeline`, `diff_xmeml_roundtrip`).
4. `read_marker_selections` gives the **selection**. `build_apply_confirmation`
   gives the **confirmation** summary and digest.
5. The user confirms explicitly: `apply_approved_cuts(confirmation,
   confirmed_digest=…)`. This is the **approval**. The result is a **new**
   Expected timeline (`<name> AIE v2`). Since LAYER-001 the cuts follow a
   per-track policy (dialogue source tracks are cut, every other track only
   ripples, nothing spanning a cut is split), all tracks and unmodelled items
   are preserved, A/V stays linked, and the remaining candidates stay as
   markers. See `docs/LAYER_001_STATUS.md`.
6. The editor imports the new file by hand and renders only the final version
   in Resolve Deliver. VER-001 on the next round trip is the **verification**.

The four axes stay separate (ADR-015, `docs/CANDIDATE_AUTHORITY.md`):
`MarkerSelectionSet.axis = "SELECTION"`; `ApplyConfirmation.authorizes_apply =
False`; approval happens only when the digest is echoed back;
`AppliedTimeline.verified = False`.

## Editor workflow in Resolve (marker rename convention)

Each candidate marker is written on the clip of the first video track
(`Video 1`) that contains the candidate:

- Name: `AIE-0012 ?` (pending). Note/comment: `candidate=AIE-0012; reason=<short reason>`.
- To **approve**, rename it to `AIE-0012 OK` (or `AIE-0012 승인`).
- To **reject**, rename it to `AIE-0012 X` (or `AIE-0012 제외`).
- To **decide later**, leave it as `AIE-0012 ?`.
- Matching ignores case (`aie-0012 ok` works). Keep the token and change only
  the word after it. Do not move, copy or delete the marker.

Marker colour is a secondary signal only, and only where the format carries
it. OTIO `Marker.2` carries colour; FCP7 xmeml markers do not. GREEN means
approve and RED means reject; other colours are neutral. Colour alone never
approves. A colour that contradicts the name makes the candidate UNKNOWN; this
includes `?` with GREEN.

The candidate becomes **UNKNOWN** and is never applied when:

- the token is missing;
- the token appears more than once (duplicated);
- the name is malformed (any word outside the vocabulary, or extra words);
- the name and colour conflict;
- the marker moved by even one frame from the Expected candidate (stale). This
  includes a change of media or of anchor track.

Movement is measured in the media-relative frames of the clip that carries the
marker. If the editor ripples something elsewhere and the clip shifts on the
timeline, the candidate is not stale. The cut is applied where that content
sits now in the Actual (Human Edit Wins). Tokens found in the Actual that we
never issued are reported (`unexpected_tokens`) and ignored.

## Confirmation (`build_apply_confirmation(selection, expected, diff)`)

The function refuses (`ValueError`) when the RT-001 diff is not bound to this
Expected digest, or when the diff and the selection refer to different Actual
digests. Stale inputs never reach an apply.

Skip reasons:

| code | meaning |
|---|---|
| `UNKNOWN` | selection issue (MISSING / DUPLICATED / MALFORMED / COLOR_CONFLICT / MOVED) |
| `REJECTED` | editor rejected |
| `PENDING` | editor left it undecided |
| `HUMAN_EDIT_LOCKED` | the cut overlaps an RT-001 HARD_LOCK (a human edit or UNKNOWN region) on any track; a whole-UNKNOWN diff locks everything |
| `MARKER_CONFLICT` | the cut range overlaps another marker (a human marker or another candidate); markers are never silently destroyed |

Locks come from `derive_human_edit_protection`, with one exception. A change
whose only difference is on `AIE-` candidate markers (a rename, or a dragged
candidate marker) is not counted as a content edit, because that is the
approval channel. Every other human change still locks, and that includes
markers the editor adds.

`ApplyConfirmation.summary` is deterministic text in Korean with English codes.
It shows the number of approved cuts, the total frames and seconds removed, one
line per cut, the skipped items with reasons, the HARD_LOCK regions that will
shift (they are not edited), and the digest. `confirmation_digest` is the
SHA-256 (canonical JSON) of exactly `{expected_digest, actual_digest,
approved_cuts}`. The dataclass recomputes it on construction, so a confirmation
whose cut set was altered cannot exist.

## Apply (`apply_approved_cuts(confirmation, *, confirmed_digest)`)

- The call raises `ApplyRefused` unless `confirmed_digest ==
  confirmation.confirmation_digest`.
- The cuts are applied to the **Actual** re-imported timeline, not to the old
  Expected. Superseded by LAYER-001: each approved range, in Actual timeline
  frames, is removed only from the tracks whose policy for that cut is
  `CUT_WITH_SOURCE`; `SHIFT_WITH_RIPPLE` tracks only move their later items
  left; `KEEP_IN_PLACE` tracks do not change (`docs/LAYER_001_STATUS.md`). On
  CUT tracks clips are split as needed with a 1:1 source cut. Gaps shrink,
  adjacent gaps merge and trailing gaps are dropped.
- The output is a ripple displacement per moved clip piece, following the
  project's `domain.RippleDisplacement` semantics (as in
  `safety.propose_ripple_displacements`):
  - `track_id` is the Actual track name;
  - `original_range` is the piece in Actual coordinates;
  - `delta_frames` is negative.

  Nothing moves implicitly.
- Markers inside surviving pieces are kept unchanged. That covers pending,
  rejected, skipped-approved and human markers. The applied candidate's own
  marker leaves with its content. `remaining_candidate_ids` lists the tokens
  still present.
- The result is an `AppliedTimeline`:
  - `artifact_kind = EXPECTED_TIMELINE_ARTIFACT`, `authorizes_import = False`,
    `verified = False`, `approval = EXPLICIT_CONFIRMATION_DIGEST`;
  - `revision` (a content-addressed `PreparedArtifactRevision`) feeds VER-001.

## A/V links (xmeml writer)

A video clipitem forms one link group with the audio clipitems that share its
media ID, timeline range and source range. Every member writes one `<link>`
per member, itself included, containing:

- `linkclipref`
- `mediatype`
- `trackindex` (1-based within the media kind)
- `clipindex` (1-based position in the track)
- `groupindex` 1 (audio only)

A group with more than one matching video clip is ambiguous and is not linked.
The layout is adapted from timeline (Chat Octopus) `src/xmeml/writer.ts`
`writeLinkEntries`, MIT, `licenses/timeline-LICENSE.txt`; it was read only,
and no code was executed or copied verbatim. The reader already ignores
`<link>`, so links do not affect diffs. Whether Resolve honours these links on
import is UNVERIFIED.

## Limits (tell the editor)

- **Import creates a new timeline.** Grades, effects, titles, retimes and other
  work done on the old timeline do not carry over to `… AIE v2`. **Approve
  cuts before finishing work** (grading, mixing, effects) on the timeline.
- Only cut candidates that lie inside one clip of `Video 1` can be marked.
- ~~Cuts remove the same frames from every track, music beds and B-roll
  included.~~ Fixed by LAYER-001: per-track policy; music beds, B-roll, titles
  and SFX are not cut by default (`docs/LAYER_001_STATUS.md`).
- RT-001 locks MOVED clips conservatively. After a ripple trim by the editor,
  every downstream clip is locked, so its candidates are skipped as
  `HUMAN_EDIT_LOCKED`. A non-ripple trim (which leaves a gap) locks only the
  trimmed clip.
- FCP7 marker colours do not survive; on xmeml the name is the only signal.
- The source in/out convention (0-based vs media timecode) on Resolve export is
  still UNVERIFIED (RT-001), and so is Resolve's handling of `<link>`.

## What it does NOT authorize

- No import, no Resolve API call, no UI automation, no render. The user imports
  the file and renders only the final version in Resolve Deliver.
- A selection or a confirmation is never an approval. Only the echoed digest
  is. Positive feedback ("좋다") is not an approval.
- No auto-apply of stale input. A changed Expected, Actual or cut set changes
  the digest, and the confirmation refuses mismatched bindings.
- Applying produces an unverified Expected artifact. It is not VERIFIED and
  not PROMOTED. VER-001 on the next round trip is still required, and that is
  `FILE_ROUNDTRIP` evidence, never native.
- Not wired into orchestration, candidate authority or promotion.

## Tests (`tests/test_apply_001.py`)

The end-to-end test runs the full chain on synthetic data:

1. Build an Expected with 7 candidates and write it as FCP7 XML.
2. Hand-edit the marker names: approve 2, reject 1, leave 1 pending, 1
   malformed, 1 moved, and 1 approved inside a human trim (B tail trimmed on V1
   and A1).
3. Read the export back, take the selection and build the confirmation. Check
   the summary, the skip reasons including `HUMAN_EDIT_LOCKED`, and the
   shifted locks.
4. Apply with a wrong digest (refused), then with the right digest.
5. Write the new XML and parse it back. Check that video and audio are cut at
   identical frames, the ripple is correct, the links are present, the
   remaining markers are present, and the displacements are as expected.
6. Run VER-001 on a simulated re-export with renumbered clipitem ids. The
   result is **MATCH**.

Other tests cover:

- determinism;
- refusal of stale bindings;
- that the digest binds the cut set;
- the name vocabulary (12 cases);
- colour as a secondary signal (OTIO);
- duplicated, missing and unexpected tokens;
- a marker added by the editor (locked) vs an existing marker (`MARKER_CONFLICT`);
- a whole-UNKNOWN diff locking every cut;
- the OTIO round trip with STRONG identity;
- attach refusals;
- version naming;
- writer links.

## Validation

Python 3.12.10 `.venv` with `PYTHONPATH=<worktree>/src` (import path verified
inside this worktree); CI target 3.11, no 3.12-only syntax.

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_apply_001.py   26 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                          2280 passed, 2 skipped
python -m ruff check src tests tools                                                  All checks passed
python -m ruff format --check <changed .py files>                                     already formatted
python -m mypy                                                                        Success, 51 source files
MYPYPATH=tests python -m mypy --strict --explicit-package-bases <new/changed files>   Success
git diff --check                                                                      clean
```

## Open questions

- **Safety alignment for shifting HARD_LOCK content.** `safety.preflight`
  (native path) rejects a ripple that changes a HARD_LOCK position. APPLY-001
  never cuts into a lock, but it does shift locked content that comes after an
  approved cut. Each such shift is listed in the summary and bound by the
  digest. Should this instead skip every cut that sits upstream of a lock?
- Should a ripple trim made by a human exempt downstream MOVED clips from
  locking (RT-001 open question)? Without that exemption, candidates after a
  ripple trim cannot be applied.
- Should colour-only approval (GREEN with `?`) ever count, for example as an
  OTIO-only opt-in? It is currently a conflict.
- Should the anchor be configurable (a track other than `Video 1`, or
  sequence-level markers, which the xmeml reader currently reports without
  modelling)?
