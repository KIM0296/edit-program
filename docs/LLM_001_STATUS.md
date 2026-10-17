# LLM-001 — ID-only Transcript Context, Rough-cut Proposal Validator, Advisory Boundary Check

Qualification: **CODE_COMPLETE / TEST_ONLY_SUPPORT**. Pure, stdlib-only data contracts.
No LLM call, no network, no media, no Resolve, no timeline mutation, no approval authority.

> AI에게 편집 업무는 맡기되, 편집권은 넘기지 않는다.

## Purpose

Give a future LLM step a safe way to *suggest* a transcript-based rough cut:

1. the LLM sees only numbered segments (`S0001`...) and text — never frames, timecodes, word
   refs, producer refs or file names;
2. the LLM answers with segment IDs and a closed reason code only (semantic IR, ADR-006);
3. a deterministic validator rejects anything else, all-or-nothing, and turns an accepted answer
   into `DRAFT` descriptions;
4. a deterministic, advisory boundary check reports how a candidate removal range relates to word
   timings, without ever moving it.

## Scope / files

Base: `038f1ce` (TXE `transcript.py`). Changed files:

- `src/davinci_ai_editor/transcript_context.py`
- `src/davinci_ai_editor/rough_cut_proposal.py`
- `src/davinci_ai_editor/cut_boundary_check.py`
- `tests/test_transcript_context.py`, `tests/test_rough_cut_proposal.py`,
  `tests/test_cut_boundary_check.py`
- `docs/LLM_001_STATUS.md`

All existing modules are unchanged. No dependency or config change.

## Schemas

### Context view (`transcript_context.py`)

- `ContextPolicy(break_gap_frames>=1, max_segment_words>=1)`; `policy_ref` is a versioned string.
- `render_transcript_context(snapshot, policy)` groups `TranscriptSnapshot.words` in producer order
  and starts a new segment when: the source-frame gap `>= break_gap_frames`, the speaker changes,
  `max_segment_words` is reached, or the timed/untimed status changes. A segment is therefore
  fully timed (`range` spans its words) or fully untimed (`range=None`, no gap).
- `ContextSegment(segment_id, word_refs, range, gap_before_frames, speaker_ref, text)`.
  `gap_before_frames` is `None` for the first segment and whenever either side is untimed.
- Rendered line: `S0007 sp1 gap=18f | text`. Speakers are aliased (`sp1`, `sp2`, `sp?` when mixed
  or absent); untimed segments render `gap=? untimed`; audio events render `[text]`. Control,
  line-separator and format characters are neutralised and `|` becomes `¦`, so producer text cannot
  forge a line or a field.
- `TranscriptContextView(view_id, transcript_id, producer_ref, policy_ref, segments,
  rendered_text, view_digest)`. `view_digest` = SHA-256 over canonical JSON of the contract
  version, transcript/source/producer identity, timing tolerance, policy, every word's
  ref/text/range/timing status/kind/speaker, all segments and the rendered text.
  `view_id = "ctxv-" + digest[:16]`. `view_matches(view, snapshot, policy)` re-renders and compares.

### LLM proposal (`rough_cut_proposal.py`)

```json
{"view_id": "ctxv-…", "view_digest": "<sha256>",
 "items": [{"op": "KEEP|REMOVE|REVIEW", "segment_ids": ["S0003", "S0004"],
            "reason_code": "<RoughCutReason>", "note": "≤ 200 chars, optional"}]}
```

`RoughCutReason`: DEAD_AIR, FALSE_START, IMMEDIATE_REPETITION, SELF_CORRECTION, RETAKE, FILLER,
OFF_TOPIC, CORE_CONTENT, UNCERTAIN (+ `UNKNOWN`, never accepted from the LLM).
`proposal_json_schema(view=None, max_items=64)` returns a stdlib-built JSON Schema 2020-12 dict
with `additionalProperties: false`; with a view it pins `view_id`/`view_digest` as `const` and
enumerates the segment IDs. The schema only narrows generation; validation always runs.

`validate_rough_cut_proposal(raw, view, *, max_items)` → `RoughCutValidationResult(view_id,
view_digest, errors, intents)`. Every error carries a `loc` path such as
`("items", 0, "segment_ids", 1)`. Codes:

| Code | Meaning |
|---|---|
| VIEW_MISMATCH | `view_id` is not the supplied view |
| STALE_DIGEST | `view_digest` differs (transcript/producer/policy changed) |
| UNKNOWN_SEGMENT | ID not in the view (incl. malformed IDs) |
| DUPLICATE_SEGMENT | ID repeated inside one item |
| OVERLAPPING_ITEMS | ID already claimed by an earlier item |
| NON_CONTIGUOUS_SEGMENTS | item IDs are not one ascending gap-free run |
| UNKNOWN_FIELD | key not in the schema |
| FORBIDDEN_FIELD | key naming start/end/time/timestamp/timecode/frame/duration/offset/path/file/directory/filter/command/script/grade/ffmpeg/render/shell/exec/url/lut/approval/apply (camel/snake insensitive) at **any depth** |
| TYPE_MISMATCH | wrong JSON type (bool is not int/str, `2.0`/`2` is not a segment ID, non-object input) |
| MISSING_FIELD | required key absent |
| INVALID_VALUE | op/reason not in the closed enum (incl. `UNKNOWN`, lowercase) |
| EMPTY | empty `items` or `segment_ids` |
| LIMIT_EXCEEDED | `items > max_items`, more IDs than the view has, nesting > 16, > 20 000 nodes, > 200 errors |
| NOTE_TOO_LONG | note > 200 characters |

