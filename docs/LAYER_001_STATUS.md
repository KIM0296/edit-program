# LAYER-001 — Per-Track Edit Policy and Layer Preservation

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Nothing here has been run against DaVinci Resolve. Every "editor" action in the
tests is a text edit of our own writer output.

## Product rule (Free and Studio)

Layers are never merged. Every track (layer) is kept until the final render,
and each track is edited on its own.

Before this change, APPLY-001 removed each approved range from every video and
audio track at the same frames. That cut music beds, B-roll, titles and
graphics at the dialogue cut points. On top of that, the Free file path could
drop track items that the xmeml reader does not model.

## Base and boundary

- Base: APPLY-001 branch `e5591838ac5d740d60f3c80d6d7f5027c3f9f3a3` (HANDOFF-001
  → RT-001 → VER-001 → RT/VER follow-ups → APPLY-001), branch
  `wip/layer-001-per-track`. Not pushed.
- Zero runtime dependencies (stdlib `xml.etree`). Frozen dataclasses. str-Enums
  have `UNKNOWN`. No rendering, no media access, no Resolve API.

Files:

| file | change |
|---|---|
| `src/davinci_ai_editor/layer_policy.py` | new: policies, conflict checks, per-track apply, layer comparison |
| `src/davinci_ai_editor/layer_xml.py` | new: canonical raw subtree helpers (capture, shift, 1:1 cut, emit) |
| `src/davinci_ai_editor/handoff_model.py` | `PassthroughItem`, `LayerItemKind`; `HandoffTrack.passthrough/enabled/locked/attributes/extra_xml`; `ReimportedTimeline.unpreserved`; `SequenceMarker` + `markers` on both timelines; `HandoffClip.source_track`, `link_group`; diagnostic codes `LAYER_LOSS_RISK`, `LINK_NOT_PRESERVED` |
| `src/davinci_ai_editor/xmeml_reader.py` | captures every unplaced track child verbatim; reads track flags, attributes and settings, sequence markers, `<link>` groups and `<sourcetrack>` |
| `src/davinci_ai_editor/xmeml_writer.py` | re-emits pass-through items, track flags, attributes and settings; refuses inconsistent items |
| `src/davinci_ai_editor/otio_json.py` | writer refuses layer state it cannot carry (`LAYER_LOSS_RISK`) |
| `src/davinci_ai_editor/apply_cuts.py` | per-track policy, overrides, new skip reasons, per-track effects in the summary and the digest |
| `src/davinci_ai_editor/roundtrip_diff.py` | `layer_findings`; pass-through-explained regions are no longer UNKNOWN; layer changes are locked |
| `src/davinci_ai_editor/roundtrip_verification.py` | layer items `LAYER_LOST`, `LAYER_ADDED`, `TRACK_STATE_CHANGED` |
| `tests/test_layer_001.py` | new (21 tests) |

## Per-track policy

`TrackEditPolicy`:

- `CUT_WITH_SOURCE`: the approved range is removed from this track. Clips are
  split 1:1 and later items ripple left.
- `SHIFT_WITH_RIPPLE`: nothing on the track is cut. Items entirely after the
  cut move left by the removed duration; items entirely before it stay put.
- `KEEP_IN_PLACE`: nothing on the track is cut or moved.
- `UNKNOWN`: never applied.

**Default, set for each approved cut.** A track is `CUT_WITH_SOURCE` when the
items on it that cover the cut range all come from the candidate's source
media, or belong to the candidate clip's file `<link>` group. Those are the
dialogue clip and its linked A/V, including separate-recorder audio that the
file links to the camera clip. The candidate is the `Video 1` clip carrying
the marker. Every other track is
`SHIFT_WITH_RIPPLE`. A track with nothing in the range is also SHIFT (an empty
range just collapses). `KEEP_IN_PLACE` is never a default.

**Overrides.** `build_apply_confirmation(..., track_overrides=(TrackPolicyOverride("Audio 3", CUT_WITH_SOURCE),))`.
A track is named by its Actual track name (`Audio 3`) or label (`AUDIO:3`,
case-insensitive). An override applies to every cut. A reference that matches
no track or several tracks, a duplicate override and an `UNKNOWN` policy are
all refused with `ValueError`; nothing is guessed. Each `ApprovedCut` carries
one `TrackPolicyAssignment` per Actual track, with source `DEFAULT` or
`OVERRIDE`.

