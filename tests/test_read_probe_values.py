from dataclasses import FrozenInstanceError, replace

import pytest

from davinci_ai_editor.resolve_probe.model import ReadObservation, RuntimeResult
from davinci_ai_editor.resolve_probe.qualification import classify_observations
from davinci_ai_editor.resolve_probe.surface import READS, shape_valid
from davinci_ai_editor.resolve_probe.values import freeze, semantic


def test_distinct_absence_false_empty_and_exact_float():
    values = [freeze(v) for v in (None, False, "", [], {}, 0, 0.0)]
    assert len(set(values)) == 7
    assert freeze(0.8).scalar == "0x1.999999999999ap-1"


def test_raw_defensive_copy_and_semantic_map_order_only():
    raw = {"z": [1, 2], "a": None}
    before = freeze(raw)
    raw["z"].append(3)
    assert before != freeze(raw)
    assert before != freeze({"a": None, "z": [1, 2]})
    assert semantic(before) == semantic(freeze({"a": None, "z": [1, 2]}))
    assert semantic(freeze([1, 2])) != semantic(freeze([2, 1]))
    with pytest.raises(FrozenInstanceError):
        before.scalar = 0


@pytest.mark.parametrize("bad", [True, 1.0, None, "", "1"])
def test_exact_frame_shape_rejects_coercion(bad):
    assert not shape_valid("integer", bad)
    assert shape_valid("integer", 1)


def test_fixed_surface_contains_only_reads():
    assert all(r.method.startswith("Get") for r in READS)
    assert {"GetSettings", "GetCurrentDatabase", "GetSourceStartFrame", "GetMarkers"} <= {
        r.method for r in READS
    }
    assert not any(r.method.startswith(("Set", "Add", "Delete", "Import")) for r in READS)


def observation(value=1, valid=True, absent=False):
    return ReadObservation(
        "RV-012",
        "timeline",
        "GetStartFrame",
        freeze(()),
        freeze(value),
        valid,
        semantic(freeze(value)) if valid else None,
        None,
        absent,
    )


def test_one_call_cannot_establish_stable_support():
    assert classify_observations((observation(),), coverage_complete=False) == RuntimeResult.UNKNOWN


def test_drift_retained_no_majority_override():
    reads = tuple(observation(2 if i == 4 else 1) for i in range(20))
    assert classify_observations(reads, coverage_complete=True) == RuntimeResult.SUPPORTED_UNSTABLE


def test_unknown_is_not_unsupported_or_false():
    assert (
        classify_observations((observation(None, False),) * 20, coverage_complete=True)
        == RuntimeResult.UNKNOWN
    )
    assert (
        classify_observations((observation(None, False, True),) * 20, coverage_complete=True)
        == RuntimeResult.UNSUPPORTED
    )
    assert (
        classify_observations((observation(False),) * 20, coverage_complete=True)
        == RuntimeResult.SUPPORTED_STABLE
    )


def test_stable_wrong_value_is_still_readable():
    assert (
        classify_observations((observation(999),) * 20, coverage_complete=True)
        == RuntimeResult.SUPPORTED_STABLE
    )


def test_observation_constructor_preserves_error_and_no_default():
    o = replace(observation(None, False), error="BridgeError: unavailable")
    assert o.raw == freeze(None) and o.semantic_value is None
    assert o.error


def test_mutable_semantic_payload_is_rejected():
    with pytest.raises(TypeError):
        ReadObservation(
            "RV-012", "timeline", "GetStartFrame", freeze(()), freeze(1), True, {"mutable": []}
        )


def test_nested_snapshot_findings_must_be_strings():
    from read_probe_fakes import fixture_runtime

    a, b, f, *_ = fixture_runtime()
    s = a.capture(b, f.context, f.timeline_id, 1)
    with pytest.raises((TypeError, ValueError)):
        replace(s, findings=({"mutable": []},))
