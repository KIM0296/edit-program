# RT-001 — File Round-Trip Import, Diff and Human-Edit Protection

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Nothing here has been exercised against DaVinci Resolve or any other NLE; all
"editor" actions in tests are text edits of our own writer output.

## Base and boundary

- Base: HANDOFF-001 `e80f46e7928d79e1e6c43fcf1a3a8a35ae935516`
- Branch: `wip/rt-001-roundtrip-diff` (not pushed)

Files added (no existing file modified):

1. `src/davinci_ai_editor/xmeml_reader.py`
2. `src/davinci_ai_editor/roundtrip_diff.py`
3. `tests/support/roundtrip_fixtures.py`
4. `tests/test_xmeml_reader.py`
5. `tests/test_roundtrip_diff.py`
6. `docs/RT_001_STATUS.md`

Zero runtime dependencies (stdlib `xml.etree`, `re`, `hashlib`, `json`).

## Why

Resolve 21.1 moved Python scripting to Studio, so for Free users the only path
is a file round-trip: we write an Expected timeline file (HANDOFF-001), the
editor imports it, edits by hand, exports FCP7 XML or OTIO, and we re-read it.
No competitor documents preserving human edits across an AI re-run; RT-001 is
the mechanism that makes "Human Edit Wins" enforceable in that loop.

## Evidence class

A re-imported file is `FILE_ROUNDTRIP` evidence (`XmemlReadResult`,
`RoundTripArtifactRef`, `RoundTripDiff` carry the validated constant). It is
never native evidence, never VERIFIED_LIVE, and never an observed native
snapshot for Safety. `RoundTripArtifactRef.native_evidence` is a validated
`False`. The re-read file is a `ReimportedTimeline` (Actual side, see
"Follow-up decisions"), never an Expected `HandoffTimeline`.

## xmeml reader (`xmeml_reader.py`)

Accepted: `xmeml` version 4/5 with exactly one top-level `sequence`;
`rate/timebase` + `ntsc`; sequence `timecode` (`frame` and/or `string`, must
agree); `media/video|audio/track/clipitem` `start/end/in/out`, `name`,
`enabled`; `file` definitions collected by id across all clipitems so
`<file id=…/>` references resolve in any order (idea adapted from timeline
`src/xmeml/reader.ts`, MIT, `licenses/timeline-LICENSE.txt`); file `pathurl`,
`name`, `rate`, `duration`, `timecode`; clip `marker` (`out` -1/absent = one
frame). Track names become `Video N` / `Audio N`.

Refused (no timeline returned): >`max_chars` (default 8 MiB) or >200k elements;
any `<!ENTITY`; DTD internal subset, external DOCTYPE id, or any DOCTYPE other
than bare `<!DOCTYPE xmeml>`; malformed XML; unknown version; project/bin roots
or multiple sequences; missing `ntsc` or non-whitelisted rate (UNKNOWN, never
defaulted to 24); missing sequence timecode (start UNKNOWN, never 0); undefined
or conflicting file ids.

UNSUPPORTED → `UnknownRegion` (warning diagnostic, region UNKNOWN, clip not
placed, its span becomes a gap): `transitionitem`, `generatoritem`, nested
`sequence`, speed change (record != source duration, `timeremap` filter), any
other `filter`, unknown clip/track child, clip without file or in/out,
mixed-rate file, marker outside the clip, overlapping placements, disabled
track. A `-1`/missing clip boundary or unknown track child makes the whole
track UNKNOWN (`frame_range=None`). Missing clip `enabled` uses the FCP7 DTD
default TRUE with a warning. Sequence-level markers are reported, not modelled.

## Diff (`roundtrip_diff.py`)

`diff_roundtrip(expected, actual, *, artifact_ref, unknown_regions=(), read_diagnostics=())`
plus `diff_xmeml_roundtrip`, `diff_otio_roundtrip`, `diff_unreadable_roundtrip`.

- Tracks correspond by `TrackKey(kind, ordinal within kind)` (xmeml has no
  track names).
- Identity basis follows the artifact format: OTIO carries our `media_id`
  metadata (STRONG when id matches and paths agree/absent; WEAK on relink);
  xmeml carries only a display name + path (WEAK when the path matches,
  UNKNOWN on a display-name match with a different path).
- Per track, a bipartite graph links Expected and Actual clips with compatible
  identity and overlapping source ranges. Components: 1↔1 → UNCHANGED / MOVED
  (same source, timeline shift) / TRIMMED (head/tail deltas); 1↔N with ordered
  disjoint sources → SPLIT; N↔1 exact contiguous union → MERGED; anything else
  → UNKNOWN `AMBIGUOUS_MATCH`. Then cross-track exact-source unique matches →
  MOVED `track_changed`; unique same-position different-media pairs →
  REPLACED; remaining Expected → REMOVED_BY_HUMAN; remaining Actual →
  ADDED_BY_HUMAN. Enabled/marker differences are `attribute_changes`.
- Anything overlapping an UNSUPPORTED region is UNKNOWN; an unmatched Expected
  clip while any region of its kind is UNKNOWN is UNKNOWN, not REMOVED.
- Rate mismatch, start mismatch, unknown format or an unreadable Actual →
  whole diff `DiffStatus.UNKNOWN` with reasons.
- Deterministic ordering; `expected_digest` / `actual_digest` use the
  `trust_evidence.canonical_bytes` SHA-256 (same as `artifact_revision`);
  `artifact.text_sha256` binds the exact file text; `RoundTripDiff.digest`
  covers everything.