**Skip reasons (new).** Nothing is ever split, truncated or dropped
automatically:

| code | when |
|---|---|
| `LAYER_CONFLICT` | an item on a SHIFT or KEEP track spans or partly overlaps the removed range (a music bed or title running across the cut). The detail names the track and the item. Only an explicit `CUT_WITH_SOURCE` override for that track lets the cut through. |
| `LAYER_UNSUPPORTED_ITEM` | on a CUT track, a pass-through item lies in or spans the removed range and cannot be cut 1:1 (generator, transition, nested sequence, retimed or otherwise unmodelled clip); or a pass-through item with an UNKNOWN position sits on a track that has to change |

Order of checks for an approved selection: whole-UNKNOWN diff
(`HUMAN_EDIT_LOCKED`), then layer checks, then HARD_LOCKs, then
`MARKER_CONFLICT`. A HARD_LOCK blocks a cut only on tracks that rip for that
cut (CUT or SHIFT). A lock on a KEEP track does not block, because that track
is not touched. A lock whose track is UNKNOWN blocks.

**Warnings.** These are listed in the summary and bound by the digest:

- `SYNC_SHIFT`: a KEEP track sits next to rippling tracks. The warning lists
  the KEEP items after the cut that will no longer line up.
- `EFFECT_SPLIT_REVIEW`: a clipitem with `<filter>` effects is cut. Every
  piece keeps the filter elements verbatim, but keyframes may not line up.
- `MARKER_MOVED_TO_CUT`: a sequence (timeline) marker lies inside a removed
  range. It is kept, moved to the cut point, and never dropped.

**Confirmation.** The summary shows:

- for each approved cut, a `트랙 정책 / track policy` line (for example
  `Video 2=SHIFT, Audio 3=CUT(override)`);
- a `트랙별 결과 / per-track effect` block with one line per track: the
  policy (default or override) and the effect (`CUT` / `SHIFTED` /
  `UNCHANGED` / `CONFLICT`, the frames cut or shifted, and which candidates
  conflicted on that track);
- the warnings, and any `LAYER_LOSS_RISK`.

`confirmation_digest` uses schema `apply-001-confirmation-v3-layer-001`. It
binds:

- the Expected digest;
- `actual_binding_digest(actual)`, the Actual with every marker colour
  neutralized;
- the resolved `CandidateStatus` of every candidate (decision + issue, after
  name + colour resolution);
- the cut set with each cut's per-track policies;
- the per-track effects, the warnings and the loss risks.

The raw marker colour is not bound, only its resolved effect. The same
approvals therefore give the same digest whether or not the transport carries
colours; GREEN vs a neutral colour on an `OK` marker is tested. Other
transport differences in the Actual, if a transport has any, still change the
digest. A Studio (native) transport is not implemented here.

## Layer preservation in the Free file path

- **Tracks.** The output timeline has exactly the Actual tracks: same count,
  order, names, kinds, `enabled`/`locked` flags, XML attributes and
  settings children (e.g. `outputchannelindex`). An empty result track stays
  an empty track. `apply_approved_cuts` re-checks this as a postcondition, and
  also checks that every non-cuttable pass-through item survived with
  identical content. If either check fails it raises `ApplyRefused`
  (`LAYER_LOSS_RISK`).
- **xmeml pass-through.** The reader keeps, as a `PassthroughItem` on its
  track, every track child that is not placed as a modelled clip. That covers
  generator items (titles), transitions, nested sequences, clipitems with
  filters or speed changes, every item of a disabled or whole-UNKNOWN track,
  overlapped clipitems and unknown elements. The original `xml.etree` subtree
  is kept as a canonical string with these normalizations:
  - whitespace removed;
  - the root id removed, and nested ids renamed `n1…`;
  - `<file id=…/>` references inlined;
  - root `<link>` children removed; the link group is kept as `link_group`
    and rewritten by the writer.

  The writer re-emits the item verbatim. Only the root's `start`/`end` are
  rewritten when the item is shifted, and only `start`/`end`/`in`/`out`/
  `duration` plus the root's own markers when it is cut. The writer assigns
  fresh ids (`passthrough-N`, `pt-file-N`) so they cannot collide. On KEEP
  tracks items are untouched. The existing hardening is unchanged: input size
  cap, element cap, no ENTITY/DTD. `parse_raw` also refuses declarations.
