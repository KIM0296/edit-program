"""HANDOFF-001 exact SMPTE timecode and frame/millisecond conversion.

Pure arithmetic over integer frames and exact rationals. No media access, no
Resolve access, no float accumulation. A frame rate outside the SMPTE
whitelist is never guessed: :func:`snap_rate` returns ``None`` (UNKNOWN).

Timecode labels are a presentation policy over integer frame counts; they are
not evidence of any native timeline state.
"""

import math
import re
from enum import Enum
from fractions import Fraction

from .temporal_mapping import FrameRate

SMPTE_RATES: tuple[FrameRate, ...] = (
    FrameRate(24000, 1001),
    FrameRate(24, 1),
    FrameRate(25, 1),
    FrameRate(30000, 1001),
    FrameRate(30, 1),
    FrameRate(48000, 1001),
    FrameRate(48, 1),
    FrameRate(50, 1),
    FrameRate(60000, 1001),
    FrameRate(60, 1),
)

# Drop-frame is defined only for these two rates (frames dropped per minute,
# except every tenth minute).
_DROP_FRAMES_PER_MINUTE: dict[FrameRate, int] = {
    FrameRate(30000, 1001): 2,
    FrameRate(60000, 1001): 4,
}

# Absolute tolerance for snapping a float rate to the whitelist. Whitelisted
# rates are at least ~0.024 apart, so a match is never ambiguous.
SNAP_TOLERANCE = 1e-3

_HOURS_PER_DAY = 24


class TimecodeMode(str, Enum):
    UNKNOWN = "UNKNOWN"
    NON_DROP_FRAME = "NON_DROP_FRAME"
    DROP_FRAME = "DROP_FRAME"


class RolloverPolicy(str, Enum):
    """Explicit handling of frame counts at or beyond 24 hours."""

    REJECT = "REJECT"
    WRAP_24H = "WRAP_24H"


def _require_rate(rate: FrameRate) -> None:
    if not isinstance(rate, FrameRate):
        raise TypeError("A FrameRate is required")
    if rate not in SMPTE_RATES:
        raise ValueError("Frame rate is not a whitelisted SMPTE rate")


def _require_frames(frames: int) -> None:
    if type(frames) is not int:
        raise TypeError("Frame count must be an int")
    if frames < 0:
        raise ValueError("Frame count must be nonnegative")


def is_smpte_rate(rate: FrameRate) -> bool:
    return isinstance(rate, FrameRate) and rate in SMPTE_RATES


def is_ntsc(rate: FrameRate) -> bool:
    _require_rate(rate)
    return rate.denominator == 1001


