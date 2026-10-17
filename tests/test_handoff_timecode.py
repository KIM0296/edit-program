import math
from fractions import Fraction

import pytest

from davinci_ai_editor.temporal_mapping import FrameRate
from davinci_ai_editor.timecode import (
    SMPTE_RATES,
    RolloverPolicy,
    TimecodeMode,
    default_mode,
    frame_span_to_ms,
    frames_per_24_hours,
    frames_to_ms_ceil,
    frames_to_ms_floor,
    frames_to_seconds,
    frames_to_timecode,
    is_ntsc,
    nominal_fps,
    parse_timecode,
    rate_as_float,
    snap_rate,
    timecode_to_frames,
)

DF2997 = FrameRate(30000, 1001)
DF5994 = FrameRate(60000, 1001)
NDF23976 = FrameRate(24000, 1001)
DF = TimecodeMode.DROP_FRAME
NDF = TimecodeMode.NON_DROP_FRAME


@pytest.mark.parametrize(
    ("frames", "label"),
    [
        (0, "00:00:00;00"),
        (29, "00:00:00;29"),
        (1799, "00:00:59;29"),
        (1800, "00:01:00;02"),
        (3597, "00:01:59;29"),
        (3598, "00:02:00;02"),
        (17981, "00:09:59;29"),
        (17982, "00:10:00;00"),
        (17983, "00:10:00;01"),
        (19781, "00:10:59;29"),
        (19782, "00:11:00;02"),
        (107892, "01:00:00;00"),
    ],
)
def test_2997_drop_frame_vectors(frames: int, label: str) -> None:
    assert frames_to_timecode(frames, DF2997) == label
    assert timecode_to_frames(label, DF2997) == frames


@pytest.mark.parametrize(
    ("frames", "label"),
    [
        (3599, "00:00:59;59"),
        (3600, "00:01:00;04"),
        (35963, "00:09:59;59"),
        (35964, "00:10:00;00"),
        (215784, "01:00:00;00"),
    ],
)
def test_5994_drop_frame_vectors(frames: int, label: str) -> None:
    assert frames_to_timecode(frames, DF5994) == label
    assert timecode_to_frames(label, DF5994) == frames


@pytest.mark.parametrize(
    ("frames", "label"),
    [(0, "00:00:00:00"), (23, "00:00:00:23"), (1440, "00:01:00:00"), (86400, "01:00:00:00")],
)
def test_23976_is_non_drop_frame(frames: int, label: str) -> None:
    assert default_mode(NDF23976) is NDF
    assert nominal_fps(NDF23976) == 24
    assert is_ntsc(NDF23976)
    assert frames_to_timecode(frames, NDF23976) == label
    assert timecode_to_frames(label, NDF23976) == frames


def test_2997_can_be_labelled_non_drop_explicitly() -> None:
    assert frames_to_timecode(1800, DF2997, NDF) == "00:01:00:00"
    assert parse_timecode("00:01:00:00", DF2997) == (1800, NDF)
    assert parse_timecode("00:01:00;02", DF2997) == (1800, DF)


def test_drop_frame_only_for_2997_and_5994() -> None:
    for rate in SMPTE_RATES:
        expected = DF if rate in (DF2997, DF5994) else NDF
        assert default_mode(rate) is expected
        if expected is NDF:
            with pytest.raises(ValueError):
                frames_to_timecode(0, rate, DF)
            with pytest.raises(ValueError):
                timecode_to_frames("00:00:00;00", rate)


def test_nonexistent_drop_frame_labels_reject() -> None:
    for label in ("00:01:00;00", "00:01:00;01", "00:59:00;01"):
        with pytest.raises(ValueError):
            timecode_to_frames(label, DF2997)
    for label in ("00:01:00;02", "00:01:00;03"):
        with pytest.raises(ValueError):
            timecode_to_frames(label, DF5994)
    assert timecode_to_frames("00:10:00;00", DF2997) == 17982