- **1:1 cuttable pass-through.** A clipitem whose only unmodelled children are
  non-speed `<filter>` effects, with valid `start`/`end`/`in`/`out`
  (`out - in == end - start`), a resolvable file at the sequence rate,
  in-range markers and no overlap, carries a `source_range` and is cut like a
  modelled clip (`EFFECT_SPLIT_REVIEW`).
- **Links.** The reader reads FCP7 `<link>` groups among track items into
  `link_group` (connected components, named `L1`, `L2`, … in document order).
  Dangling references are ignored. Groups are kept on modelled clips and on
  pass-through items.
  - The writer re-maps every group to the new element ids (`clipitem-N` /
    `passthrough-N`, with `clipindex` counting all track items).
  - When a linked item is split, its pieces get the group suffix `.k`, where k
    is the number of approved cuts before the piece. Piece k of the video
    therefore stays linked with piece k of its audio, and unsplit items keep
    their group.
  - Only a group whose other end is gone (a single surviving member) is
    written unlinked, with a `LINK_NOT_PRESERVED` warning.
  - Clips without a file group are still linked by the APPLY-001 rule (same
    media, timeline range and source range).
  - `link_group` is relationship evidence, not identity, so it is excluded
    from equality.
- **Sequence (timeline) markers.** These are kept verbatim as
  `ReimportedTimeline.markers` / `HandoffTimeline.markers` (`SequenceMarker`:
  timeline range, name, canonical `<marker>` subtree) and re-emitted by the
  writer.
  - Apply ripples them with the timeline over every approved cut: a frame
    inside a removed range maps to the cut point. A marker inside a removed
    range is therefore moved to the cut point (and becomes one frame if it
    collapses) and flagged `MARKER_MOVED_TO_CUT`; it is never dropped.
  - Only the marker's `in`/`out` are rewritten, and a point marker keeps its
    `-1` out.
  - Sequence-marker changes do not create HARD_LOCKs: they are not track
    content.
- **Stereo channels.** FCP7 `<sourcetrack>` (mediatype + trackindex) is read
  into `HandoffClip.source_track` (`audio:2`) and written back.
- **OTIO (decision: refuse).** The OTIO reader already refuses unknown
  schemas, so an OTIO Actual never carries items that are not modelled. The
  OTIO writer refuses (`LAYER_LOSS_RISK`) any timeline whose tracks carry
  pass-through items or track state its subset cannot represent. That includes
  sequence markers and `source_track`. Link groups only produce a
  `LINK_NOT_PRESERVED` warning, because OTIO never carried links. Preserving
  raw OTIO objects is not implemented.
- **Anything else that would be lost.** A malformed sequence marker (no
  usable `in`) is listed in `ReimportedTimeline.unpreserved` and shown as
  `LAYER_LOSS_RISK` in the confirmation, and `apply_approved_cuts` raises
  `ApplyRefused("LAYER_LOSS_RISK: …")`. No file is emitted that silently
  lacks a layer item.

## RT-001 / VER-001 extension

`RoundTripDiff.layer_findings` comes from `compare_layers(expected, actual)`
and compares:

- tracks: `TRACK_MISSING`, `TRACK_ADDED`, `TRACK_STATE_CHANGED`;
- pass-through items (canonical equality): `MATCH`, `MOVED` (same content,
  new position), `CHANGED` (different content where it overlaps; UNKNOWN),
  `LOST`, `ADDED`;
- sequence markers (pseudo track `SEQUENCE_TRACK`; ids `M:SEQUENCE:i` /
  `MA:SEQUENCE:j`): `MATCH`, `MOVED` (same content, other `in`/`out`), `LOST`,
  `ADDED`.

VER-001 reports these as layer items:

