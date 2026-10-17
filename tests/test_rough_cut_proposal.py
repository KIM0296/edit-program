"""LLM-001 rough-cut proposal validator tests (untrusted LLM output, no LLM calls)."""

import copy
import json
from collections.abc import Callable
from typing import Any

import pytest

from davinci_ai_editor import execution_ir, orchestration
from davinci_ai_editor.domain import FrameRange
from davinci_ai_editor.rough_cut_proposal import (
    MAX_ERRORS,
    NOTE_MAX_CHARS,
    IntentStatus,
    ProposalOp,
    RejectionCode,
    RoughCutReason,
    RoughCutValidationError,
    RoughCutValidationResult,
    TranscriptRemovalIntent,
    is_forbidden_key,
    proposal_json_schema,
    validate_rough_cut_proposal,
)
from davinci_ai_editor.temporal_mapping import SourceFrameRange
from davinci_ai_editor.transcript import TranscriptSnapshot, TranscriptWord, WordTimingStatus
from davinci_ai_editor.transcript_context import (
    ContextPolicy,
    TranscriptContextView,
    render_transcript_context,
)


def _word(ref: str, text: str, start: int) -> TranscriptWord:
    rng = SourceFrameRange(FrameRange(start, start + 5))
    return TranscriptWord(ref, text, rng, WordTimingStatus.ALIGNED, speaker_ref="A")


def make_view(tolerance: int = 1) -> TranscriptContextView:
    # Five one-word segments (gap 20 >= break 10).
    words = tuple(
        _word(f"w{i}", t, i * 25) for i, t in enumerate(["어", "그러니까", "음", "네", "끝"])
    )
    snap = TranscriptSnapshot("tx-1", "src-1", "producer-ev-1", tolerance, words)
    return render_transcript_context(snap, ContextPolicy(10, 8))


VIEW = make_view()


def good() -> dict[str, Any]:
    return {
        "view_id": VIEW.view_id,
        "view_digest": VIEW.view_digest,
        "items": [
            {"op": "REMOVE", "segment_ids": ["S0002", "S0003"], "reason_code": "FALSE_START"},
            {"op": "KEEP", "segment_ids": ["S0004"], "reason_code": "CORE_CONTENT", "note": "ok"},
            {"op": "REVIEW", "segment_ids": ["S0005"], "reason_code": "UNCERTAIN"},
        ],
    }


def test_valid_proposal_yields_draft_intents_with_resolved_word_refs() -> None:
    result = validate_rough_cut_proposal(good(), VIEW)
    assert result.accepted and result.errors == ()
    first, second, third = result.intents
    assert first.op is ProposalOp.REMOVE
    assert first.segment_ids == ("S0002", "S0003")
    assert first.word_refs == ("w1", "w2")
    assert first.reason_code is RoughCutReason.FALSE_START
    assert first.status is IntentStatus.DRAFT
    assert first.intent_id == f"{VIEW.view_id}:I001"
    assert second.note == "ok" and third.op is ProposalOp.REVIEW
    assert all(i.view_digest == VIEW.view_digest for i in result.intents)


def test_validator_produces_no_execution_or_approval_objects() -> None:
    result = validate_rough_cut_proposal(good(), VIEW)
    forbidden_types = tuple(
        t
        for t in (
            getattr(execution_ir, name, None)
            for name in ("ValidatedExecutionIR", "ExecutionIR", "EditCommand")
        )
        if isinstance(t, type)
    ) + (orchestration.BoundApproval, orchestration.AuthorizedEdit, orchestration.PreparedEdit)
    for intent in result.intents:
        assert type(intent) is TranscriptRemovalIntent
        for value in vars(intent).values():
            assert not isinstance(value, forbidden_types)
            assert not isinstance(value, FrameRange | SourceFrameRange)
    with pytest.raises(ValueError, match="DRAFT"):
        TranscriptRemovalIntent(
            "i",
            "v",
            "d",
            ProposalOp.REMOVE,
            ("S0001",),
            ("w0",),
            RoughCutReason.FILLER,
            "",
            IntentStatus.UNKNOWN,
        )


def _set(path: tuple[Any, ...], value: Any) -> Callable[[dict[str, Any]], None]:
    def mutate(payload: dict[str, Any]) -> None:
        node: Any = payload
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value

    return mutate