@pytest.mark.parametrize(
    "label", ["1:00:00:00", "00:60:00:00", "00:00:60:00", "00:00:00:30", "24:00:00:00", "x"]
)
def test_malformed_or_out_of_range_labels_reject(label: str) -> None:
    with pytest.raises(ValueError):
        timecode_to_frames(label, FrameRate(30, 1))


def test_rollover_policy_is_explicit() -> None:
    day = frames_per_24_hours(DF2997)
    assert day == 2589408
    assert frames_per_24_hours(DF2997, NDF) == 30 * 86400
    assert frames_per_24_hours(DF5994) == 2 * 2589408
    assert frames_to_timecode(day - 1, DF2997) == "23:59:59;29"
    with pytest.raises(ValueError):
        frames_to_timecode(day, DF2997)
    assert frames_to_timecode(day, DF2997, rollover=RolloverPolicy.WRAP_24H) == "00:00:00;00"
    assert frames_to_timecode(day + 1800, DF2997, rollover=RolloverPolicy.WRAP_24H) == "00:01:00;02"
    with pytest.raises(ValueError):
        frames_to_timecode(25 * 86400, FrameRate(25, 1))


def test_invalid_inputs_reject() -> None:
    with pytest.raises(ValueError):
        frames_to_timecode(-1, DF2997)
    with pytest.raises(TypeError):
        frames_to_timecode(True, DF2997)
    with pytest.raises(ValueError):
        frames_to_timecode(0, FrameRate(12, 1))
    with pytest.raises(ValueError):
        frames_to_timecode(0, DF2997, TimecodeMode.UNKNOWN)


@pytest.mark.parametrize("rate", SMPTE_RATES)
def test_round_trip_exhaustive_over_range(rate: FrameRate) -> None:
    modes = [NDF, DF] if rate in (DF2997, DF5994) else [NDF]
    for mode in modes:
        day = frames_per_24_hours(rate, mode)
        frames = list(range(40000)) + list(range(day - 40000, day))
        labels = [frames_to_timecode(f, rate, mode) for f in frames]
        assert len(set(labels)) == len(labels)
        for frame, label in zip(frames, labels, strict=True):
            assert parse_timecode(label, rate) == (frame, mode)


def test_snap_rate_never_guesses() -> None:
    assert snap_rate(23.976) == NDF23976
    assert snap_rate(24000 / 1001) == NDF23976
    assert snap_rate(29.97) == DF2997
    assert snap_rate(59.94) == DF5994
    assert snap_rate(47.952) == FrameRate(48000, 1001)
    assert snap_rate(24) == FrameRate(24, 1)
    assert snap_rate(25.0) == FrameRate(25, 1)
    for value in (23.98, 29.0, 12.0, 0.0, -24.0, math.nan, math.inf, 120.0):
        assert snap_rate(value) is None
    assert snap_rate(True) is None
    assert snap_rate("24") is None  # type: ignore[arg-type]
    for rate in SMPTE_RATES:
        assert snap_rate(rate_as_float(rate)) == rate


def test_frames_to_ms_uses_exact_rationals_floor_start_ceil_end() -> None:
    assert frames_to_seconds(1, DF2997) == Fraction(1001, 30000)
    assert frames_to_ms_floor(1, DF2997) == 33
    assert frames_to_ms_ceil(1, DF2997) == 34
    assert frame_span_to_ms(1, 2, FrameRate(24, 1)) == (41, 84)
    assert frame_span_to_ms(0, 24, FrameRate(24, 1)) == (0, 1000)
    assert frame_span_to_ms(30, 60, FrameRate(30, 1)) == (1000, 2000)
    # 1 hour of 29.97 frames is 3603.6 s exactly: no float drift
    assert frame_span_to_ms(0, 108000, DF2997) == (0, 3603600)
    with pytest.raises(ValueError):
        frame_span_to_ms(5, 5, DF2997)