- `L:<KIND>:<n>:<i>` and `LA:…` are pass-through items, `T:<KIND>:<n>` are
  tracks, and `M:`/`MA:` are sequence markers.
- MATCH means the item is present verbatim.
- An item moved by a delta other than the planned one is `FRAME_DRIFT`.
- A missing pass-through item or track is `LAYER_LOST`, and a missing
  sequence marker is `MARKER_LOST`. Both are defects (MISMATCH).
- An extra item is `LAYER_ADDED`. A flags or settings change is
  `TRACK_STATE_CHANGED`. Changed content is UNKNOWN (UNVERIFIED).
- An unreadable re-export is UNVERIFIED, as before.

Attribution follows the existing VER-001 rules. The existing per-clip items
check the CUT/SHIFT geometry of modelled clips against the applied Expected.

**Channel identity.** RT-001 and VER-001 use `<sourcetrack>` evidence:

- When two clips both carry `source_track` and it differs (for example the
  left vs right channel of one stereo file), they never correspond in RT-001.
- VER's WEAK identity key is path + source channel + source range.

A1/A2 from one interview file are therefore distinguishable, and the stereo
scenario reaches overall MATCH. Without `<sourcetrack>` evidence, same-path
same-range clips stay `IDENTITY_AMBIGUOUS` (RT/VER decision 3, tested).

The clip's index on the track is not used as identity evidence. Every clip
has a unique track and position, so using them would make the ambiguity rule
meaningless.

## Requires Chat Gate sign-off

**Loosened RT-001 rule: pass-through-explained regions are not UNKNOWN.** The
RT-001 contract says that anything touching an UNSUPPORTED region stays
UNKNOWN. LAYER-001 drops an UNSUPPORTED region from the diff only when all
three of these hold:

1. pass-through items cover the region completely;
2. every pass-through item in it is resolved as MATCH (canonical subtree
   identical to the Expected item at the same position), MOVED (identical
   content at another position) or ADDED (not in Expected);
3. no Expected modelled clip overlaps the region.

A region whose content changed (CHANGED), or which overlaps an Expected
modelled clip, stays UNKNOWN. MOVED, ADDED, CHANGED and LOST items and changed
track state are still HARD_LOCKed through `layer_findings` (Human Edit Wins).
The rule never makes AI edits touch such content. Locked items are only ever
shifted, exactly like any other HARD_LOCK after an approved cut.

Rationale:

- Without the rule, any timeline with a title, transition or effect clip
  would lock every cut forever. Real Resolve exports always contain such
  items, so the per-track policy could never be used.
- A verbatim comparison of the canonical subtree is exact evidence that the
  item is unchanged. Its semantics are still never interpreted, so a MATCH
  means "identical bytes after canonicalization", not "understood".
- The loosening is narrow: changed or overlapping content stays UNKNOWN, and
  every non-MATCH finding becomes a HARD_LOCK.

Until Chat signs off, this is a CODE_COMPLETE proposal, not an accepted
contract change.

## Tests (`tests/test_layer_001.py`, 21)

The synthetic timeline has:

- V1 interview;
- V2 B-roll clipitem with a colour filter (with keyframes);
- V3 title generatoritem;
- A1/A2 interview stereo from one file (`<sourcetrack>` audio 1/2), linked
  to V1;
- A3 music bed spanning both candidates;
- A4 SFX after the cut.

The end-to-end flow:

1. Read the editor's export, take Expected with pass-through, attach the
   candidates, write and approve them.
2. With the default policy, AIE-0001 is `LAYER_CONFLICT` (A3 music) and
   AIE-0002 is `LAYER_CONFLICT` (A3 and V3 title).
3. With the override A3=CUT, AIE-0001 is applied and AIE-0002 stays a
   conflict because of the V3 title.
4. The written XML is parsed back and checked:
   - V2 and A4 are shifted by exactly -30;
   - the V3 generator is verbatim apart from start/end, which moved to
     270–320;
   - the filter is verbatim;
   - V1, A1, A2 and A3 are cut at identical frames;
   - the V1 pieces are linked to A1 and A2 only;
   - there are 3 video and 4 audio tracks.
