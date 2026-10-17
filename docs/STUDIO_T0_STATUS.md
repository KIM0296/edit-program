# STUDIO-T0 — Studio Transport on the Shared Core (Fake Resolve)

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Nothing here touched DaVinci Resolve. Every Studio-side "Resolve" in the tests is
the in-repo fake object graph (`tests/support/fake_resolve.py`). No result is
native or live evidence.

## Base and boundary

- Branch `wip/studio-t0-transport` from integration commit
  `d4e342867e923b5e8b7f215d201fae90bf6a3c45`, not pushed.

Files:

1. `src/davinci_ai_editor/studio_capabilities.py` (new): capability matrix, sources,
   `IN_PLACE_FEASIBILITY`, runtime grants (`StudioCapabilityProfile`).
2. `src/davinci_ai_editor/studio_transport.py` (new): `ResolveReadPort`,
   `ResolveMutationPort`, `TrackCutPolicy`, helpers.
3. `src/davinci_ai_editor/roundtrip_diff.py` (changed, additive): new
   `RoundTripFormat.STUDIO_API_READ`. Its identity basis is DISPLAY_NAME, the same
   as FCP7 xmeml.
4. `tests/support/fake_resolve.py` (new): a deterministic fake
   Project/Timeline/TimelineItem/MediaPoolItem.
5. `tests/test_studio_parity.py` (new): 20 tests.
6. `docs/STUDIO_T0_STATUS.md` (this file).

The work adds no runtime dependency and never imports `DaVinciResolveScript`.
It uses no `hasattr()`: capabilities are declared grants, and calls go through
an explicit allowlisted method table.

## Capability matrix (summary; full entries and notes in `studio_capabilities.py`)

Sources:

- **README**: the Resolve scripting README mirror in the OSS davinci-resolve-mcp
  (MIT) at `docs/reference/resolve_scripting_api.txt`, dated 24 Jul 2026.
- **21.1 CL**: the same OSS, `resolve_scripting_changelog_21.1.md`.
- **TRUTH**: the same OSS, `src/utils/api_truth.py`. Its entries were measured
  live by the OSS authors on 19.1.3.7, 20.3.2.9 and 21.0.x.
- **MAP**: `docs/RESOLVE_READ_CAPABILITY_MAP.md`.

We read the OSS only. We never executed it.

