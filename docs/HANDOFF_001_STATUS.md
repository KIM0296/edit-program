# HANDOFF-001 — File-Based NLE Handoff Artifacts

Qualification: CODE_COMPLETE / TEST_ONLY_SUPPORT. Not native qualification.
Nothing here has been exercised against DaVinci Resolve.

## Base and boundary

- Base main: `7949c8b7fcb1a17fa612a6cd4279de6f3b245031`
- Branch: `wip/handoff-001-file-adapters` (not pushed)

Files added:

1. `src/davinci_ai_editor/timecode.py`
2. `src/davinci_ai_editor/handoff_model.py`
3. `src/davinci_ai_editor/subtitle_io.py`
4. `src/davinci_ai_editor/otio_json.py`
5. `src/davinci_ai_editor/xmeml_writer.py`
6. `tests/test_handoff_timecode.py`
7. `tests/test_handoff_model.py`
8. `tests/test_handoff_subtitle_io.py`
9. `tests/test_handoff_otio_json.py`
10. `tests/test_handoff_xmeml_writer.py`
11. `tests/fixtures/handoff001/golden_default.otio`
12. `tests/fixtures/handoff001/golden.xmeml.xml`
13. `licenses/timeline-LICENSE.txt`, `licenses/srt-LICENSE.txt`,
    `licenses/OpenTimelineIO-LICENSE.txt`, `licenses/OpenTimelineIO-NOTICE.txt`
14. `docs/HANDOFF_001_STATUS.md`

No existing file is modified. Zero runtime dependencies (stdlib `json`,
`xml.etree`, `fractions`, `re`, `urllib.parse`, `pathlib` pure paths only).

## Purpose

Describe an **Expected** timeline as a file that a human may choose to bring
into an NLE manually. The neutral `HandoffTimeline` model and every writer /
reader result carry `artifact_kind = "EXPECTED_TIMELINE_ARTIFACT"` and
`authorizes_import = False`; both are validated constants, not options.

## What it does NOT authorize

- No import. `ImportTimelineFromFile` (or any UI import) is a native mutation
  that stays **HOLD / manual user action**. No code path here calls Resolve.
- No native evidence. A written file proves only what we intended; it never
  proves Actual timeline state, never feeds Post-Edit Verification as Actual,
  and never satisfies a Safety gate.
- No media access. Paths are strings; nothing is opened, probed or hashed.
- No guessing: UNKNOWN rate, track kind, marker color and media start stay
  UNKNOWN; writers refuse instead of choosing.

## Formats

### Timecode (`timecode.py`)

- Whitelist (exact `FrameRate`, reused from `temporal_mapping`): 24000/1001,
  24, 25, 30000/1001, 30, 48000/1001, 48, 50, 60000/1001, 60.
- Drop-frame only for 30000/1001 (2 frames/min) and 60000/1001 (4 frames/min),
  separator `;`. 23.976 and 47.952 are NDF.
- `frames_to_timecode` / `parse_timecode` both directions, exact integers.
  Nonexistent DF labels (e.g. `00:01:00;00`) are rejected, not coerced.
- 24h rollover policy is explicit: `RolloverPolicy.REJECT` (default) raises;
  `WRAP_24H` wraps modulo the 24h frame count (2,589,408 at 29.97 DF).
- `snap_rate(float) -> FrameRate | None`: absolute tolerance 1e-3 against the
  whitelist; `None` = UNKNOWN (e.g. 23.98 is UNKNOWN, never snapped).
- frames -> ms via `Fraction`: start = floor, end = ceil (covering span).

### Neutral model (`handoff_model.py`)

`HandoffTimeline(name, rate, start_frame, tracks)`,
`HandoffTrack(name, kind VIDEO|AUDIO|UNKNOWN, items)`,
`HandoffClip(name, media, source_range, enabled, markers)`, `HandoffGap(duration)`,
`HandoffMediaRef(media_id, target_path|None, available_range|None,
media_start_frame|None)`, `HandoffMarker(frame_range, name, color, note)`,
`HandoffSubtitleCue(frame_range, text)`. Source/available/marker ranges are
media-relative frames at the timeline rate (mixed-rate media out of scope).
`handoff_from_snapshot(snapshot, media, rate, name, start_frame=0)` derives
ordered gaps from `domain.TimelineSnapshot` clip timeline ranges; missing
media mapping or SUBTITLE/OTHER tracks reject; UNKNOWN track type stays
UNKNOWN. `start_frame` is the artifact's declared label origin, not an
observed Resolve value.

### Subtitles (`subtitle_io.py`)