## Human-edit protection

`derive_human_edit_protection(diff) -> tuple[ProtectedRange, ...]` (HARD_LOCK,
Actual timeline coordinates, merged per track, deterministic):

- TRIMMED: clip span extended over trimmed-away frames; MOVED: new span and
  the old span; SPLIT/MERGED/ADDED: actual span; REPLACED: hull of old+new;
  REMOVED: neighbourhood between surviving neighbours (or the two frames around
  a ripple join; or the old duration after the last survivor); UNCHANGED only
  with attribute changes.
- Every UNKNOWN item and every UNKNOWN region is locked; whole-track UNKNOWN
  and whole-diff UNKNOWN lock `[0, 24h of frames at the Actual rate)`.
- Unreadable Actual → `ProtectionUnavailable` (no coordinates exist; the
  caller must treat the whole timeline as untouchable). Never an empty tuple.
- `track_id`: the Expected track name for the same `TrackKey` (HANDOFF-001
  derives Expected track names from snapshot track IDs), else
  `ROUNDTRIP:<KIND>:<n>`.

Feeding the existing path (documented, not wired): an AI re-run builds its base
`TimelineSnapshot` from the authoritative Actual and passes these as
`protected_ranges` (`safety.preflight` rejects direct edits and ripple shifts
of HARD_LOCK ranges) or as `safety_preflight.ProtectedRangeRecord` values in a
`ProtectionContext`. Candidate generation excludes them before proposing.
Stale plans built before the round-trip cannot auto-execute; nothing is
silently rebased.

## Tests

Synthetic Expected built with `handoff_model`, written by `xmeml_writer` /
`otio_json`, then text-mutated: untouched, trim tail, trim head, move, delete,
ripple delete, insert, split, merge (lost cut), replace, enable toggle, rate
change, start change, transition added, duplicate paste (ambiguous),
display-name/path conflict, cross-track move, OTIO trim (STRONG), OTIO
`Transition.1` (unreadable → UNKNOWN, `ProtectionUnavailable`), XXE /
billion-laughs / external DOCTYPE refusal, oversize refusal, unknown rate,
missing timecode, dangling file id, nested sequence, speed, generator, `-1`
boundary, determinism and digest binding.

## Validation

Python 3.12.10 `.venv` with `PYTHONPATH=<worktree>/src` (verified
`davinci_ai_editor.__file__` is inside this worktree). CI target 3.11; no
3.12-only syntax used.

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_xmeml_reader.py tests/test_roundtrip_diff.py   28 passed
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>                                                         2233 passed, 2 skipped
python -m ruff check src tests tools                                                                                 All checks passed
python -m ruff format --check <5 new .py files>                                                                      already formatted
python -m mypy                                                                                                       Success, 48 source files
MYPYPATH=tests python -m mypy --strict --explicit-package-bases <2 new src> <2 new tests> tests/support/roundtrip_fixtures.py   Success, 5 files
git diff --check                                                                                                     clean
```

## Follow-up decisions (user-approved, APPLY-001 branch)

1. **Separate Actual container.** Readers (`read_xmeml`, `read_otio`) return
   `handoff_model.ReimportedTimeline` (evidence class `FILE_ROUNDTRIP`,
   `native_evidence = False`, no `EXPECTED_TIMELINE_ARTIFACT` constant). The
   Expected `HandoffTimeline` keeps `EXPECTED_TIMELINE_ARTIFACT`.
   `diff_roundtrip(expected: HandoffTimeline, actual: ReimportedTimeline, …)`
   rejects an Expected passed as Actual (`TypeError`). Tracks reuse the
   structural `HandoffTrack`. The canonical digest includes the type name, so
   an Expected and a re-read timeline never share a digest. `OtioReadResult`
   now carries `evidence_class = FILE_ROUNDTRIP` instead of the Expected
   `artifact_kind` / `authorizes_import` constants.
2. **FCP7 XML is the default/primary round-trip format.** OTIO stays
   supported. An OTIO `ExternalReference` whose
   `metadata["davinci_ai_editor"]` was dropped by the NLE is no longer a
   refusal: the target path becomes the media ID (warning `MISSING_MEDIA_ID`,
   ID listed in `ReimportedTimeline.path_identified_media_ids`). The diff
   matches those clips by target path + source range with identity strength
   WEAK (`MediaIdentityBasis.PATH_FALLBACK`; clips that kept the metadata stay
   STRONG). A `MissingReference` without metadata has no path and is still a
   refusal. A path-derived ID that happens to equal a real media ID is
   treated as path-identified (weaker, conservative).
3. VER-001 identity rule — see `docs/VER_001_STATUS.md`.

## Limits and open questions

- Whether Resolve exports xmeml `in`/`out` 0-based (our writer's convention)
  or media-timecode-absolute is UNVERIFIED; the timeline OSS reader subtracts
  the file timecode. A native probe must settle this before relying on trims.
- OTIO exports that drop our `media_id` metadata now use the WEAK path basis
  (decision 2); media start and Resolve-shaped absolute ranges are then
  UNKNOWN, so the Resolve-shaped profile still refuses without metadata.
- MOVED clips caused purely by an upstream ripple are locked too (conservative);
  a ripple-consistent exemption would need an approved policy.
- MERGED is an extra class beyond the requested list (exact-union join).