def _delete(path: tuple[Any, ...]) -> Callable[[dict[str, Any]], None]:
    def mutate(payload: dict[str, Any]) -> None:
        node: Any = payload
        for part in path[:-1]:
            node = node[part]
        del node[path[-1]]

    return mutate


REJECTIONS: list[tuple[str, Callable[[dict[str, Any]], None], RejectionCode, tuple[Any, ...]]] = [
    ("view mismatch", _set(("view_id",), "ctxv-other"), RejectionCode.VIEW_MISMATCH, ("view_id",)),
    (
        "stale digest",
        _set(("view_digest",), "0" * 64),
        RejectionCode.STALE_DIGEST,
        ("view_digest",),
    ),
    (
        "unknown segment",
        _set(("items", 0, "segment_ids"), ["S0002", "S0099"]),
        RejectionCode.UNKNOWN_SEGMENT,
        ("items", 0, "segment_ids", 1),
    ),
    (
        "malformed segment id",
        _set(("items", 0, "segment_ids"), ["s2"]),
        RejectionCode.UNKNOWN_SEGMENT,
        ("items", 0, "segment_ids", 0),
    ),
    (
        "duplicate segment",
        _set(("items", 0, "segment_ids"), ["S0002", "S0002"]),
        RejectionCode.DUPLICATE_SEGMENT,
        ("items", 0, "segment_ids", 1),
    ),
    (
        "overlapping items",
        _set(("items", 1, "segment_ids"), ["S0003", "S0004"]),
        RejectionCode.OVERLAPPING_ITEMS,
        ("items", 1, "segment_ids", 0),
    ),
    (
        "non contiguous",
        _set(("items", 0, "segment_ids"), ["S0001", "S0003"]),
        RejectionCode.NON_CONTIGUOUS_SEGMENTS,
        ("items", 0, "segment_ids"),
    ),
    (
        "descending",
        _set(("items", 0, "segment_ids"), ["S0003", "S0002"]),
        RejectionCode.NON_CONTIGUOUS_SEGMENTS,
        ("items", 0, "segment_ids"),
    ),
    ("unknown top field", _set(("confidence",), 0.9), RejectionCode.UNKNOWN_FIELD, ("confidence",)),
    (
        "unknown item field",
        _set(("items", 0, "priority"), 1),
        RejectionCode.UNKNOWN_FIELD,
        ("items", 0, "priority"),
    ),
    (
        "forbidden start",
        _set(("items", 0, "start"), 12),
        RejectionCode.FORBIDDEN_FIELD,
        ("items", 0, "start"),
    ),
    (
        "forbidden camel",
        _set(("items", 0, "endFrame"), 12),
        RejectionCode.FORBIDDEN_FIELD,
        ("items", 0, "endFrame"),
    ),
    (
        "forbidden path",
        _set(("output_path",), "C:/x.mp4"),
        RejectionCode.FORBIDDEN_FIELD,
        ("output_path",),
    ),
    (
        "forbidden ffmpeg",
        _set(("items", 0, "ffmpeg_args"), "-ss 1"),
        RejectionCode.FORBIDDEN_FIELD,
        ("items", 0, "ffmpeg_args"),
    ),
    ("forbidden approval", _set(("approved",), True), RejectionCode.FORBIDDEN_FIELD, ("approved",)),
    (
        "op bool",
        _set(("items", 0, "op"), True),
        RejectionCode.TYPE_MISMATCH,
        ("items", 0, "op"),
    ),
    (
        "float encoded id",
        _set(("items", 0, "segment_ids"), [2.0]),
        RejectionCode.TYPE_MISMATCH,
        ("items", 0, "segment_ids", 0),
    ),
    (
        "int id",
        _set(("items", 0, "segment_ids"), [2]),
        RejectionCode.TYPE_MISMATCH,
        ("items", 0, "segment_ids", 0),
    ),
    (
        "bool id",
        _set(("items", 0, "segment_ids"), [True]),
        RejectionCode.TYPE_MISMATCH,
        ("items", 0, "segment_ids", 0),
    ),
    (
        "segment ids string",
        _set(("items", 0, "segment_ids"), "S0002"),
        RejectionCode.TYPE_MISMATCH,
        ("items", 0, "segment_ids"),
    ),
    ("items dict", _set(("items",), {"0": {}}), RejectionCode.TYPE_MISMATCH, ("items",)),
    (
        "item not object",
        _set(("items", 0), "REMOVE S0002"),
        RejectionCode.TYPE_MISMATCH,
        ("items", 0),
    ),
    ("view id int", _set(("view_id",), 7), RejectionCode.TYPE_MISMATCH, ("view_id",)),
    ("note int", _set(("items", 0, "note"), 5), RejectionCode.TYPE_MISMATCH, ("items", 0, "note")),
    ("empty items", _set(("items",), []), RejectionCode.EMPTY, ("items",)),
    (
        "empty segment ids",
        _set(("items", 0, "segment_ids"), []),
        RejectionCode.EMPTY,
        ("items", 0, "segment_ids"),
    ),
    (
        "too many segment ids",
        _set(("items", 0, "segment_ids"), ["S0001"] * 6),
        RejectionCode.LIMIT_EXCEEDED,
        ("items", 0, "segment_ids"),
    ),
    (
        "note too long",
        _set(("items", 0, "note"), "가" * (NOTE_MAX_CHARS + 1)),
        RejectionCode.NOTE_TOO_LONG,
        ("items", 0, "note"),
    ),
    ("missing items", _delete(("items",)), RejectionCode.MISSING_FIELD, ("items",)),
    (
        "missing op",
        _delete(("items", 0, "op")),
        RejectionCode.MISSING_FIELD,
        ("items", 0, "op"),
    ),
    (
        "invalid op",
        _set(("items", 0, "op"), "TRIM"),
        RejectionCode.INVALID_VALUE,
        ("items", 0, "op"),
    ),
    (
        "unknown op sentinel",
        _set(("items", 0, "op"), "UNKNOWN"),
        RejectionCode.INVALID_VALUE,
        ("items", 0, "op"),
    ),
    (
        "lowercase op",
        _set(("items", 0, "op"), "remove"),
        RejectionCode.INVALID_VALUE,
        ("items", 0, "op"),
    ),
    (
        "invalid reason",
        _set(("items", 0, "reason_code"), "BORING"),
        RejectionCode.INVALID_VALUE,
        ("items", 0, "reason_code"),
    ),
]