| Capability | API | Status | Source |
|---|---|---|---|
| current timeline | `Project.GetCurrentTimeline` | DOCUMENTED_CLAIM | README |
| tracks | `GetTrackCount`, `GetItemListInTrack` | DOCUMENTED_CLAIM (list order undocumented) | README, MAP |
| timeline start | `GetStartFrame` (absolute, e.g. 86400) | DOCUMENTED_CLAIM | README, TRUTH recordFrame |
| timeline end | `GetEndFrame` | DOCUMENTED_CLAIM, **exclusive** | TRUTH "GetEndFrame (exclusive bound)" |
| item start / end | `GetStart` / `GetEnd` | DOCUMENTED_CLAIM, absolute, end **exclusive** | README, TRUTH |
| source start | `GetLeftOffset` | DOCUMENTED_CLAIM, exact at 100% speed; warped by retime | TRUTH "GetSourceStartFrame" |
| source start (alt) | `GetSourceStartFrame` | UNVERIFIED (off by one on some items; diagnostic only) | TRUTH |
| source end | `GetSourceEndFrame` | UNVERIFIED (exclusive or inclusive depending on rate match; unused) | TRUTH |
| media pool item / path | `GetMediaPoolItem`, `GetClipProperty('File Path')` | DOCUMENTED_CLAIM (key spelling to qualify) | README, MAP |
| media frames / start | `GetClipProperty('Frames'/'Start')` | UNVERIFIED | TRUTH |
| fps | `GetSetting('timelineFrameRate')` | UNVERIFIED (string vocabulary undocumented; strict whitelist) | README |
| item markers | `TimelineItem.GetMarkers` | DOCUMENTED_CLAIM | README |
| item marker frame basis | "clip offset" | **UNVERIFIED** (offset from the item start or from the media start) | README |
| marker add | `TimelineItem.AddMarker(frameId,color,name,note,duration,customData)` | DOCUMENTED_CLAIM | README |
| marker delete | `DeleteMarkerByCustomData` / `DeleteMarkerAtFrame` | DOCUMENTED_CLAIM | README |
| marker update | `UpdateMarkerCustomData` only | DOCUMENTED_CLAIM; name/colour/note update **NOT_AVAILABLE** | README |
| split / razor / blade at a frame | none | **NOT_AVAILABLE** | TRUTH "Razor / blade / split" (dir() on 21.0.0); README; 21.1 CL |
| trim / move an item | none (getters only) | **NOT_AVAILABLE** | TRUTH "no position setters" |
| ripple-delete a frame sub-range | none | **NOT_AVAILABLE** | README; TRUTH "edit modes" |
| delete items with ripple | `Timeline.DeleteClips(items, True)` | DOCUMENTED_CLAIM (needs the Edit page; False return advisory; linked audio not auto-deleted) | README; TRUTH ×2 |
| ripple span semantics | which tracks shift, and by how much | **UNVERIFIED** | README |
| ripple / shift chosen tracks only | none | **NOT_AVAILABLE** | README; TRUTH "edit modes" |
| track lock read / set | `GetIsTrackLocked` / `SetTrackLock` | DOCUMENTED_CLAIM (not used) | README, MAP |
| locked track vs `DeleteClips` ripple | — | **UNVERIFIED** | README; TRUTH DeleteClips |
| delete track | `DeleteTrack` | DOCUMENTED_CLAIM; **never used** | README |
| scene-cut detection | `DetectSceneCuts` | DOCUMENTED_CLAIM; cannot target a frame | README |
| rebuild | `CreateTimelineFromClips`, `AppendToTimeline`, `CopyGrades` | DOCUMENTED_CLAIM; **never used** (new items, grades and effects lost) | README; TRUTH |
| capability probing | `hasattr` | NOT_AVAILABLE (always True) | TRUTH |

## In-place feasibility (product-critical)

No documented call splits an item at a frame, trims an item, or ripple-deletes a
frame sub-range. This holds for every source we have: the 19.x/20.x/21.0/21.1
README, the 21.1 changelog, and the OSS `dir()` probes on 21.0.0. The only
in-place cut primitive is `Timeline.DeleteClips([items], True)`, and it removes
**whole items**.

Consequences for the strategy promise ("applied in place, grades preserved"):

- **In place works only for cuts that coincide with item boundaries** on every
  track that is cut. Typical pause or filler cuts fall inside a clip, so they
  are **UNSUPPORTED in place**. The outcome is `UNSUPPORTED` with
  `fallback = FILE_PATH`: the APPLY-001 XML, a new timeline that does not carry
  grades.
- The transport **never rebuilds** a timeline, and nothing rebuilds silently.
- Split is a capability flag (`SPLIT_ITEM_AT_FRAME`). It can only be granted
  for tests, through a fake-only method `AieTestOnlySplitAt` that is not a
  Resolve API. A test shows that the flag path reaches the file path's
  geometry. If Blackmagic ships a split API, that path is where it goes.
- Per-track policy (LAYER-001 requirement): `apply_confirmed_cuts(...,
  track_policies=...)` takes one of `CUT_WITH_SOURCE`, `SHIFT_WITH_RIPPLE` or
  `KEEP_IN_PLACE` for each track.
  - Items on non-CUT tracks are never deleted.
  - An item on a non-CUT track that overlaps a cut is a `LAYER_CONFLICT`, and
    the result is UNSUPPORTED.
  - `KEEP_IN_PLACE` is UNSUPPORTED because track-selective ripple is
    NOT_AVAILABLE.
  - `SHIFT_WITH_RIPPLE` relies on the UNVERIFIED span ripple of `DeleteClips`.
  - An UNKNOWN policy is refused.
  - Tracks are never deleted, merged or flattened. `DeleteTrack` and
    `SetTrackLock` are not allowlisted.