- SRT writer: sorted by (start, end, input order), renumbered from 1,
  `HH:MM:SS,mmm`, blank lines collapsed. Empty text and text containing `-->`
  are **refused** with diagnostics (`EMPTY_TEXT`, `ARROW_IN_TEXT`); the result
  is marked `complete = False`. Nothing is silently dropped.
- Strict SRT reader: BOM and CRLF tolerated; bare CR, bad index, non-sequential
  index, malformed timing, start >= end and empty content are reported.
- WebVTT writer: `WEBVTT` header, `HH:MM:SS.mmm`, `& < >` escaped, `-->` refused.

### OTIO JSON (`otio_json.py`)

- Schemas: Timeline.1, Stack.1, Track.1, Clip.2 (`media_references` map with
  `active_media_reference_key = "DEFAULT_MEDIA"`), Gap.1, ExternalReference.1,
  MissingReference.1, Marker.2 (string color), RationalTime.1, TimeRange.1.
- Deterministic: sorted keys, 2-space indent, LF, trailing newline. Rate is
  the single correctly rounded float of the exact rational
  (30000/1001 -> `29.97002997002997`); values are integral frame counts.
- `media_id`, `media_start_frame` and the profile are kept in
  `metadata["davinci_ai_editor"]` so the reader never guesses them.
- Reader (same subset): rates snap back through `snap_rate`; unknown schema
  name/version (e.g. `Clip.3`, `Marker.3`, `Transition.1`), unknown rate,
  mixed rates, non-integral times, effects, missing `media_id` and unknown
  profile are refusals (no timeline returned). Unknown track kind / marker
  color are returned as UNKNOWN with a warning.

### FCP7 xmeml v5 (`xmeml_writer.py`)

`<!DOCTYPE xmeml>`, `rate/timebase` + `ntsc`, sequence and file `timecode`
with `DF`/`NDF` displayformat, clipitem `name/enabled/duration/start/end/in/out`
and `file` (`pathurl`, later uses reference `<file id=…/>`). Built with
`xml.etree`, deterministic. Missing references and UNKNOWN track kinds are
refused. A file `timecode` is written only when `media_start_frame` is known.
Not written (explicit limits): `<format>`/`samplecharacteristics` (frame size
and sample rate are unknown to the model), marker colors
(warning `MARKER_NOT_REPRESENTED`). A/V `link` elements were added later by
APPLY-001 (see `docs/APPLY_001_STATUS.md`).

## Resolve-shape claims (third-party, UNVERIFIED on our runtime)

`OtioProfile.RESOLVE_SHAPED` encodes claims gathered from third-party tooling,
not from Resolve documentation or our own runtime observation:

1. `ExternalReference.target_url` is a bare filesystem path, not a `file://` URL.
2. Clip `source_range` (and `available_range`, marker ranges) are absolute
   against the media start timecode (`media_start_frame`), not 0-based.
3. Track names follow `Video 1`, `Audio 1`, … per kind.

When `media_start_frame` is UNKNOWN the profile **refuses**
(`MEDIA_START_UNKNOWN`) rather than assume 0. URL-shaped targets are refused.
These claims must be verified by a separately approved native probe before any
reliance; until then the profile is test-only support.

## Validation

Python: `.venv` interpreter with `PYTHONPATH=<worktree>/src` (import path
verified to point into this worktree).

```text
python -m pytest -q -p no:cacheprovider --basetemp=<scratch> tests/test_handoff_*.py
python -m pytest -q -p no:cacheprovider --basetemp=<scratch>
python -m ruff check src tests tools
python -m ruff format --check <new files>
python -m mypy
python -m mypy --strict --explicit-package-bases <new src files> <new test files>
git diff --check
```

Results are recorded in the commit report: targeted 95 passed; full suite,
ruff, ruff format, mypy (project) and mypy --strict (new files) clean.

## Provenance and licensing

- `timecode.py` drop-frame branch: adapted from OpenTimelineIO
  `src/opentime/rationalTime.cpp` (`to_timecode`), Apache-2.0, ported to exact
  integer arithmetic. OTIO schema names/fields follow OpenTimelineIO.
  `licenses/OpenTimelineIO-LICENSE.txt` and `licenses/OpenTimelineIO-NOTICE.txt`
  (NOTICE copied with trailing whitespace stripped; text unchanged).
- `otio_json.py` object layout and `xmeml_writer.py` element layout: adapted
  from `timeline` (Chat Octopus) `src/otio/writer.ts`, `src/xmeml/writer.ts`,
  `src/time.ts`, MIT — `licenses/timeline-LICENSE.txt`.
- `subtitle_io.py` content legalization and skip conditions: adapted from
  `srt` (Christopher Down) `srt.py`, MIT — `licenses/srt-LICENSE.txt`; skip
  conditions became explicit refusals.
- Nothing copied from repositories without a license file. No OSS code was
  executed, imported or installed.
