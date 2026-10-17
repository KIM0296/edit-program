"""PVP-001C derived cut-candidate geometry from silence regions.

Derived geometry only. PCM silence is not editorial meaning and non-silence is
not speech. Nothing here emits an edit action, a cut decision, a ContentMode or a
semantic label. Raw SILENCE_REGION evidence is never modified: every function
returns new values and each derived artifact names its source region(s) and every
transformation (handles, bridging, drops) applied to them.

Two layers:

1. ``apply_margin`` / ``smooth_runs``: a faithful integer-frame port of
   auto-editor's ``mutMargin`` and ``smoothing`` on a per-frame boolean "active"
   (non-silent) sequence, applied in auto-editor order (margin, then smoothing).
2. ``CutGeometryPolicy`` / ``bridge_short_active_gaps`` /
   ``derive_cut_candidate_geometry``: the project contract over typed silence
   ``FrameRange`` regions inside an analysis window.

Intentional differences from auto-editor (see docs/PVP_001C_STATUS.md):

- Pure functions: inputs are copied and a new tuple is returned (auto-editor
  mutates the sequence in place).
- Integer frames only; no seconds, no ``toTb`` rounding and no default values.
  auto-editor's CLI defaults (margin 0.2s, smooth 0.2s,0.1s) are NOT adopted.
- Strict typing: elements must be ``bool``; frame counts must be ``int`` (``bool``
  rejected). ``smooth_runs`` refuses negative thresholds (auto-editor treats a
  negative threshold as a no-op).
- ``smooth_runs`` keeps the fixed-point loop and its 2-cycle guard but raises
  ``RuntimeError`` after a generous iteration bound instead of looping forever
  should a longer cycle ever occur.
- Contract layer only: window-edge active runs are never bridged (their true
  length beyond the window is unknown), whereas auto-editor's minclip also flips
  short active runs touching the sequence edges. Contract bridging is a single
  ordered pass after handles; with both ``max_bridge_frames`` and
  ``min_cut_frames`` nonzero it is not claimed equivalent to auto-editor's
  simultaneous fixed-point smoothing.
"""

import hashlib
import json
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from itertools import pairwise

from .domain import FrameRange

DERIVATION = "PVP-001C-geometry-v1"
AUTHORIZATION_STATEMENT = (
    "DERIVED_GEOMETRY_ONLY: authorizes no edit action, cut decision, ContentMode or "
    "semantic label; bridged frames are not claimed to be non-speech; policy values "
    "are uncalibrated and raw silence evidence is unchanged."
)


def _int(name: str, value: object, *, nonnegative: bool) -> int:
    if type(value) is not int:
        raise TypeError(f"{name} must be an int (bool rejected)")
    if nonnegative and value < 0:
        raise ValueError(f"{name} must be >= 0")
    return value


def _bools(active: Sequence[bool]) -> list[bool]:
    if isinstance(active, (str, bytes)) or not isinstance(active, Sequence):
        raise TypeError("active must be a sequence of bool")
    values = list(active)
    if any(type(v) is not bool for v in values):
        raise TypeError("active elements must be bool (ints rejected)")
    return values


# ---------------------------------------------------------------------------
# Layer 1: ported auto-editor functions.
# Adapted from auto-editor src/lib/editutil.nim (Unlicense): `mutMargin`, `smoothing`.
# Adapted from auto-editor src/conductor.nim (Unlicense): margin, then smoothing.
# License text: licenses/auto-editor-LICENSE.txt (public domain dedication).
# ---------------------------------------------------------------------------


