"""Independent frame oracle: current-coordinate deletion loses original intent."""

import os

import pytest


def naive_remaining() -> list[int]:
    frames = list(range(120 * 30))
    del frames[30 * 30 : 32 * 30]
    del frames[90 * 30 : 92 * 30]
    return frames


def expected_remaining() -> list[int]:
    return [f for f in range(120 * 30) if not (900 <= f < 960 or 2700 <= f < 2760)]


def test_naive_wrong_original_content_is_reproducible() -> None:
    actual = naive_remaining()
    assert len(actual) == 116 * 30
    assert set(range(2700, 2760)).issubset(actual)
    assert set(range(2760, 2820)).isdisjoint(actual)
    assert actual != expected_remaining()


@pytest.mark.skipif(
    os.environ.get("REPRODUCE_NAIVE_FAILURE") != "1",
    reason="Opt-in intentional red test; regression above always runs",
)
def test_naive_fails_inv001() -> None:
    assert naive_remaining() == expected_remaining()
