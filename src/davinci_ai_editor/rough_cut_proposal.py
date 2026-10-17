"""LLM-001: validate an LLM rough-cut proposal against an ID-only context view.

The LLM may emit ONLY semantic IR (ADR-006)::

    {"view_id": "...", "view_digest": "...",
     "items": [{"op": "KEEP|REMOVE|REVIEW", "segment_ids": ["S0003", "S0004"],
                "reason_code": "<RoughCutReason>", "note": "<= 200 chars"}]}

:func:`validate_rough_cut_proposal` treats the payload as untrusted data. It
collects every problem with a location path (pydantic-style ``loc``) instead of
stopping at the first one, and accepts all-or-nothing: a single error yields no
intents at all (no partial apply, no repair, no clamping, no blind retry).

On success it returns :class:`TranscriptRemovalIntent` descriptions with status
``DRAFT``. They name segments and the word refs those segments resolve to; they
carry no frames, no geometry, no EditCommand, no ExecutionIR and no approval.
Feeding the existing path is a separate, explicit step (see
``docs/LLM_001_STATUS.md``)::

    TranscriptRemovalIntent(DRAFT)
      -> deterministic geometry resolution from snapshot word ranges
         + cut_boundary_check advisory findings (human-reviewed)
      -> PauseEditProposal / PreparedEdit (orchestration.prepare_edit)
      -> Safety preflight -> explicit BoundApproval -> apply -> postflight verify
      -> promotion (ADR-015)

The validator never calls an LLM and never asks one to "fix" its output.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise

from .transcript_context import SEGMENT_ID_PATTERN, TranscriptContextView

PROPOSAL_CONTRACT_VERSION = "llm-001-rough-cut-v1"
NOTE_MAX_CHARS = 200
DEFAULT_MAX_ITEMS = 64
MAX_NESTING_DEPTH = 16
MAX_SCANNED_NODES = 20_000
MAX_ERRORS = 200

_TOP_KEYS = ("view_id", "view_digest", "items")
_ITEM_KEYS = ("op", "segment_ids", "reason_code", "note")
_REQUIRED_ITEM_KEYS = ("op", "segment_ids", "reason_code")

# Any key containing one of these fragments (case/separator-insensitive) is a
# forbidden attempt to smuggle coordinates, files or executable intent.
_FORBIDDEN_FRAGMENTS = (
    "start",
    "end",
    "time",
    "timestamp",
    "timecode",
    "frame",
    "second",
    "duration",
    "offset",
    "path",
    "file",
    "folder",
    "directory",
    "filter",
    "command",
    "script",
    "grade",
    "ffmpeg",
    "render",
    "shell",
    "exec",
    "url",
    "lut",
    "approv",
)
# Short tokens that only count as whole words (``in_point`` -> ``in``).
_FORBIDDEN_TOKENS = frozenset(
    {"in", "out", "tc", "ms", "sec", "cmd", "uri", "dir", "lua", "py", "code", "apply"}
)


class ProposalOp(str, Enum):
    KEEP = "KEEP"
    REMOVE = "REMOVE"
    REVIEW = "REVIEW"
    UNKNOWN = "UNKNOWN"


class RoughCutReason(str, Enum):
    DEAD_AIR = "DEAD_AIR"
    FALSE_START = "FALSE_START"
    IMMEDIATE_REPETITION = "IMMEDIATE_REPETITION"
    SELF_CORRECTION = "SELF_CORRECTION"
    RETAKE = "RETAKE"
    FILLER = "FILLER"
    OFF_TOPIC = "OFF_TOPIC"
    CORE_CONTENT = "CORE_CONTENT"
    UNCERTAIN = "UNCERTAIN"
    UNKNOWN = "UNKNOWN"


class IntentStatus(str, Enum):
    DRAFT = "DRAFT"
    UNKNOWN = "UNKNOWN"


class RejectionCode(str, Enum):
    VIEW_MISMATCH = "VIEW_MISMATCH"
    STALE_DIGEST = "STALE_DIGEST"
    UNKNOWN_SEGMENT = "UNKNOWN_SEGMENT"
    DUPLICATE_SEGMENT = "DUPLICATE_SEGMENT"
    OVERLAPPING_ITEMS = "OVERLAPPING_ITEMS"
    NON_CONTIGUOUS_SEGMENTS = "NON_CONTIGUOUS_SEGMENTS"
    UNKNOWN_FIELD = "UNKNOWN_FIELD"
    FORBIDDEN_FIELD = "FORBIDDEN_FIELD"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    MISSING_FIELD = "MISSING_FIELD"
    INVALID_VALUE = "INVALID_VALUE"
    EMPTY = "EMPTY"
    LIMIT_EXCEEDED = "LIMIT_EXCEEDED"
    NOTE_TOO_LONG = "NOTE_TOO_LONG"
    UNKNOWN = "UNKNOWN"


Loc = tuple[str | int, ...]

_SELECTABLE_OPS = tuple(op.value for op in ProposalOp if op is not ProposalOp.UNKNOWN)
_SELECTABLE_REASONS = tuple(r.value for r in RoughCutReason if r is not RoughCutReason.UNKNOWN)


@dataclass(frozen=True)
class RoughCutValidationError:
    code: RejectionCode
    loc: Loc
    message: str

    def __post_init__(self) -> None:
        if not isinstance(self.code, RejectionCode) or self.code is RejectionCode.UNKNOWN:
            raise TypeError("Typed, known rejection code required")
        loc = tuple(self.loc)
        if any(type(part) not in (str, int) for part in loc):
            raise TypeError("Location parts must be str or int")
        object.__setattr__(self, "loc", loc)
        if not isinstance(self.message, str) or not self.message.strip():
            raise ValueError("Nonblank error message required")


@dataclass(frozen=True)
class TranscriptRemovalIntent:
    """A DRAFT description of what the LLM proposed for a contiguous segment run.

    Not a selection, approval, geometry, EditCommand or ExecutionIR. KEEP and
    REVIEW intents are recorded too so the reviewer sees the full proposal.
    """

    intent_id: str
    view_id: str
    view_digest: str
    op: ProposalOp
    segment_ids: tuple[str, ...]
    word_refs: tuple[str, ...]
    reason_code: RoughCutReason
    note: str
    status: IntentStatus = IntentStatus.DRAFT

    def __post_init__(self) -> None:
        for value in (self.intent_id, self.view_id, self.view_digest):
            if not isinstance(value, str) or not value.strip():
                raise ValueError("Explicit intent/view identity required")
        if not isinstance(self.op, ProposalOp) or self.op is ProposalOp.UNKNOWN:
            raise ValueError("Known proposal op required")
        if not isinstance(self.reason_code, RoughCutReason) or (
            self.reason_code is RoughCutReason.UNKNOWN
        ):
            raise ValueError("Known reason code required")
        if self.status is not IntentStatus.DRAFT:
            raise ValueError("LLM-derived intents are DRAFT only; approval lives elsewhere")
        segment_ids = tuple(self.segment_ids)
        word_refs = tuple(self.word_refs)
        if not segment_ids or not word_refs:
            raise ValueError("Intent must reference segments and resolved words")
        if any(not isinstance(s, str) or not SEGMENT_ID_PATTERN.match(s) for s in segment_ids):
            raise ValueError("Segment IDs must look like S0001")
        if len(set(segment_ids)) != len(segment_ids) or len(set(word_refs)) != len(word_refs):
            raise ValueError("Intent references must be unique")
        if not isinstance(self.note, str) or len(self.note) > NOTE_MAX_CHARS:
            raise ValueError("Note must be a string of at most 200 characters")
        object.__setattr__(self, "segment_ids", segment_ids)
        object.__setattr__(self, "word_refs", word_refs)


@dataclass(frozen=True)
class RoughCutValidationResult:
    view_id: str
    view_digest: str
    errors: tuple[RoughCutValidationError, ...]
    intents: tuple[TranscriptRemovalIntent, ...]

    def __post_init__(self) -> None:
        errors = tuple(self.errors)
        intents = tuple(self.intents)
        if any(not isinstance(e, RoughCutValidationError) for e in errors):
            raise TypeError("Typed errors required")
        if any(not isinstance(i, TranscriptRemovalIntent) for i in intents):
            raise TypeError("Typed intents required")
        if errors and intents:
            raise ValueError("Rejected proposals carry no intents (all-or-nothing)")
        if not errors and not intents:
            raise ValueError("Accepted proposals carry at least one intent")
        if any(i.view_id != self.view_id or i.view_digest != self.view_digest for i in intents):
            raise ValueError("Intents must bind the validated view")
        object.__setattr__(self, "errors", errors)
        object.__setattr__(self, "intents", intents)

    @property
    def accepted(self) -> bool:
        return not self.errors

    @property
    def codes(self) -> frozenset[RejectionCode]:
        return frozenset(e.code for e in self.errors)


class _Collector:
    def __init__(self) -> None:
        self.errors: list[RoughCutValidationError] = []
        self.truncated = False

    def add(self, code: RejectionCode, loc: Loc, message: str) -> None:
        if len(self.errors) >= MAX_ERRORS:
            self.truncated = True
            return
        self.errors.append(RoughCutValidationError(code, loc, message))

    def finish(self) -> tuple[RoughCutValidationError, ...]:
        if self.truncated:
            self.errors.append(
                RoughCutValidationError(
                    RejectionCode.LIMIT_EXCEEDED, (), f"More than {MAX_ERRORS} errors"
                )
            )
        return tuple(self.errors)


def _key_tokens(key: str) -> list[str]:
    spaced = ""
    for i, ch in enumerate(key):
        if ch.isupper() and i and key[i - 1].islower():
            spaced += " "
        spaced += ch if ch.isalnum() else " "
    return spaced.lower().split()


def is_forbidden_key(key: str) -> bool:
    """True when ``key`` names a coordinate, file, filter, command, grade or approval."""

    tokens = _key_tokens(key)
    joined = "".join(tokens)
    return any(fragment in joined for fragment in _FORBIDDEN_FRAGMENTS) or any(
        token in _FORBIDDEN_TOKENS for token in tokens
    )


def _allowed_at(loc: Loc) -> tuple[str, ...]:
    if loc == ():
        return _TOP_KEYS
    if len(loc) == 2 and loc[0] == "items" and type(loc[1]) is int:
        return _ITEM_KEYS
    return ()


def _scan(raw: object, out: _Collector) -> set[Loc]:
    """Iterative whole-tree scan. Returns locations of forbidden keys."""

    forbidden: set[Loc] = set()
    stack: list[tuple[object, Loc]] = [(raw, ())]
    seen = 0
    while stack:
        node, loc = stack.pop()
        seen += 1
        if seen > MAX_SCANNED_NODES:
            out.add(RejectionCode.LIMIT_EXCEEDED, (), "Payload has too many nodes")
            return forbidden
        if len(loc) > MAX_NESTING_DEPTH:
            out.add(RejectionCode.LIMIT_EXCEEDED, loc, "Payload is nested too deeply")
            continue
        if isinstance(node, Mapping):
            allowed = _allowed_at(loc)
            children: list[tuple[object, Loc]] = []
            for key, value in node.items():
                if not isinstance(key, str):
                    out.add(RejectionCode.TYPE_MISMATCH, (*loc, repr(key)), "Keys must be strings")
                    continue
                child = (*loc, key)
                if key not in allowed and is_forbidden_key(key):
                    out.add(
                        RejectionCode.FORBIDDEN_FIELD,
                        child,
                        "Coordinates, files, filters, commands, grades and approvals "
                        "are never accepted from an LLM",
                    )
                    forbidden.add(child)
                children.append((value, child))
            stack.extend(reversed(children))
        elif isinstance(node, list | tuple):
            budget = MAX_SCANNED_NODES - seen - len(stack) + 1
            if len(node) > budget:
                out.add(RejectionCode.LIMIT_EXCEEDED, loc, "Payload list is too large to scan")
                return forbidden
            stack.extend((node[i], (*loc, i)) for i in range(len(node) - 1, -1, -1))
    return forbidden


def _type_name(value: object) -> str:
    return type(value).__name__


def _expect_str(value: object, loc: Loc, out: _Collector) -> str | None:
    if type(value) is not str:
        out.add(RejectionCode.TYPE_MISMATCH, loc, f"Expected string, got {_type_name(value)}")
        return None
    return value


def _check_keys(
    node: Mapping[object, object],
    loc: Loc,
    allowed: tuple[str, ...],
    required: tuple[str, ...],
    forbidden: set[Loc],
    out: _Collector,
) -> None:
    for key in node:
        if isinstance(key, str) and key not in allowed and (*loc, key) not in forbidden:
            out.add(RejectionCode.UNKNOWN_FIELD, (*loc, key), "Field is not part of the schema")
    for key in required:
        if key not in node:
            out.add(RejectionCode.MISSING_FIELD, (*loc, key), "Required field is missing")


@dataclass(frozen=True)
class _ParsedItem:
    index: int
    op: ProposalOp
    segment_ids: tuple[str, ...]
    reason: RoughCutReason
    note: str


def _validate_item(
    item: object,
    index: int,
    view: TranscriptContextView,
    claimed: dict[str, int],
    forbidden: set[Loc],
    out: _Collector,
) -> _ParsedItem | None:
    loc: Loc = ("items", index)
    if not isinstance(item, Mapping):
        out.add(RejectionCode.TYPE_MISMATCH, loc, f"Expected object, got {_type_name(item)}")
        return None
    _check_keys(item, loc, _ITEM_KEYS, _REQUIRED_ITEM_KEYS, forbidden, out)
    before = len(out.errors)

    op: ProposalOp | None = None
    if "op" in item:
        raw_op = _expect_str(item["op"], (*loc, "op"), out)
        if raw_op is not None:
            if raw_op in _SELECTABLE_OPS:
                op = ProposalOp(raw_op)
            else:
                out.add(RejectionCode.INVALID_VALUE, (*loc, "op"), "Op must be KEEP/REMOVE/REVIEW")

    reason: RoughCutReason | None = None
    if "reason_code" in item:
        raw_reason = _expect_str(item["reason_code"], (*loc, "reason_code"), out)
        if raw_reason is not None:
            if raw_reason in _SELECTABLE_REASONS:
                reason = RoughCutReason(raw_reason)
            else:
                out.add(RejectionCode.INVALID_VALUE, (*loc, "reason_code"), "Unknown reason code")

    note = ""
    if "note" in item:
        raw_note = _expect_str(item["note"], (*loc, "note"), out)
        if raw_note is not None:
            if len(raw_note) > NOTE_MAX_CHARS:
                out.add(
                    RejectionCode.NOTE_TOO_LONG,
                    (*loc, "note"),
                    f"Note exceeds {NOTE_MAX_CHARS} characters",
                )
            note = raw_note

    segment_ids: list[str] = []
    if "segment_ids" in item:
        seg_loc: Loc = (*loc, "segment_ids")
        raw_ids = item["segment_ids"]
        if not isinstance(raw_ids, list):
            out.add(
                RejectionCode.TYPE_MISMATCH, seg_loc, f"Expected list, got {_type_name(raw_ids)}"
            )
        elif not raw_ids:
            out.add(RejectionCode.EMPTY, seg_loc, "At least one segment ID required")
        elif len(raw_ids) > len(view.segments):
            out.add(
                RejectionCode.LIMIT_EXCEEDED, seg_loc, "More segment IDs than the view contains"
            )
        else:
            positions: list[int] = []
            local: set[str] = set()
            for j, raw_id in enumerate(raw_ids):
                id_loc: Loc = (*seg_loc, j)
                seg_id = _expect_str(raw_id, id_loc, out)
                if seg_id is None:
                    continue
                position = view.segment_index(seg_id)
                if position is None:
                    out.add(RejectionCode.UNKNOWN_SEGMENT, id_loc, "Segment ID not in the view")
                    continue
                if seg_id in local:
                    out.add(RejectionCode.DUPLICATE_SEGMENT, id_loc, "Segment repeated in item")
                    continue
                local.add(seg_id)
                if seg_id in claimed:
                    out.add(
                        RejectionCode.OVERLAPPING_ITEMS,
                        id_loc,
                        f"Segment already claimed by items[{claimed[seg_id]}]",
                    )
                else:
                    claimed[seg_id] = index
                positions.append(position)
                segment_ids.append(seg_id)
            if any(b != a + 1 for a, b in pairwise(positions)):
                out.add(
                    RejectionCode.NON_CONTIGUOUS_SEGMENTS,
                    seg_loc,
                    "Segments must be one ascending, gap-free run",
                )

    if len(out.errors) != before or op is None or reason is None or not segment_ids:
        return None
    return _ParsedItem(index, op, tuple(segment_ids), reason, note)


def validate_rough_cut_proposal(
    raw: object, view: TranscriptContextView, *, max_items: int = DEFAULT_MAX_ITEMS
) -> RoughCutValidationResult:
    """Validate untrusted LLM output. Collects all errors; accepts all-or-nothing."""

    if not isinstance(view, TranscriptContextView):
        raise TypeError("Typed context view required")
    if type(max_items) is not int or max_items < 1:
        raise ValueError("Positive integer max_items required")

    out = _Collector()

    def result(intents: tuple[TranscriptRemovalIntent, ...] = ()) -> RoughCutValidationResult:
        return RoughCutValidationResult(view.view_id, view.view_digest, out.finish(), intents)

    if not isinstance(raw, Mapping):
        out.add(RejectionCode.TYPE_MISMATCH, (), f"Expected object, got {_type_name(raw)}")
        return result()

    forbidden = _scan(raw, out)
    _check_keys(raw, (), _TOP_KEYS, _TOP_KEYS, forbidden, out)

    if "view_id" in raw:
        view_id = _expect_str(raw["view_id"], ("view_id",), out)
        if view_id is not None and view_id != view.view_id:
            out.add(RejectionCode.VIEW_MISMATCH, ("view_id",), "Proposal targets another view")
    if "view_digest" in raw:
        digest = _expect_str(raw["view_digest"], ("view_digest",), out)
        if digest is not None and digest != view.view_digest:
            out.add(
                RejectionCode.STALE_DIGEST,
                ("view_digest",),
                "Proposal was made against a different transcript/policy state",
            )

    parsed: list[_ParsedItem] = []
    if "items" in raw:
        items = raw["items"]
        if not isinstance(items, list):
            out.add(
                RejectionCode.TYPE_MISMATCH, ("items",), f"Expected list, got {_type_name(items)}"
            )
        elif not items:
            out.add(RejectionCode.EMPTY, ("items",), "At least one item required")
        else:
            if len(items) > max_items:
                out.add(
                    RejectionCode.LIMIT_EXCEEDED,
                    ("items",),
                    f"{len(items)} items exceed the limit of {max_items}",
                )
            claimed: dict[str, int] = {}
            for index, item in enumerate(items[:max_items]):
                item_result = _validate_item(item, index, view, claimed, forbidden, out)
                if item_result is not None:
                    parsed.append(item_result)

    if out.errors:
        return result()
    intents = tuple(
        TranscriptRemovalIntent(
            intent_id=f"{view.view_id}:I{p.index + 1:03d}",
            view_id=view.view_id,
            view_digest=view.view_digest,
            op=p.op,
            segment_ids=p.segment_ids,
            word_refs=tuple(
                ref
                for seg_id in p.segment_ids
                for ref in view.segments[_index(view, seg_id)].word_refs
            ),
            reason_code=p.reason,
            note=p.note,
        )
        for p in parsed
    )
    return result(intents)


def _index(view: TranscriptContextView, segment_id: str) -> int:
    index = view.segment_index(segment_id)
    if index is None:  # pragma: no cover - guarded by validation
        raise KeyError(segment_id)
    return index


def proposal_json_schema(
    view: TranscriptContextView | None = None, *, max_items: int = DEFAULT_MAX_ITEMS
) -> dict[str, object]:
    """JSON Schema (2020-12) for LLM structured output. Built with stdlib dicts.

    With a ``view`` the schema pins ``view_id``/``view_digest`` and enumerates
    the valid segment IDs. The schema narrows generation; it is NOT a substitute
    for :func:`validate_rough_cut_proposal`, which always runs.
    """

    if type(max_items) is not int or max_items < 1:
        raise ValueError("Positive integer max_items required")
    segment_id: dict[str, object] = {"type": "string", "pattern": SEGMENT_ID_PATTERN.pattern}
    view_id: dict[str, object] = {"type": "string", "minLength": 1}
    view_digest: dict[str, object] = {"type": "string", "pattern": "^[0-9a-f]{64}$"}
    max_segments: int | None = None
    if view is not None:
        if not isinstance(view, TranscriptContextView):
            raise TypeError("Typed context view required")
        segment_id = {"type": "string", "enum": [s.segment_id for s in view.segments]}
        view_id = {"type": "string", "const": view.view_id}
        view_digest = {"type": "string", "const": view.view_digest}
        max_segments = len(view.segments)
    segment_ids: dict[str, object] = {
        "type": "array",
        "items": segment_id,
        "minItems": 1,
        "uniqueItems": True,
    }
    if max_segments is not None:
        segment_ids["maxItems"] = max_segments
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": f"urn:davinci-ai-editor:{PROPOSAL_CONTRACT_VERSION}",
        "title": "RoughCutProposal",
        "type": "object",
        "additionalProperties": False,
        "required": list(_TOP_KEYS),
        "properties": {
            "view_id": view_id,
            "view_digest": view_digest,
            "items": {
                "type": "array",
                "minItems": 1,
                "maxItems": max_items,
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(_REQUIRED_ITEM_KEYS),
                    "properties": {
                        "op": {"type": "string", "enum": list(_SELECTABLE_OPS)},
                        "segment_ids": segment_ids,
                        "reason_code": {"type": "string", "enum": list(_SELECTABLE_REASONS)},
                        "note": {"type": "string", "maxLength": NOTE_MAX_CHARS},
                    },
                },
            },
        },
    }