def apply_margin(
    active: Sequence[bool], start_margin_frames: int, end_margin_frames: int
) -> tuple[bool, ...]:
    """Port of auto-editor ``mutMargin``; returns a new sequence.

    Transitions are located on the input once. A positive start margin marks the
    ``start_margin_frames`` frames before each inactive->active transition active;
    a negative one marks the first ``-start_margin_frames`` frames of the active
    run inactive. A positive end margin marks the frames after each
    active->inactive transition active; a negative one marks the last frames of
    the active run inactive. Start margins are applied before end margins.
    Sequence edges are not transitions, so edge runs get no margin.
    """
    arr = _bools(active)
    start_m = _int("start_margin_frames", start_margin_frames, nonnegative=False)
    end_m = _int("end_margin_frames", end_margin_frames, nonnegative=False)
    arrlen = len(arr)
    start_index: list[int] = []
    end_index: list[int] = []
    for j in range(1, arrlen):
        if arr[j] != arr[j - 1]:
            if arr[j]:
                start_index.append(j)
            else:
                end_index.append(j)

    if start_m > 0:
        for i in start_index:
            for k in range(max(i - start_m, 0), i):
                arr[k] = True
    if start_m < 0:
        for i in start_index:
            for k in range(i, min(i - start_m, arrlen)):
                arr[k] = False
    if end_m > 0:
        for i in end_index:
            for k in range(i, min(i + end_m, arrlen)):
                arr[k] = True
    if end_m < 0:
        for i in end_index:
            for k in range(max(i + end_m, 0), i):
                arr[k] = False
    return tuple(arr)


def smooth_runs(
    active: Sequence[bool], min_cut_frames: int, min_clip_frames: int
) -> tuple[bool, ...]:
    """Port of auto-editor ``smoothing``; returns a new sequence.

    Each iteration reads the previous state: active runs shorter than
    ``min_clip_frames`` become inactive and inactive runs shorter than
    ``min_cut_frames`` become active (edge runs included). Iterates to a fixed
    point; a 2-cycle (state equal to two iterations back) also terminates.
    """
    val = _bools(active)
    mincut = _int("min_cut_frames", min_cut_frames, nonnegative=True)
    minclip = _int("min_clip_frames", min_clip_frames, nonnegative=True)
    prev: list[bool] = []
    prev2: list[bool] = []
    bound = 4 * len(val) + 8
    iterations = 0
    while prev != val and prev2 != val:
        iterations += 1
        if iterations > bound:
            raise RuntimeError("smoothing did not converge within the iteration bound")
        prev2 = prev
        prev = val
        nxt = list(prev)
        last = len(prev) - 1

        start_p = 0
        in_run = False
        for j, item in enumerate(prev):
            if item:
                if not in_run:
                    start_p = j
                    in_run = True
                # j is the run's last index here (inclusive), hence the +1.
                if j == last and j - start_p + 1 < minclip:
                    for i in range(start_p, len(prev)):
                        nxt[i] = False
            elif in_run:
                if j - start_p < minclip:
                    for i in range(start_p, j):
                        nxt[i] = False
                in_run = False

        start_p = 0
        in_run = False
        for j, item in enumerate(prev):
            if not item:
                if not in_run:
                    start_p = j
                    in_run = True
                if j == last and j - start_p + 1 < mincut:
                    for i in range(start_p, len(prev)):
                        nxt[i] = True
            elif in_run:
                if j - start_p < mincut:
                    for i in range(start_p, j):
                        nxt[i] = True
                in_run = False

        val = nxt
    return tuple(val)


# ---------------------------------------------------------------------------
# Layer 2: project contract over silence FrameRange regions.
# ---------------------------------------------------------------------------


def _digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


@dataclass(frozen=True)
class CutGeometryPolicy:
    """Explicit, uncalibrated geometry parameters in integer frames.

    ``head_keep_frames``: silence kept after preceding non-silence (auto-editor
    end margin). ``tail_keep_frames``: silence kept before following non-silence
    (auto-editor start margin). ``max_bridge_frames``: interior active gaps of at
    most this many frames between derived interiors are bridged (auto-editor
    minclip = max_bridge_frames + 1). ``min_cut_frames``: derived spans shorter
    than this are dropped (auto-editor mincut). No value is a recommendation.
    """

    head_keep_frames: int
    tail_keep_frames: int
    max_bridge_frames: int
    min_cut_frames: int

    def __post_init__(self) -> None:
        for name in ("head_keep_frames", "tail_keep_frames", "max_bridge_frames", "min_cut_frames"):
            _int(name, getattr(self, name), nonnegative=True)

    @property
    def policy_ref(self) -> str:
        return "cut-geometry-policy:" + _digest(
            [
                DERIVATION,
                self.head_keep_frames,
                self.tail_keep_frames,
                self.max_bridge_frames,
                self.min_cut_frames,
            ]
        )


