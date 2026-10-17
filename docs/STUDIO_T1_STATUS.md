# STUDIO-T1 — Tiered Studio Apply (Fake Resolve)

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Nothing here touched DaVinci Resolve. Every "Resolve" in the tests is the
in-repo fake graph (`tests/support/fake_resolve.py`). No result is native or
live evidence. Native HOLD and Studio runtime HOLD stand; **TASK-020 is still
required**.

## Base and boundary

- Branch `wip/studio-t1-tiered-apply` from STUDIO-T0
  `b768f837663edf62280385b27d7b23f5ac92e873`. Not pushed.
- Not touched, because LAYER-001 is changing them in parallel: `apply_cuts.py`,
  `candidate_markers.py`, `xmeml_*.py`, `otio_json.py`, `roundtrip_*.py`.

Files:

1. `src/davinci_ai_editor/studio_capabilities.py` (changed). New capability
   entries for T1, five new areas and four new source constants. The
   `DuplicateTimeline` entry now records the OSS-measured current-pointer side
   effect.
2. `src/davinci_ai_editor/studio_transport.py` (changed). This file adds:
   - the Studio evidence label (`StudioEvidence`, `studio_verification`);
   - `read(timeline=…)`, which reads an explicit timeline object;
   - `apply_confirmed_cuts(…, neutral_splits=…)`;
   - two new object kinds: `MEDIA_POOL` and `GRAPH`.
3. `src/davinci_ai_editor/studio_razor.py` (new). Pure helpers: timecodes,
   razor steps and the NEUTRAL_SPLIT classifier.
4. `src/davinci_ai_editor/studio_apply_planner.py` (new). The pure tier
   planner and the plan summary (Korean text, English codes).
5. `src/davinci_ai_editor/studio_tiered_apply.py` (new). `TieredApplyPort`,
   which plans and executes tiers 1–4 and verifies each one by read-back.
6. `tests/support/fake_resolve.py` (extended). Adds:
   - MediaPool import, including the documented naming quirks;
   - structural grades and Fusion comps;
   - `CopyGrades`;
   - the playhead and a blade action;
   - track names.
7. `tests/test_studio_t1_tiered_apply.py` (new, 22 tests).
8. `docs/STUDIO_T1_STATUS.md` (this file).

The work adds no runtime dependency. It never imports `DaVinciResolveScript`
and uses no `hasattr`. Every call goes through an explicit allowlist
(`TIERED_READ_METHODS` / `TIERED_MUTATION_METHODS`) and needs a declared grant.
The T0 allowlist is unchanged. Its hygiene test still forbids
`ImportTimelineFromFile` in the in-place port.

## Tier model

| Tier | When | What happens | What the editor does |
|---|---|---|---|
| 1 `TIER_1_IMPORT_NEW_VERSION` | Some cut is mid-item and no grade is detected (`UNGRADED`), or the user chose `ACCEPT_GRADE_LOSS` | Writes the shared Expected (APPLY-001 result) as FCP7 XML, with a unique `<name> AIE vN` inside the file, and imports it as a NEW timeline. The original timeline is untouched and stays as the backup. The new version is opened only after the read-back gives MATCH. | `CONFIRM_ONLY` |
| 2 `TIER_2_IMPORT_WITH_GRADE_TRANSFER` | Grades are present and every transfer capability is granted | Tier 1, then `CopyGrades` from each graded original item to its pieces, and comps via `ExportFusionComp` / `ImportFusionComp`. Each item is read back. | `CONFIRM_THEN_REVIEW_GRADES` |
| 3 `TIER_3_DELETE_ALIGNED_IN_PLACE` | Every cut sits on item boundaries | T0 `DeleteClips(items, True)`, in place | `CONFIRM_ON_EDIT_PAGE` |
| 4 `TIER_4_RAZOR_ASSIST` | Graded but not transferable, or the user chose `USE_RAZOR_ASSIST` | `razor_goto` moves the playhead to each listed frame and the editor presses blade. If the result is NEUTRAL_SPLIT, tier 3 deletes the middle pieces. | `RAZOR_THEN_CONFIRM` |

Selection rules (`plan_studio_apply`, a pure function):

1. If every cut is aligned and tier 3 is granted, choose tier 3.
2. Otherwise follow the user's explicit choice, if there is one.
3. If the timeline is `UNGRADED`, choose tier 1.
4. If it is `GRADED` and the grades are transferable, choose tier 2.
5. If it is `GRADED` and the grades are not transferable, choose tier 4. If
   tier 4 is unavailable, return `NEEDS_USER_CHOICE` with
   `[ACCEPT_GRADE_LOSS]`.