5. A simulated re-export renumbers the ids. VER reports overall **MATCH**,
   including the layer items.

Other tests cover:

- dual-mono without `<sourcetrack>` (`IDENTITY_AMBIGUOUS`);
- mono dialogue (MATCH);
- a lost title (`LAYER_LOST`); a title shifted by one frame (`FRAME_DRIFT`);
  an unreadable file (UNVERIFIED);
- a lost track (`LAYER_LOST`) and a locked track (`TRACK_STATE_CHANGED`);
- a cut filtered audio clip: filters stay on each piece, the clip is flagged
  `EFFECT_SPLIT_REVIEW`, and its links are re-mapped piece by piece;
- a retimed clip on a CUT track (`LAYER_UNSUPPORTED_ITEM`);
- a KEEP override (`SYNC_SHIFT`);
- override validation;
- sequence markers:
  - preserved and shifted, with one moved to the cut point
    (`MARKER_MOVED_TO_CUT`);
  - VER MATCH, and `MARKER_LOST` when one is dropped;
  - a malformed marker gives `LAYER_LOSS_RISK`;
- links:
  - file `<link>` groups make separate-recorder audio CUT together with the
    video, and the pieces stay linked;
  - unlinked recorder audio gives `LAYER_CONFLICT`;
  - a link with a missing end gives `LINK_NOT_PRESERVED`;
- the confirmation digest binds the resolved status, not the raw colour:
  GREEN and BLUE `OK` markers give equal digests, RED is UNKNOWN and gives a
  different digest;
- writer refusals;
- track flags, settings and empty tracks;
- model invariants;
- determinism.

## Limits (UNVERIFIED claims, tell the editor)

- **Free import still creates a new timeline.** Grades, Fusion, Fairlight
  automation and anything else that lives only in the Resolve project do not
  carry over to `… AIE v2`. Approve cuts before finishing work.
- **What we preserve verbatim** (in our written file):
  - generator and title items, transitions, nested-sequence clipitems;
  - clipitems with `<filter>` effects (parameters and keyframes), retimed
    clipitems, items on disabled tracks;
  - track flags, track XML attributes and settings children;
  - sequence markers;
  - `<sourcetrack>`;
  - `<link>` groups (re-mapped).
- **What Resolve may still drop or change (UNVERIFIED):**
  - whether Resolve's FCP7 import honours these elements at all, for example
    Resolve-native titles and Fusion generators exported as `generatoritem`,
    effects that have no FCP7 equivalent, colour grades (not in FCP7 XML),
    Fairlight effects, speed ramps, compound/nested clips, `<link>` groups,
    `<sourcetrack>` and sequence markers;
  - whether Resolve's FCP7 export writes them back in the same form.

  Anything Resolve changes on the next round trip shows up in VER as
  CHANGED/UNKNOWN, `LAYER_LOST` or `MARKER_LOST`; it is never reported as
  MATCH.
- Sequence-level settings that the writer does not emit (`<format>`/sample
  characteristics, audio outputs) are outside layer preservation. This is the
  unchanged HANDOFF-001 scope.
- A linked pair is written unlinked, with `LINK_NOT_PRESERVED`, when one
  member is split by a cut and the other is not (e.g. a J/L-cut whose audio
  does not cover the cut range).

## Validation

Python 3.12.10 `.venv` with `PYTHONPATH=<worktree>/src` (import path verified
inside this worktree); CI target 3.11, no 3.12-only syntax.

```text
python -m pytest -q tests/test_layer_001.py                                     21 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                    2301 passed, 2 skipped
python -m ruff check src tests tools                                            All checks passed
python -m ruff format --check <new/changed .py files>                           already formatted
python -m mypy                                                                  Success, 53 source files
MYPYPATH=tests python -m mypy --strict --explicit-package-bases <new/changed>   Success
git diff --check                                                                clean
```

## Open questions

- The loosened RT-001 region rule (see "Requires Chat Gate sign-off").
- Should sequence-marker changes made by a human (moved, added or removed
  timeline markers) ever create HARD_LOCKs? Today they are reported only.
- Should a J/L-cut linked partner that is not split be re-linked to the
  nearest piece instead of being written unlinked?
