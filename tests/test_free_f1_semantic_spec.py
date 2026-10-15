import json
from pathlib import Path

SPEC = Path("tasks/TASK_023_F1_SEMANTIC_QUALIFICATION_PHASE_1.md")


def contract():
    text = SPEC.read_text(encoding="utf-8")
    return json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])


def test_coordinate_vocabulary_and_no_endpoint_default():
    c = contract()
    assert c["coordinate_statuses"] == [
        "NOT_ESTABLISHED", "CORRESPONDENCE_CANDIDATE", "VERIFIED_EXACT", "CONFLICT", "UNKNOWN"
    ]
    assert c["native_endpoint_default"] == "NOT_ESTABLISHED"
    assert c["native_basis_default"] == "UNKNOWN"
    assert c["current_coordinate_status"] == "NOT_ESTABLISHED"


def test_range_gate_requires_exact_proof_without_repairs():
    c = contract()
    assert c["frame_range_gate"]["necessary_status"] == "VERIFIED_EXACT"
    assert set(c["frame_range_gate"]["also_required"]) == {
        "current_snapshot_binding", "placement_correspondence", "exact_integer_boundaries",
        "qualified_basis_and_endpoints", "exact_rate_evidence",
    }
    assert c["frame_range_construction_in_this_task"] is False
    assert set(c["forbidden_repairs"]) == {
        "round", "floor", "ceil", "clamp", "tolerance", "shift", "silent_rebase"
    }


def test_controlled_fixture_coverage_and_raw_semantic_separation():
    c = contract()
    assert c["fixture_cases"] == ["C01", "C02", "C03", "C04", "C05", "C06", "C07"]
    assert c["fixture_creation_authorized"] is False
    assert set(c["observation_fields"]) >= {
        "raw_value", "raw_type", "coordinate_basis", "endpoint_convention",
        "rate_evidence", "coordinate_domain", "correspondence_status", "provenance",
        "method_arguments", "fixture_oracle_ref", "snapshot_binding",
    }


def test_lifetime_levels_do_not_promote_identity():
    c = contract()
    assert c["identity_levels"] == ["I0", "I1", "I2", "I3", "I4"]
    assert c["identity_outcomes"] == [
        "STABLE_OBSERVED_AT_LEVEL", "CHANGED", "NOT_OBSERVED", "AMBIGUOUS", "ERROR"
    ]
    assert c["cross_level_inference"] is False
    assert c["automatic_identity_scope_promotion"] is False
    assert c["handle_equality_is_identity_proof"] is False
    assert c["current_levels"] == {
        "I0": "PARTIAL_VIDEO_FIELDS_ONLY", "I1": "NOT_OBSERVED", "I2": "NOT_OBSERVED",
        "I3": "NOT_OBSERVED", "I4": "NOT_OBSERVED",
    }


def test_freshness_remains_fail_closed_and_core_shared():
    c = contract()
    assert c["freshness_rules"] == {
        "snapshot_mismatch": "STALE", "missing_currentness": "BLOCKED_UNKNOWN",
        "equal_reread_implies_current": False, "state_token_synthesis": False,
        "human_edit_priority": True,
    }
    assert c["shared_contract_changes"] == []
    assert c["edition_specific_semantics"] is False
    assert c["runtime_execution_authorized"] is False
    assert c["native_probe_changes"] == []


def test_audit_sources_and_fixture_cases_are_documented():
    text = SPEC.read_text(encoding="utf-8")
    for source in (
        "ADR-008", "ADR-012", "ADR-015", "ADR-016", "ADR-021", "ADR-022",
        "docs/NATIVE_TIME_SNAPSHOT_MAPPING.md", "docs/EDITING_IR.md",
        "docs/CANDIDATE_AUTHORITY.md", "docs/PARALLEL_EDITING.md",
        "docs/READ_ONLY_RESOLVE_SNAPSHOT_CONTRACT.md", "OPEN-001", "OPEN-006",
    ):
        assert source in text
    for case in contract()["fixture_cases"]:
        assert f"| {case} |" in text
    assert "No inclusive/exclusive endpoint convention is assumed" in text
    assert "NOT_OBSERVED is not STABLE_OBSERVED_AT_LEVEL" in text