6. If the grade state is **UNKNOWN**, return **`NEEDS_USER_CHOICE`** with
   `ACCEPT_GRADE_LOSS` and/or `USE_RAZOR_ASSIST`. Tier 1 is never chosen
   silently.

A policy the shared Expected cannot express yet is `UNSUPPORTED` with
`USE_FILE_PATH`. Such policies are:

- KEEP_IN_PLACE with later items;
- SHIFT_WITH_RIPPLE when an item overlaps a cut;
- an UNKNOWN policy.

Grade state (`read_grade_state`) is a capability-gated structural read. It
reads, for each video item, the node graph (count, labels, tools), the colour
versions and the Fusion comps, plus the project setting `nodeStackLayers`.

- Any positive signal gives GRADED.
- UNGRADED needs complete reads AND the `GRADE_ABSENCE_INFERENCE` grant, which
  is UNVERIFIED. Without that grant the state is UNKNOWN.

Bindings:

- A plan is `axis = "PLAN"` and `authorizes_apply = False`.
- `plan_digest` binds the tier, the cuts, the split frames, the names, the
  policies and the summary. It also binds `confirmation_digest` and the live
  Actual digest.
- `execute` raises `ApplyRefused` unless both digests are echoed exactly.
- Before any call, `execute` re-reads the live timeline; a difference is
  STALE.
- Execution is single-shot and never retries.

Read-back:

- **Geometry**: VER-001 compares the Expected with the new or edited
  timeline. For imports, marker colours are excluded (`format_losses`: FCP7
  carries no marker colour or customData).
- **Layers**: track count, kind, order and names via `GetTrackName`. Names are
  restored with `SetTrackName` only when granted; otherwise MISMATCH. Layers
  are never merged.
- **Grades** (tier 2): a structural fingerprint per item gives MATCH /
  MISMATCH / UNVERIFIED, and the MISMATCH items are listed. Grade **values**
  stay UNVERIFIED.

The outcome is MATCH only when every one of these parts is MATCH.

NEUTRAL_SPLIT (`studio_razor.classify_split_change`):

- A change counts as NEUTRAL_SPLIT only when every change splits one item into
  source-contiguous pieces at a listed frame, and nothing else changed. The
  pieces must keep the same media, name and enabled state, leave no gap, and
  the union of their markers must equal the original item's markers.
- It is not a human edit, so `hard_lock = False`. Merging the pieces back
  reproduces the confirmed Actual.
- A split at an unlisted frame, or any other change, is `HUMAN_EDIT`:
  `hard_lock = True`, and nothing is applied.
- Missing listed splits give `INCOMPLETE_SPLIT`, and nothing is applied.

## Capability evidence (sources: read-only OSS davinci-resolve-mcp, never executed)