## Design

- **Read** (`ResolveReadPort.read`):
  - It makes getter-only allowlisted calls with typed validation. A `None` stays
    `None` and makes the read UNVERIFIED. Wrong types, missing methods and
    raising calls also make it UNVERIFIED.
  - It reads at least twice. Identical raw reads are `CONSISTENT`; differing
    reads are `UNSTABLE`. Only `CONSISTENT` returns an Actual. That Actual is a
    `ReimportedTimeline`, so RT-001, VER-001 and APPLY-001 run unchanged.
  - Conversion rules: timeline-relative frame = `GetStart() - GetStartFrame()`;
    source = `[GetLeftOffset, +duration)`; item marker range = left offset +
    frameId (needs the `ITEM_START_RELATIVE` basis grant); media = display name
    + path (WEAK identity, as with xmeml); tracks are `Video N` / `Audio N`.
  - The last item end must equal `GetEndFrame()`, which catches inclusive-end
    drift.
- **Mutate** (`ResolveMutationPort`):
  - Marker add first checks that the handoff was built from the live timeline
    (otherwise STALE). The token goes in `customData`. Marker remove uses
    `DeleteMarkerByCustomData`.
  - Cuts: `apply_confirmed_cuts` calls APPLY-001 `apply_approved_cuts`, so a
    wrong digest raises `ApplyRefused`. The live read must be CONSISTENT and
    equal the confirmation's Actual digest (otherwise STALE). This means a
    file-path confirmation cannot drive the live timeline.
  - The planner then applies the capability, policy and lock gates, and runs
    `DeleteClips` once per cut, last cut first, passing video and audio items
    together.
  - Every mutation is followed by a read-back. VER-001 compares it against the
    Expected (APPLY-001's result, keeping the live name) and returns MATCH,
    MISMATCH or UNVERIFIED.
  - A False, None or raising call gives `FAILED`. The port stops and **never
    retries**, unlike the OSS recommendation to retry once.
- Reused, not re-invented: `CaptureConsistency` (native_snapshot), `PortIssueKind`
  (runtime_ports), and the APPLY-001, RT-001 and VER-001 functions. The
  transport has no state machine.

## Parity results (`tests/test_studio_parity.py`)

Shared fixture: an interview pre-cut at its pauses (V1 plus linked A1), a B-roll
layer on V2, start frame 86400, and 4 candidates. The editor approves 2, rejects
1 and leaves 1 pending.

- The candidate sets are identical, and so is the Expected (`expected_digest`).
- The approved cut set and the skip reasons are identical.
- **The confirmation digests differ, for one documented reason.** The digest is
  computed over `{expected_digest, actual_digest, approved_cuts}`. Only
  `actual_digest` differs, because FCP7 xmeml carries no marker colour: markers
  re-read from the file are `MarkerColor.UNKNOWN`, while the live read returns
  `YELLOW`. The test checks this exactly:
  - with the colours normalized to UNKNOWN, the Studio Actual equals the xmeml
    Actual;
  - over the normalized Actual, `confirmation_digest_for` reproduces the file
    path's digest bit for bit.
- The applied cut geometry is identical on V1, V2 and A1 across the file-path
  Expected, the Studio Expected and the Studio read-back. Video and audio are
  cut at the same frames. The timeline keeps its name and keeps all 3 tracks.
- VER-001 gives MATCH on both paths.
- Other tests:
  - a mid-item cut is UNSUPPORTED, makes zero `DeleteClips` calls, leaves the
    timeline untouched, and the file path covers it;
  - the split flag path matches the file-path geometry;
  - an ABSENT ripple grant gives UNSUPPORTED and an UNKNOWN grant gives
    REFUSED;
  - None, missing-method, unstable, inclusive-end and no-timeline reads are all
    non-MATCH: UNVERIFIED, or UNSTABLE for unstable reads;
  - an unknown marker basis and the documented-only profile are UNVERIFIED;
  - an unstable live read refuses the mutation;
  - a wrong digest, or a file-path confirmation, is refused;
  - a stale marker handoff is refused;
  - a post-mutation geometry error gives MISMATCH with one call per cut;
  - a failing `DeleteClips` gives FAILED after 1 call, with no retry;
  - a HARD_LOCK from a human marker skips that cut and keeps the locked item;
  - for per-track policies, KEEP_IN_PLACE, LAYER_CONFLICT and UNKNOWN are
    UNSUPPORTED, and SHIFT on V2 moves the B-roll by 32 frames without cutting
    it (MATCH);
  - marker removal gives MATCH;
  - matrix answers and allowlist hygiene: no rebuild or track calls, no
    `hasattr`, no `DaVinciResolveScript`.

**Parity must be re-run after LAYER-001 lands.** LAYER-001 changes APPLY-001 so
that it cuts only CUT_WITH_SOURCE tracks. The tests here use the current
APPLY-001, which cuts every track. Until then, a non-CUT track that overlaps a
cut is reported as LAYER_CONFLICT rather than diverging from the Expected.

## What it does NOT authorize

- No native read or mutation of Resolve. The native HOLD stands, Studio runtime
  qualification HOLD stands, and **TASK-020 is still required**.
- A documented claim is not a qualified capability. `documented_profile()`
  grants nothing, so a transport built on it refuses everything.
- No import, render, UI automation or timeline rebuild. Not wired into
  orchestration, authority or promotion.
- The evidence labels inside the reused core types still say `FILE_ROUNDTRIP`
  ("re-read, never native"). The Studio results carry
  `evidence_domain = TEST_ONLY_SUPPORT` and `native_evidence = False`.

## Next steps for native qualification (TASK-020 and later)

1. Probe the Tier-A getters on a disposable project. Confirm absolute
   `GetStart`, exclusive `GetEnd` / `GetEndFrame`, `GetLeftOffset` versus
   `GetSourceStartFrame`, and the `timelineFrameRate` strings.
2. Settle the item marker frameId basis, then grant `ITEM_START_RELATIVE` only
   with that evidence.
3. Probe `DeleteClips(items, True)`: the Edit-page gate, the span ripple across
   tracks, linked items, locked-track behaviour, and whether grades and effects
   on surviving items are untouched.
4. Re-confirm that no split, trim or range-delete API exists on the target
   build. If one appears, add it behind `SPLIT_ITEM_AT_FRAME`.
5. (Answered by STUDIO-T1, `docs/STUDIO_T1_STATUS.md`: four-tier apply —
   import a new version, grade transfer, in place, razor assist.) Decide the
   product answer for mid-item cuts. Options: the file path; or ask
   the editor to razor at the listed frames, noting that a razor counts as an
   RT-001 SPLIT and therefore a HARD_LOCK today.
6. Re-run parity after LAYER-001. Add a native `CapabilityGrant` only through
   the existing qualification gates.

## Validation

Python 3.12 `.venv` with `PYTHONPATH=<worktree>/src`; the import path was
verified to be inside this worktree.

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_studio_parity.py   20 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                              2547 passed, 2 skipped
python -m ruff check src tests tools                                                      All checks passed
python -m ruff format --check <5 new/changed .py>                                         already formatted
python -m mypy                                                                            Success, 60 source files
MYPYPATH=tests python -m mypy --strict --explicit-package-bases <4 new .py>              Success
git diff --check                                                                          clean
```

## Open questions

- Should mid-item cuts in Studio offer "razor at these frames, then re-run"? That
  needs an RT-001 policy so that the editor's razor at our listed frames does not
  lock the cut.
- Should the core evidence-class constant be generalized (for example to
  `NON_NATIVE_REREAD`) instead of reusing `FILE_ROUNDTRIP` for Studio reads?
- Marker colour makes the confirmation digests differ between transports. Should
  the digest canonicalize the Actual without marker colours, so that both
  transports produce one digest for the same decision?