@pytest.mark.parametrize(
    ("mutate", "code", "loc"),
    [pytest.param(m, c, loc, id=name) for name, m, c, loc in REJECTIONS],
)
def test_every_rejection_code_with_location(
    mutate: Callable[[dict[str, Any]], None], code: RejectionCode, loc: tuple[Any, ...]
) -> None:
    payload = good()
    mutate(payload)
    result = validate_rough_cut_proposal(payload, VIEW)
    assert not result.accepted
    assert result.intents == ()
    assert (code, loc) in {(e.code, e.loc) for e in result.errors}, result.errors


def test_rejection_table_covers_every_known_code() -> None:
    covered = {code for _, _, code, _ in REJECTIONS}
    assert covered == set(RejectionCode) - {RejectionCode.UNKNOWN}


def test_note_at_limit_is_accepted() -> None:
    payload = good()
    payload["items"][0]["note"] = "가" * NOTE_MAX_CHARS
    assert validate_rough_cut_proposal(payload, VIEW).accepted


@pytest.mark.parametrize("raw", [None, "{}", 3, 1.5, True, ["items"], b"{}"])
def test_non_object_input_is_type_mismatch(raw: object) -> None:
    result = validate_rough_cut_proposal(raw, VIEW)
    assert [(e.code, e.loc) for e in result.errors] == [(RejectionCode.TYPE_MISMATCH, ())]


def test_all_errors_are_collected_not_first_only() -> None:
    payload = good()
    payload["view_digest"] = "f" * 64
    payload["items"][0]["segment_ids"] = ["S0001", "S0003"]
    payload["items"][1]["op"] = "DELETE"
    payload["items"][2]["timestamp"] = "00:01"
    codes = validate_rough_cut_proposal(payload, VIEW).codes
    assert {
        RejectionCode.STALE_DIGEST,
        RejectionCode.NON_CONTIGUOUS_SEGMENTS,
        RejectionCode.INVALID_VALUE,
        RejectionCode.FORBIDDEN_FIELD,
    } <= codes