def nominal_fps(rate: FrameRate) -> int:
    """Integer frames-per-second label base (ceil): 30000/1001 -> 30."""
    _require_rate(rate)
    return -(-rate.numerator // rate.denominator)


def supports_drop_frame(rate: FrameRate) -> bool:
    _require_rate(rate)
    return rate in _DROP_FRAMES_PER_MINUTE


def default_mode(rate: FrameRate) -> TimecodeMode:
    """DF for 29.97/59.94, NDF otherwise. A policy default, not an observation."""
    return TimecodeMode.DROP_FRAME if supports_drop_frame(rate) else TimecodeMode.NON_DROP_FRAME


def _resolve_mode(rate: FrameRate, mode: TimecodeMode | None) -> TimecodeMode:
    resolved = default_mode(rate) if mode is None else mode
    if not isinstance(resolved, TimecodeMode) or resolved is TimecodeMode.UNKNOWN:
        raise ValueError("Timecode mode must be DROP_FRAME or NON_DROP_FRAME")
    if resolved is TimecodeMode.DROP_FRAME and not supports_drop_frame(rate):
        raise ValueError("Drop-frame is only defined for 30000/1001 and 60000/1001")
    return resolved


def frames_per_24_hours(rate: FrameRate, mode: TimecodeMode | None = None) -> int:
    resolved = _resolve_mode(rate, mode)
    nominal = nominal_fps(rate)
    if resolved is TimecodeMode.DROP_FRAME:
        drop = _DROP_FRAMES_PER_MINUTE[rate]
        per_ten_minutes = nominal * 600 - drop * 9
        return per_ten_minutes * 6 * _HOURS_PER_DAY
    return nominal * 3600 * _HOURS_PER_DAY


def frames_to_timecode(
    frames: int,
    rate: FrameRate,
    mode: TimecodeMode | None = None,
    rollover: RolloverPolicy = RolloverPolicy.REJECT,
) -> str:
    """Render ``HH:MM:SS:FF`` (NDF) or ``HH:MM:SS;FF`` (DF).

    ``rollover=REJECT`` raises for counts >= 24h; ``WRAP_24H`` wraps modulo 24h.
    """
    _require_frames(frames)
    resolved = _resolve_mode(rate, mode)
    if not isinstance(rollover, RolloverPolicy):
        raise TypeError("Unknown rollover policy")
    day = frames_per_24_hours(rate, resolved)
    if frames >= day:
        if rollover is RolloverPolicy.REJECT:
            raise ValueError("Frame count reaches or exceeds 24 hours; rollover rejected")
        frames %= day
    nominal = nominal_fps(rate)
    value = frames
    separator = ":"
    if resolved is TimecodeMode.DROP_FRAME:
        # Adapted from OpenTimelineIO src/opentime/rationalTime.cpp
        # (RationalTime::to_timecode, drop-frame branch), Apache-2.0,
        # Copyright Contributors to the OpenTimelineIO project.
        # See licenses/OpenTimelineIO-LICENSE.txt and OpenTimelineIO-NOTICE.txt.
        # Ported to exact integer arithmetic (no fmod/round on doubles).
        drop = _DROP_FRAMES_PER_MINUTE[rate]
        per_ten_minutes = nominal * 600 - drop * 9
        per_minute = nominal * 60 - drop
        ten_minute_chunks, remainder = divmod(value, per_ten_minutes)
        if remainder > drop:
            value += drop * 9 * ten_minute_chunks + drop * ((remainder - drop) // per_minute)
        else:
            value += drop * 9 * ten_minute_chunks
        separator = ";"
    frame_field = value % nominal
    seconds_total = value // nominal
    hours, rest = divmod(seconds_total, 3600)
    minutes, seconds = divmod(rest, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{separator}{frame_field:02d}"


_TIMECODE_RE = re.compile(r"^(\d{2}):(\d{2}):(\d{2})([:;])(\d{2})$")


def parse_timecode(text: str, rate: FrameRate) -> tuple[int, TimecodeMode]:
    """Strictly parse a timecode label into a frame count and its mode.

    The separator decides the mode: ``;`` = DF (only at 29.97/59.94), ``:`` = NDF.
    Labels skipped by drop-frame counting are rejected, never coerced.
    """
    _require_rate(rate)
    if not isinstance(text, str):
        raise TypeError("Timecode must be a string")
    match = _TIMECODE_RE.match(text)
    if match is None:
        raise ValueError("Malformed timecode")
    hours, minutes, seconds = (int(match.group(i)) for i in (1, 2, 3))
    separator = match.group(4)
    frame_field = int(match.group(5))
    nominal = nominal_fps(rate)
    if hours >= _HOURS_PER_DAY or minutes >= 60 or seconds >= 60 or frame_field >= nominal:
        raise ValueError("Timecode field out of range")
    mode = TimecodeMode.DROP_FRAME if separator == ";" else TimecodeMode.NON_DROP_FRAME
    _resolve_mode(rate, mode)
    total_minutes = hours * 60 + minutes
    total = (total_minutes * 60 + seconds) * nominal + frame_field
    if mode is TimecodeMode.DROP_FRAME:
        drop = _DROP_FRAMES_PER_MINUTE[rate]
        if seconds == 0 and minutes % 10 != 0 and frame_field < drop:
            raise ValueError("Timecode label does not exist in drop-frame counting")
        total -= drop * (total_minutes - total_minutes // 10)
    return total, mode


def timecode_to_frames(text: str, rate: FrameRate) -> int:
    return parse_timecode(text, rate)[0]


def snap_rate(value: float) -> FrameRate | None:
    """Snap a float rate to the whitelist; ``None`` means UNKNOWN (never guessed)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value <= 0:
        return None
    for rate in SMPTE_RATES:
        if abs(value - rate.numerator / rate.denominator) <= SNAP_TOLERANCE:
            return rate
    return None


def rate_as_float(rate: FrameRate) -> float:
    """Single correctly-rounded float of the exact rational (for file formats only)."""
    _require_rate(rate)
    return rate.numerator / rate.denominator


def frames_to_seconds(frames: int, rate: FrameRate) -> Fraction:
    _require_frames(frames)
    _require_rate(rate)
    return Fraction(frames * rate.denominator, rate.numerator)


def frames_to_ms_floor(frames: int, rate: FrameRate) -> int:
    return math.floor(frames_to_seconds(frames, rate) * 1000)


def frames_to_ms_ceil(frames: int, rate: FrameRate) -> int:
    return math.ceil(frames_to_seconds(frames, rate) * 1000)


def frame_span_to_ms(start: int, end: int, rate: FrameRate) -> tuple[int, int]:
    """Covering millisecond span: floor(start), ceil(end). Never shrinks a range."""
    if type(start) is not int or type(end) is not int or start < 0 or end <= start:
        raise ValueError("Expected nonempty, nonnegative [start, end)")
    return frames_to_ms_floor(start, rate), frames_to_ms_ceil(end, rate)
