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
| `src/davinci_ai_editor/handoff_model.py` | `PassthroughItem`, `LayerItemKind`; `HandoffTrack.passthrough/enabled/locked/attributes/extra_xml`; `ReimportedTimeline.unpreserved`; diagnostic codes `LAYER_LOSS_RISK`, `LINK_NOT_PRESERVED` |
| `src/davinci_ai_editor/xmeml_reader.py` | captures every unplaced track child verbatim; reads track flags, attributes and settings; lists sequence markers as `unpreserved` |
| `src/davinci_ai_editor/xmeml_writer.py` | re-emits pass-through items, track flags, attributes and settings; refuses inconsistent items |
| `src/davinci_ai_editor/otio_json.py` | writer refuses layer state it cannot carry (`LAYER_LOSS_RISK`) |
| `src/davinci_ai_editor/apply_cuts.py` | per-track policy, overrides, new skip reasons, per-track effects in the summary and the digest |
| `src/davinci_ai_editor/roundtrip_diff.py` | `layer_findings`; pass-through-explained regions are no longer UNKNOWN; layer changes are locked |
| `src/davinci_ai_editor/roundtrip_verification.py` | layer items `LAYER_LOST`, `LAYER_ADDED`, `TRACK_STATE_CHANGED` |
| `tests/test_layer_001.py` | new (16 tests) |

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
media. Those are the dialogue clip and its linked A/V; the candidate media is
the media of the `Video 1` clip carrying the marker. Every other track is
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
- `LINK_REVIEW`: a pass-through item in the Actual had `<link>` references.

**Confirmation.** The summary shows:

- for each approved cut, a `트랙 정책 / track policy` line (for example
  `Video 2=SHIFT, Audio 3=CUT(override)`);
- a `트랙별 결과 / per-track effect` block with one line per track: the
  policy (default or override) and the effect (`CUT` / `SHIFTED` /
  `UNCHANGED` / `CONFLICT`, the frames cut or shifted, and which candidates
  conflicted on that track);
- the warnings, and any `LAYER_LOSS_RISK`.

`confirmation_digest` uses schema `apply-001-confirmation-v2-layer-001`. It
binds the cut set together with each cut's per-track policies, the per-track
effects, the warnings and the loss risks.

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
  - root `<link>` children removed and counted.

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
- **Links.** A new file cannot keep `<link>` references to clipitem ids it
  does not write. The writer reports each affected item as a
  `LINK_NOT_PRESERVED` warning; this is not silent. Modelled clips are still
  linked by the APPLY-001 rule (same media, timeline range and source range).
- **OTIO (decision: refuse).** The OTIO reader already refuses unknown
  schemas, so an OTIO Actual never carries items that are not modelled. The
  OTIO writer refuses (`LAYER_LOSS_RISK`) any timeline whose tracks carry
  pass-through items or track state its subset cannot represent.
  Preserving raw OTIO objects is not implemented.
- **Anything else that would be lost.** Sequence-level markers are not
  modelled. They are listed in `ReimportedTimeline.unpreserved`, shown as
  `LAYER_LOSS_RISK` in the confirmation, and `apply_approved_cuts` raises
  `ApplyRefused("LAYER_LOSS_RISK: …")`. No file is emitted that silently
  lacks a layer item.

## RT-001 / VER-001 extension

`RoundTripDiff.layer_findings` comes from `compare_layers(expected, actual)`
and compares track by track:

- tracks: `TRACK_MISSING`, `TRACK_ADDED`, `TRACK_STATE_CHANGED`;
- pass-through items (canonical equality): `MATCH`, `MOVED` (same content,
  new position), `CHANGED` (different content where it overlaps; UNKNOWN),
  `LOST`, `ADDED`.

An UNSUPPORTED region that MATCH, MOVED or ADDED items fully explain is no
longer UNKNOWN. A region stays UNKNOWN when its content changed or when it
overlaps an Expected modelled clip. MOVED, ADDED, CHANGED and LOST items and
changed track state are HARD_LOCKed (Human Edit Wins).

VER-001 reports the layer items as follows:

- `L:<KIND>:<n>:<i>` and `LA:…` for pass-through items, `T:<KIND>:<n>` for
  tracks;
- MATCH means the item is present verbatim; moved by a different delta than
  planned is `FRAME_DRIFT`; missing item or track is `LAYER_LOST`, a defect
  (MISMATCH); extra is `LAYER_ADDED`; a flags or settings change is
  `TRACK_STATE_CHANGED`; changed content is UNKNOWN (UNVERIFIED);
- an unreadable re-export is UNVERIFIED, as before;
- attribution follows the existing VER-001 rules.