Acceptance is all-or-nothing. On success each item becomes a
`TranscriptRemovalIntent(intent_id, view_id, view_digest, op, segment_ids, word_refs, reason_code,
note, status=DRAFT)`; `status` cannot be anything but `DRAFT`. Segments not mentioned are implicitly
untouched (KEEP). Intents contain no frames, geometry, EditCommand, ExecutionIR, selection or approval.

### Boundary check (`cut_boundary_check.py`)

`BoundaryPolicy(min_padding_frames, unsafe_gap_frames <= review_gap_frames)`.
`check_removal_boundaries(removal: FrameRange (source frames), snapshot, policy)` returns ordered
`BoundaryFinding(code, severity, edge START|END|JOIN, frame, word_ref, distance_frames, detail,
suggestion)`:

| Finding | Severity | Rule |
|---|---|---|
| CUTS_INSIDE_WORD | UNSAFE | edge strictly inside a timed word |
| AUDIO_EVENT_TRUNCATED | UNSAFE | edge strictly inside an AUDIO_EVENT token |
| GAP_UNSAFE | UNSAFE | silence containing the edge `< unsafe_gap_frames` |
| GAP_REVIEW | REVIEW | silence `< review_gap_frames` |
| PADDING_BELOW_MIN | REVIEW | retained neighbour keeps `< min_padding_frames` |
| NEAR_WORD_EDGE_WITHIN_TOLERANCE | REVIEW | `tolerance > 0` and edge within `snapshot.timing_tolerance_frames` of a neighbouring word edge |
| SPEAKER_HANDOFF_TIGHT | REVIEW | removal joins two different speakers with joined padding `< review_gap_frames` |
| TIMING_UNKNOWN | REVIEW | an untimed word sits between the edge's timed neighbours, or no timed words exist |

`SnapSuggestion(from_frame, to_frame, delta, within_tolerance)` is attached for inside-word
(direction that *retains* the word, ADR-018 #5) and padding findings. It is reported, never
applied; the input range is never clamped, snapped or repaired. `within_tolerance` means
`|delta| <= timing_tolerance_frames`.

## How this would feed the existing path (not implemented here)

```text
render_transcript_context → (LLM, out of scope) → validate_rough_cut_proposal
  → TranscriptRemovalIntent(DRAFT)
  → deterministic geometry from snapshot word ranges + temporal mapping (ADR-021/024)
  → check_removal_boundaries findings shown to the editor (REVIEW by default)
  → PauseEditProposal / PreparedEdit (pause_planning / orchestration.prepare_edit)
  → Safety preflight (ADR-026) → explicit BoundApproval (ADR-015)
  → apply → postflight verify (ADR-027) → promotion
```

Each arrow after validation is a separate, explicit step owned by existing contracts. A stale
view (digest mismatch) is rejected, never rebased (ADR-004/015 #5–6).

## Explicit reject list

| Rejected idea (seen in reference OSS) | Why | ADR |
|---|---|---|
| LLM-emitted ffmpeg commands / filter strings | LLM emits IR only; FORBIDDEN_FIELD | ADR-006, ADR-028 |
| LLM-emitted file paths / output names | no executable or filesystem intent from LLM | ADR-006, ADR-003 |
| LLM-invented timestamps / frames | IDs only; coordinates come from producer evidence | ADR-006, ADR-002/008 |
| Auto-render / auto-apply after proposal | proposal ≠ approval ≠ apply | ADR-015, ADR-018 #10 |
| Prose approval ("looks good") as consent | ambiguous praise is not approval; `approv*`/`apply` keys forbidden | ADR-015 #8 |
| Self-evaluation retry loops ("fix your JSON") | no blind retry; errors returned to caller, never re-prompted here | ADR-015, ADR-004 |
| Float-encoded / numeric segment IDs | TYPE_MISMATCH; bool ≠ int ≠ str | ADR-008 |
| Snapping/clamping cut edges silently | advisory only, every move reported | ADR-023 #6, ADR-024 |
| Cloud upload of media/transcripts | no network; stdlib only | ADR-007, project rules |

## What this does NOT authorize

No LLM integration, prompt shipping, or model choice. No ExecutionIR, EditCommand, geometry,
selection, approval, apply, verification or promotion. No filler/pause classification
(OPEN-009 unchanged). No Resolve access, media decode or ASR. Boundary findings are not a
Safety PASS.

## Validation

Interpreter: `.venv` Python 3.12.10 with `PYTHONPATH=<worktree>/src` (verified
`davinci_ai_editor.__file__` inside the worktree).

- targeted: `python -m pytest -q -p no:cacheprovider --basetemp=<tmp> tests/test_transcript_context.py tests/test_rough_cut_proposal.py tests/test_cut_boundary_check.py` → 130 passed
- full: `python -m pytest -q -p no:cacheprovider --basetemp=<tmp>` → 2251 passed, 2 skipped (pre-existing host skips)
- `python -m ruff check src tests tools` → all checks passed
- `python -m ruff format --check <new files>` → 6 files already formatted
- `python -m mypy` → no issues (45 files)
- `python -m mypy --strict --explicit-package-bases <new src + test files>` → no issues (6 files)
- `git diff --check` → clean

## Provenance

Concepts only, no code copied, nothing executed/imported/installed from reference repositories
(all MIT): `video-use` (`helpers/pack_transcripts.py` phrase grouping on silence/speaker change;
skill notes: never cut inside a word, padding, clean/review/unsafe silence bands),
`video-agent` (EDL quantize/snap "report every move" → reported-only `SnapSuggestion`),
`video-editor-ai-agent` (edit-plan validation collecting located errors). Because no code was
adapted, no `licenses/` file is added. No ffmpeg/render/path/filter/retry logic was reproduced.