def _validate_regions(regions: Sequence[FrameRange], window: FrameRange) -> tuple[FrameRange, ...]:
    if not isinstance(window, FrameRange):
        raise TypeError("Typed FrameRange window required")
    if isinstance(regions, (str, bytes)) or not isinstance(regions, Sequence):
        raise TypeError("Sequence of FrameRange silence regions required")
    out = tuple(regions)
    if any(not isinstance(r, FrameRange) for r in out):
        raise TypeError("Silence regions must be FrameRange")
    for r in out:
        if not window.contains(r):
            raise ValueError("Silence region outside the analysis window")
    for a, b in pairwise(out):
        if b.start <= a.end:
            raise ValueError("Silence regions must be ordered, nonoverlapping and non-touching")
    return out


@dataclass(frozen=True)
class BridgedGroup:
    """Consecutive spans joined across short active gaps.

    ``bridged`` lists every gap absorbed. Those frames were non-silent; bridging
    is geometry only and does not claim they are not speech.
    """

    members: tuple[FrameRange, ...]
    span: FrameRange
    bridged: tuple[FrameRange, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "members", tuple(self.members))
        object.__setattr__(self, "bridged", tuple(self.bridged))
        if not self.members or any(not isinstance(m, FrameRange) for m in self.members):
            raise TypeError("Nonempty FrameRange members required")
        if any(not isinstance(g, FrameRange) for g in self.bridged):
            raise TypeError("Bridged gaps must be FrameRange")
        expected = tuple(FrameRange(a.end, b.start) for a, b in pairwise(self.members))
        if self.bridged != expected:
            raise ValueError("Bridged gaps must be exactly the gaps between members")
        if self.span != FrameRange(self.members[0].start, self.members[-1].end):
            raise ValueError("Span must run from first member start to last member end")


def _bridge(spans: Sequence[FrameRange], max_bridge_frames: int) -> tuple[BridgedGroup, ...]:
    groups: list[list[FrameRange]] = []
    for s in spans:
        if groups and s.start - groups[-1][-1].end <= max_bridge_frames:
            groups[-1].append(s)
        else:
            groups.append([s])
    return tuple(
        BridgedGroup(
            tuple(g),
            FrameRange(g[0].start, g[-1].end),
            tuple(FrameRange(a.end, b.start) for a, b in pairwise(g)),
        )
        for g in groups
    )


def bridge_short_active_gaps(
    regions: Sequence[FrameRange], window: FrameRange, max_bridge_frames: int
) -> tuple[BridgedGroup, ...]:
    """Single left-to-right pass joining regions across gaps <= max_bridge_frames.

    The gap is measured from the end of the current group's last member to the
    next region. Active runs touching the window edges are never bridged. Input
    regions are returned untouched inside the groups.
    """
    checked = _validate_regions(regions, window)
    limit = _int("max_bridge_frames", max_bridge_frames, nonnegative=True)
    return _bridge(checked, limit)