@pytest.mark.parametrize(
    ("path", "key"),
    [
        (("items", 0, "note"), "file"),
        (("items", 0, "segment_ids"), "in_point"),
        (("extra",), "Render_Command"),
    ],
)
def test_adversarial_nested_forbidden_keys_at_any_depth(path: tuple[Any, ...], key: str) -> None:
    payload = good()
    nested: Any = {"wrapper": [{"deeper": {key: "x"}}]}
    _set(path, nested)(payload)
    result = validate_rough_cut_proposal(payload, VIEW)
    forbidden = [e for e in result.errors if e.code is RejectionCode.FORBIDDEN_FIELD]
    assert forbidden and forbidden[0].loc == (*path, "wrapper", 0, "deeper", key)
    assert not result.accepted


@pytest.mark.parametrize(
    "key",
    [
        "start",
        "END",
        "startTime",
        "time_ms",
        "timestamp",
        "src_path",
        "fileName",
        "filter_graph",
        "command",
        "lua_script",
        "grade",
        "colorGrade",
        "ffmpeg",
        "out",
        "TC",
        "approval",
        "applyNow",
    ],
)
def test_forbidden_key_classifier(key: str) -> None:
    assert is_forbidden_key(key)


@pytest.mark.parametrize("key", ["op", "note", "segment_ids", "view_id", "view_digest", "items"])
def test_schema_keys_are_not_forbidden(key: str) -> None:
    assert not is_forbidden_key(key)


def test_stale_digest_after_transcript_retiming() -> None:
    payload = good()
    retimed = make_view(tolerance=2)  # same words, different producer tolerance
    result = validate_rough_cut_proposal(payload, retimed)
    assert {RejectionCode.VIEW_MISMATCH, RejectionCode.STALE_DIGEST} <= result.codes


def test_huge_item_list_is_bounded() -> None:
    payload = good()
    payload["items"] = [copy.deepcopy(payload["items"][2]) for _ in range(100_000)]
    result = validate_rough_cut_proposal(payload, VIEW, max_items=8)
    assert RejectionCode.LIMIT_EXCEEDED in result.codes
    assert len(result.errors) <= MAX_ERRORS + 1


def test_deep_nesting_is_bounded() -> None:
    payload = good()
    deep: Any = "x"
    for _ in range(5_000):
        deep = [deep]
    payload["items"][0]["note"] = deep
    result = validate_rough_cut_proposal(payload, VIEW)
    assert RejectionCode.LIMIT_EXCEEDED in result.codes


def test_max_items_limit_and_argument_validation() -> None:
    result = validate_rough_cut_proposal(good(), VIEW, max_items=2)
    assert (RejectionCode.LIMIT_EXCEEDED, ("items",)) in {(e.code, e.loc) for e in result.errors}
    with pytest.raises(ValueError):
        validate_rough_cut_proposal(good(), VIEW, max_items=0)
    with pytest.raises(TypeError):
        validate_rough_cut_proposal(good(), "view")  # type: ignore[arg-type]


def test_json_round_trip_input_is_accepted() -> None:
    assert validate_rough_cut_proposal(json.loads(json.dumps(good())), VIEW).accepted


def test_result_invariants() -> None:
    err = RoughCutValidationError(RejectionCode.EMPTY, ("items",), "empty")
    intent = validate_rough_cut_proposal(good(), VIEW).intents[0]
    with pytest.raises(ValueError):
        RoughCutValidationResult(VIEW.view_id, VIEW.view_digest, (err,), (intent,))
    with pytest.raises(ValueError):
        RoughCutValidationResult(VIEW.view_id, VIEW.view_digest, (), ())
    with pytest.raises(ValueError):
        RoughCutValidationResult("other", VIEW.view_digest, (), (intent,))
    with pytest.raises(TypeError):
        RoughCutValidationError(RejectionCode.UNKNOWN, (), "x")


def test_json_schema_is_stdlib_json_and_pins_view() -> None:
    generic = proposal_json_schema()
    json.dumps(generic)
    assert generic["additionalProperties"] is False
    pinned = proposal_json_schema(VIEW, max_items=5)
    text = json.dumps(pinned, ensure_ascii=False)
    assert VIEW.view_digest in text and "S0005" in text
    props: Any = pinned["properties"]
    item = props["items"]["items"]
    assert item["additionalProperties"] is False
    assert set(item["properties"]) == {"op", "segment_ids", "reason_code", "note"}
    assert "UNKNOWN" not in item["properties"]["op"]["enum"]
    assert "UNKNOWN" not in item["properties"]["reason_code"]["enum"]
    assert props["items"]["maxItems"] == 5
    for word in ("start", 'end"', "path", "ffmpeg", "timestamp"):
        assert f'"{word}' not in text