CUT and SHIFT geometry of modelled clips is checked by the existing per-clip
items against the applied Expected.

## Tests (`tests/test_layer_001.py`, 16)

The synthetic timeline has:

- V1 interview;
- V2 B-roll clipitem with a colour filter (with keyframes);
- V3 title generatoritem;
- A1/A2 interview stereo, linked to V1;
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
5. A simulated re-export renumbers the ids. VER reports every layer item as
   MATCH.

Other tests cover:

- layer verification with mono dialogue (overall VER MATCH);
- a lost title (`LAYER_LOST`, MISMATCH); a title shifted by one frame
  (`FRAME_DRIFT`); an unreadable file (UNVERIFIED);
- a lost track (`LAYER_LOST`) and a locked track (`TRACK_STATE_CHANGED`);
- a cut filtered audio clip: filters stay on each piece, the clip is flagged
  `EFFECT_SPLIT_REVIEW` and the writer emits `LINK_NOT_PRESERVED`;
- a retimed clip on a CUT track (`LAYER_UNSUPPORTED_ITEM`);
- a KEEP override (`SYNC_SHIFT`; the SFX is not moved);
- override validation;
- sequence markers (`LAYER_LOSS_RISK`; apply refused);
- writer refusals: OTIO, and xmeml with inconsistent timing;
- disabled/locked track flags, attributes and settings, and empty tracks,
  surviving a write and re-read without UNKNOWN regions;
- model invariants;
- determinism.

## Limits (UNVERIFIED claims, tell the editor)

- **Free import still creates a new timeline.** Grades, Fusion, Fairlight
  automation and anything else that lives only in the Resolve project do not
  carry over to `… AIE v2`. Approve cuts before finishing work.
- **What we preserve verbatim** (in our written file): generator and title
  items, transitions, nested-sequence clipitems, clipitems with `<filter>`
  effects (parameters and keyframes), retimed clipitems, items on disabled
  tracks, track flags, track XML attributes and settings children.
- **What Resolve may still drop or change (UNVERIFIED):**
  - whether Resolve's FCP7 import honours these elements at all, for example
    Resolve-native titles and Fusion generators exported as `generatoritem`,
    effects that have no FCP7 equivalent, colour grades (not in FCP7 XML),
    Fairlight effects, speed ramps, compound/nested clips, and `<link>`
    groups;
  - whether Resolve's FCP7 export writes them back in the same form.

  Anything Resolve changes on the next round trip shows up in VER as
  CHANGED/UNKNOWN or `LAYER_LOST`; it is never reported as MATCH.
- Sequence-level settings that the writer does not emit (`<format>`/sample
  characteristics, audio outputs) are outside layer preservation. This is the
  unchanged HANDOFF-001 scope.
- A1/A2 dual-mono from one file over FCP7 XML is WEAK-ambiguous by RT/VER
  decision 3, so VER on such a timeline is UNVERIFIED (`IDENTITY_AMBIGUOUS`),
  even when every layer item is MATCH. The end-to-end test asserts exactly
  that. The MATCH case is covered with mono dialogue.
- The default policy compares media IDs. Double-system audio (a separate
  recorder file linked to the camera clip) is not "same source media" and
  defaults to SHIFT. It is then a `LAYER_CONFLICT` until the user overrides
  it to CUT. `<link>` evidence is not read.

## Validation

Python 3.12.10 `.venv` with `PYTHONPATH=<worktree>/src` (import path verified
inside this worktree); CI target 3.11, no 3.12-only syntax.

```text
python -m pytest -q tests/test_layer_001.py tests/test_apply_001.py …           all passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                    2296 passed, 2 skipped
python -m ruff check src tests tools                                            All checks passed
python -m ruff format --check <new/changed .py files>                           already formatted
python -m mypy                                                                  Success, 53 source files
MYPYPATH=tests python -m mypy --strict --explicit-package-bases <new/changed>   Success
git diff --check                                                                clean
```

## Open questions

- Should sequence-level markers be preserved and shifted (rather than refusing
  with `LAYER_LOSS_RISK`)? Resolve timeline markers are common.
- Should the default policy also treat file-level `<link>` groups
  (double-system sound) as "linked A/V", which would require reading and
  re-writing link evidence?
- Should RT/VER distinguish dual-mono channels (FCP7 `<sourcetrack>`) so that
  stereo dialogue can reach MATCH over FCP7 XML?
- Pass-through regions explained by MATCH, MOVED or ADDED items are no longer
  UNKNOWN in RT-001. This refines "anything touching an UNSUPPORTED region
  stays UNKNOWN". The content is compared verbatim but never interpreted.
  This needs Chat/Architecture confirmation.