class DroppedReason(str, Enum):
    DROPPED_EMPTY_AFTER_HANDLES = "DROPPED_EMPTY_AFTER_HANDLES"
    DROPPED_TOO_SHORT = "DROPPED_TOO_SHORT"
    MERGED_INTO_PRECEDING_SPAN = "MERGED_INTO_PRECEDING_SPAN"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class DerivedCutSpan:
    """Derived candidate geometry for ``source_region`` (and any merged regions).

    ``interior`` = source start + ``head_keep`` .. last merged region end -
    ``tail_keep``. ``merged_regions`` are later source regions joined by bridging;
    ``bridged`` are the absorbed gaps between derived interiors (they include
    re-absorbed keep handles); ``bridged_active`` are the raw non-silent frames
    inside them. A clamped edge touches the window and received no handle.
    """

    source_region: FrameRange
    interior: FrameRange
    bridged: tuple[FrameRange, ...]
    head_keep: int
    tail_keep: int
    clamped_at_window_start: bool
    clamped_at_window_end: bool
    merged_regions: tuple[FrameRange, ...] = ()
    bridged_active: tuple[FrameRange, ...] = ()

    def __post_init__(self) -> None:
        for name in ("bridged", "merged_regions", "bridged_active"):
            object.__setattr__(self, name, tuple(getattr(self, name)))
        if not isinstance(self.source_region, FrameRange) or not isinstance(
            self.interior, FrameRange
        ):
            raise TypeError("FrameRange source and interior required")
        for name in ("bridged", "merged_regions", "bridged_active"):
            if any(not isinstance(r, FrameRange) for r in getattr(self, name)):
                raise TypeError(f"{name} must contain FrameRange values")
        _int("head_keep", self.head_keep, nonnegative=True)
        _int("tail_keep", self.tail_keep, nonnegative=True)
        if type(self.clamped_at_window_start) is not bool or (
            type(self.clamped_at_window_end) is not bool
        ):
            raise TypeError("Explicit bool clamp flags required")
        last = self.merged_regions[-1] if self.merged_regions else self.source_region
        if self.interior.start != self.source_region.start + self.head_keep:
            raise ValueError("Interior start must equal source start + head_keep")
        if self.interior.end != last.end - self.tail_keep:
            raise ValueError("Interior end must equal last region end - tail_keep")
        if self.clamped_at_window_start and self.head_keep:
            raise ValueError("A window-start clamp receives no head handle")
        if self.clamped_at_window_end and self.tail_keep:
            raise ValueError("A window-end clamp receives no tail handle")
        if len(self.bridged) != len(self.merged_regions) or len(self.bridged_active) != len(
            self.merged_regions
        ):
            raise ValueError("One bridged gap and active gap per merged region required")
        regions = (self.source_region, *self.merged_regions)
        for a, b, act, gap in zip(
            regions, regions[1:], self.bridged_active, self.bridged, strict=False
        ):
            if act != FrameRange(a.end, b.start) or not gap.contains(act):
                raise ValueError("Bridged active gap must lie between merged regions")
            if not self.interior.contains(gap):
                raise ValueError("Bridged gaps must lie inside the interior")


@dataclass(frozen=True)
class DroppedRegion:
    """A source region that yields no span of its own, with an explicit reason."""

    source_region: FrameRange
    reason: DroppedReason
    merged_into: FrameRange | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.source_region, FrameRange):
            raise TypeError("FrameRange source region required")
        if not isinstance(self.reason, DroppedReason) or self.reason is DroppedReason.UNKNOWN:
            raise ValueError("Explicit known drop reason required")
        merged = self.reason is DroppedReason.MERGED_INTO_PRECEDING_SPAN
        if merged != (self.merged_into is not None):
            raise ValueError("merged_into is required exactly for merged regions")
        if self.merged_into is not None and (
            not isinstance(self.merged_into, FrameRange)
            or self.merged_into.start >= self.source_region.start
        ):
            raise ValueError("merged_into must be a preceding FrameRange source region")