| Capability | Status | Key facts | Source |
|---|---|---|---|
| `MediaPool.ImportTimelineFromFile` | DOCUMENTED_CLAIM | Options: `timelineName`, `importSourceClips`, `sourceClipsPath`, `sourceClipsFolders`, `interlaceProcessing`. Returns None for a repeated name. Recommended: FCP7 XML + unique name + `importSourceClips=False` + `sourceClipsFolders=[root]`. OTIO does not relink; DRT ignores the options. | README; TRUTH "MediaPool.ImportTimelineFromFile", "format fidelity" |
| Import naming authority | **UNVERIFIED** | FCP7 XML **ignores** `timelineName`; the internal `<sequence><name>` wins, and if that name exists the call returns the **existing** timeline (Studio 21.0.4.5, issue #171). | TRUTH "internal sequence name overrides timelineName" |
| Track names after import / exact media relink | UNVERIFIED | Pool media merge by a coarse identity, so items can cross-link silently. | TRUTH "Timeline import MERGES pool media…" |
| Marker colour / customData through FCP7 | NOT_AVAILABLE | Format limit (APPLY-001) | README, repo map |
| `TimelineItem.CopyGrades` | DOCUMENTED_CLAIM | Copies the **current node-stack layer** to the same layer. Measured on 21.1.0.14 (re-confirmed): **replaces** the target grade wholesale, returns True, creates **no version**, so the overwritten grade cannot be recovered. | README; pyi; TRUTH "TimelineItem.CopyGrades" |
| CopyGrades across timelines / keyframes | UNVERIFIED | Not documented | README; TRUTH |
| Copy all layers / other versions | NOT_AVAILABLE | No call selects the layer; no version is copied | README; TRUTH |
| `ExportFusionComp` / `ImportFusionComp` | DOCUMENTED_CLAIM | Comp time alignment on a later piece is UNVERIFIED | README; pyi |
| `AddFusionComp` | DOCUMENTED_CLAIM | Renders only when MediaOut has a path from MediaIn; a Composition.Lock trap exists. Not used. | TRUTH |
| `Graph.ApplyGradeFromDRX` | DOCUMENTED_CLAIM | gradeMode 0/1/2 (1 = source-TC aligned). Returns False on the Edit page with no signal. Needs a .drx still. Not used. | README; TRUTH ×2 |
| `ApplyGradeFromStill` | NOT_AVAILABLE | Does not exist on 21.1 | TRUTH |
| `ExportLUT` | DOCUMENTED_CLAIM | Color page only (bare False elsewhere). A static LUT, so it can serve only as a value read-back. | TRUTH (21.1.0.14) |
| `Timeline.SetCurrentTimecode` / `GetCurrentTimecode` | DOCUMENTED_CLAIM | Works on the Cut/Edit/Color/Fairlight/Deliver pages. The string format is UNVERIFIED, so 29.97/59.94 are refused. | README; pyi |
| `Timeline.GetCurrentVideoItem` | DOCUMENTED_CLAIM | Which track counts as "current" is undocumented. Not used. | README; TRUTH |
| `Timeline.DuplicateTimeline` | DOCUMENTED_CLAIM | **Silently moves the current-timeline pointer** to the copy (21.1.0.14). Not used: import leaves the original as the backup. | README; TRUTH |
| Split / razor at a frame | NOT_AVAILABLE | Unchanged from T0. The 21.1 changelog adds no split call. | TRUTH; 21.1 CL |
| Blackmagic 21.1 native MCP split/trim tools | **UNVERIFIED** | The OSS cites Blackmagic's MCP only for `list_luts` / `generate_lut` / `delete_lut` / `search_scripting_api`. No source in hand lists split or trim, or states Studio-only. | OSS api-coverage.md, lut-file-controls.md, typed-api-search.md |
| Grade absence inference | UNVERIFIED | A primary inside the single default node may not appear in the tools list | README |

## Tests (`tests/test_studio_t1_tiered_apply.py`, 22)

Tier selection:

- aligned cuts → tier 3 in place (2 `DeleteClips`, no import);
- mid-item + ungraded → tier 1, `CONFIRM_ONLY`. The imported geometry
  **equals the file path's APPLY-001 Expected**, the original is untouched,
  and the new version is opened;
- UNKNOWN grade → `NEEDS_USER_CHOICE`. Executing it is REFUSED with zero
  calls. Each explicit choice maps to tier 1 or tier 4. An unreadable graph
  gives UNKNOWN;
- graded + transferable → tier 2. The structure is MATCH per item, values are
  UNVERIFIED, and the calls are 1 `CopyGrades`, 1 export and 2 imports;
- graded but with 2 colour versions → tier 4, with razor timecodes. Without
  the razor grants → `NEEDS_USER_CHOICE[ACCEPT_GRADE_LOSS]`.

Grade transfer:

- partial transfer → MISMATCH, listing `Video 1@0` and naming the piece that
  was not transferred. The version is not opened and there is no retry.

Razor assist:

- NEUTRAL_SPLIT → delete → MATCH. The geometry equals the file path, and the
  grades survive in place;
- V1-only blade → INCOMPLETE_SPLIT;
- a blade at an unlisted frame → HUMAN_EDIT (`hard_lock`), with no
  `DeleteClips`;
- a playhead read-back offset → MISMATCH, with no retry;
- unit tests for the classifier (NO_CHANGE / INCOMPLETE / NEUTRAL / HUMAN) and
  for the timecode (29.97 → None).

Import quirks:

- name collision → REFUSED CONFLICT before any import; re-planning picks
  `AIE v3`;
- "returns existing" and "returns None" → FAILED with read-back UNVERIFIED,
  1 call, not retried.

Layers:

- custom track names are restored via `SetTrackName` → MATCH, with 3 tracks
  in their original kind and order;
- without the grant → MISMATCH, listing the names;
- an imported geometry error → MISMATCH, and the version is not opened.

Bindings and other checks:

- a wrong confirmation digest or a wrong plan digest → `ApplyRefused`;
- a live edit after the plan → REFUSED STALE, and re-planning is REFUSED;
- KEEP_IN_PLACE and UNKNOWN policies → UNSUPPORTED (file path);
- determinism: identical plan digest, summary and geometry over two runs;
- evidence label: `STUDIO_API_READ`, `native_evidence=False`, and the
  superseded core label `FILE_ROUNDTRIP` recorded;
- matrix findings and sources;
- allowlist hygiene: no rebuild, track, timeline-delete or duplicate calls,
  no `hasattr` and no `DaVinciResolveScript`;
- imported markers keep their names only.

## Customer-safe statement

> In Studio, "just press confirm" is promised **only for tier 1** (a new
> version timeline imported inside Resolve, with the original kept as the
> backup) until native verification (TASK-020) is complete.
>
> - Tier 2 (grade transfer) asks the editor to review the listed items' grades
>   after confirming.
> - Tier 3 needs the Edit page.
> - Tier 4 asks the editor to press blade at the listed timecodes.
>
> Nothing is applied without the confirmation, and every result is checked by
> read-back.

`StudioApplyPlan.confirm_only_promised` is True only for a READY tier-1 plan.

## What must be verified on a real Studio (TASK-020)

1. `ImportTimelineFromFile` with our FCP7 XML, `importSourceClips=False` and
   `sourceClipsFolders=[root]`. Check:
   - that it is frame-exact;
   - that it relinks to the same pool clips (file paths);
   - the name authority (internal name vs option);
   - what it returns for an existing name, and whether it changes the current
     timeline;
   - what happens to track names and to markers (colour, customData).
2. `SetTrackName` and `SetCurrentTimeline` on the imported version.
3. `CopyGrades`. Check whether it works across timelines, whether it carries
   keyframes, and how keyframes land on a later piece. Check which page it
   needs, and that it reports nothing for a multi-layer node stack (this
   should be measured, not assumed). Compare `ExportLUT` before and after on
   the Color page to get a value-level read-back.
4. `ExportFusionComp` / `ImportFusionComp`: the naming, the comp time
   alignment on later pieces, and whether the comp renders.
5. The structural grade read on the Edit page (graph, tools, versions,
   comps). Find out whether "one node, no tools" proves ungraded; until then
   `GRADE_ABSENCE_INFERENCE` stays ungranted.
6. `SetCurrentTimecode`: the accepted string format (NDF/DF), the page
   requirements, the `GetCurrentTimecode` echo, and the blade result. Check
   that Resolve's split keeps the name, media, enabled state and markers, so
   that NEUTRAL_SPLIT holds.
7. Whether Blackmagic's 21.1 MCP server exposes split or trim tools, and its
   edition.
8. Everything already listed in STUDIO_T0_STATUS "Next steps".

## Core changes needed (not made here; LAYER-001 owns those files)

> **INT-002 update:** all four items below are done in `wip/integration-v2`
> (evidence class `STUDIO_API_READ`, RT-001 `expected_splits` / `NEUTRAL_SPLIT`,
> LAYER-001 Expected with Studio CUT/SHIFT in place, colour-neutral digest).
> See docs/INT_002_STATUS.md.

- **Evidence class.** `roundtrip_diff` / `roundtrip_verification` hard-code
  `FILE_ROUNDTRIP`. A non-file class (for example `STUDIO_API_READ`, or a
  generic `NON_NATIVE_REREAD`) would make `StudioEvidence`'s "superseded"
  annotation unnecessary.
- **RT-001 neutral-split awareness.** RT-001 classifies any split as a human
  SPLIT, which means a HARD_LOCK. T1 avoids that by classifying inside the
  Studio module, against an explicit list of split frames. A core option
  (`diff_roundtrip(…, expected_splits=…)`) would let the file path accept
  editor razors at listed frames too.
- **LAYER-001 Expected.** KEEP_IN_PLACE, and SHIFT_WITH_RIPPLE with an item at
  a cut, are UNSUPPORTED until APPLY-001 cuts only CUT_WITH_SOURCE tracks.
  Imported versions (tiers 1/2) can express them once the Expected does.
- **Marker colour in the digest.** Unchanged open question from T0.

## Validation

Python 3.12 `.venv` with `PYTHONPATH=<worktree>/src`; the import path was
verified to be inside this worktree.

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_studio_t1_tiered_apply.py   22 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_studio_parity.py            20 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                                        2569 passed, 2 skipped
python -m ruff check src tests tools                                                                All checks passed
python -m ruff format --check <changed/new .py>                                                     already formatted
python -m mypy                                                                                      Success, 63 source files
MYPYPATH=tests python -m mypy --strict --explicit-package-bases <studio_* + T0/T1 tests + fake>      Success
git diff --check                                                                                    clean
```

## Open questions

- Should tier 2 also be offered when grade values cannot be verified at all,
  or should it require a value-level check (ExportLUT on the Color page)
  first?
- Should tier 3 be auto-preferred over tier 1 for aligned cuts even when no
  grade is present? It is today, because in place keeps every effect.
- Should the planner open the Color page for grade reads and transfers
  (`OpenPage`, which is not allowlisted today)?