@dataclass(frozen=True)
class CutGeometryResult:
    """Explicitly derived geometry. One outcome per source region, in input order."""

    window: FrameRange
    source_regions: tuple[FrameRange, ...]
    policy: CutGeometryPolicy
    policy_ref: str
    outcomes: tuple[DerivedCutSpan | DroppedRegion, ...]
    derivation: str = DERIVATION
    authorization: str = AUTHORIZATION_STATEMENT

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_regions", tuple(self.source_regions))
        object.__setattr__(self, "outcomes", tuple(self.outcomes))
        if not isinstance(self.policy, CutGeometryPolicy):
            raise TypeError("Typed policy required")
        _validate_regions(self.source_regions, self.window)
        if self.policy_ref != self.policy.policy_ref:
            raise ValueError("policy_ref does not match policy")
        if self.derivation != DERIVATION or self.authorization != AUTHORIZATION_STATEMENT:
            raise ValueError("Unknown derivation or altered authorization statement")
        if len(self.outcomes) != len(self.source_regions):
            raise ValueError("Exactly one outcome per source region required")
        for o, r in zip(self.outcomes, self.source_regions, strict=True):
            if not isinstance(o, (DerivedCutSpan, DroppedRegion)) or o.source_region != r:
                raise ValueError("Outcomes must follow source regions in order")
        spans = self.spans
        for a, b in pairwise(spans):
            if b.interior.start <= a.interior.end:
                raise ValueError("Derived interiors must be ordered and separated")
        if any(not self.window.contains(s.interior) for s in spans):
            raise ValueError("Derived interiors must lie inside the window")

    @property
    def spans(self) -> tuple[DerivedCutSpan, ...]:
        return tuple(o for o in self.outcomes if isinstance(o, DerivedCutSpan))


def derive_cut_candidate_geometry(
    regions: Sequence[FrameRange], window: FrameRange, policy: CutGeometryPolicy
) -> CutGeometryResult:
    """Handles first (auto-editor margin), then bridging, then the min-cut drop.

    1. Each region keeps ``head_keep_frames`` at its start unless it touches the
       window start, and ``tail_keep_frames`` at its end unless it touches the
       window end. An empty remainder is DROPPED_EMPTY_AFTER_HANDLES.
    2. Surviving interiors are bridged in one ordered pass (gap <=
       ``max_bridge_frames``); later members become MERGED_INTO_PRECEDING_SPAN.
    3. A group whose joined interior is shorter than ``min_cut_frames`` drops all
       its members as DROPPED_TOO_SHORT.
    """
    if not isinstance(policy, CutGeometryPolicy):
        raise TypeError("Typed CutGeometryPolicy required")
    checked = _validate_regions(regions, window)
    outcomes: dict[int, DerivedCutSpan | DroppedRegion] = {}
    interiors: list[FrameRange] = []
    owner: dict[FrameRange, int] = {}
    heads: dict[int, int] = {}
    tails: dict[int, int] = {}
    for idx, r in enumerate(checked):
        head = 0 if r.start == window.start else policy.head_keep_frames
        tail = 0 if r.end == window.end else policy.tail_keep_frames
        start, end = r.start + head, r.end - tail
        if end <= start:
            outcomes[idx] = DroppedRegion(r, DroppedReason.DROPPED_EMPTY_AFTER_HANDLES)
            continue
        interior = FrameRange(start, end)
        interiors.append(interior)
        owner[interior] = idx
        heads[idx], tails[idx] = head, tail

    for group in _bridge(interiors, policy.max_bridge_frames):
        idxs = [owner[m] for m in group.members]
        first, rest = idxs[0], idxs[1:]
        if group.span.duration < policy.min_cut_frames:
            for i in idxs:
                outcomes[i] = DroppedRegion(checked[i], DroppedReason.DROPPED_TOO_SHORT)
            continue
        src = checked[first]
        merged = tuple(checked[i] for i in rest)
        chain = (src, *merged)
        outcomes[first] = DerivedCutSpan(
            source_region=src,
            interior=group.span,
            bridged=group.bridged,
            head_keep=heads[first],
            tail_keep=tails[idxs[-1]],
            clamped_at_window_start=src.start == window.start,
            clamped_at_window_end=chain[-1].end == window.end,
            merged_regions=merged,
            bridged_active=tuple(FrameRange(a.end, b.start) for a, b in pairwise(chain)),
        )
        for i in rest:
            outcomes[i] = DroppedRegion(
                checked[i], DroppedReason.MERGED_INTO_PRECEDING_SPAN, merged_into=src
            )

    return CutGeometryResult(
        window=window,
        source_regions=checked,
        policy=policy,
        policy_ref=policy.policy_ref,
        outcomes=tuple(outcomes[i] for i in range(len(checked))),
    )
