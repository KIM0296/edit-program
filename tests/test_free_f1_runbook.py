import json
from pathlib import Path

RUNBOOK = Path("tasks/TASK_023_F1_RUNTIME_QUALIFICATION_RUNBOOK.md")


def schema():
    text = RUNBOOK.read_text(encoding="utf-8-sig")
    return json.loads(text.split("```json\n", 1)[1].split("\n```", 1)[0])


def test_runbook_has_no_preset_result_and_requires_independent_oracle():
    c = schema()
    assert c["record_template"]["gate_result"] is None
    assert c["record_template"]["raw_value"] is None
    assert c["independent_oracle_required"] is True
    assert c["getter_under_test_is_oracle"] is False
    assert c["canonical_asset_proves_materialization"] is False


def test_bounded_cases_and_no_runtime_authorization():
    c = schema()
    assert c["operational_coordinate_cases"] == ["C01", "C02", "C03"]
    assert c["planned_coordinate_cases"] == ["C04", "C05", "C06", "C07"]
    assert c["operational_identity_levels"] == ["I0", "I1"]
    assert c["future_not_authorized_identity_levels"] == ["I2", "I3", "I4"]
    assert c["execute_in_this_task"] is False
    assert c["future_case_requires_chat_review"] is True


def test_no_semantic_repair_or_identity_inference():
    c = schema()
    assert c["coordinate_statuses"] == [
        "NOT_ESTABLISHED", "CORRESPONDENCE_CANDIDATE", "VERIFIED_EXACT", "CONFLICT", "UNKNOWN"
    ]
    assert c["record_template"]["endpoint_status"] == "NOT_ESTABLISHED"
    assert c["frame_range_construction"] is False
    assert set(c["forbidden_repairs"]) == {
        "round", "floor", "ceil", "clamp", "tolerance", "+1", "-1", "silent_rebase"
    }
    assert c["pointer_handle_identity"] is False
    assert c["cross_level_inference"] is False
    assert c["retry_until_green"] is False


def test_append_only_schema_retains_raw_and_provenance():
    c = schema()
    assert c["append_only"] is True
    assert set(c["record_template"]) >= {
        "run_id", "record_id", "sequence_no", "case_id", "identity_level", "operator",
        "wall_clock_timestamp", "resolve_version_string", "product_string", "project_id",
        "project_name", "timeline_id", "timeline_name", "source_asset_id", "source_sha256",
        "source_native_id", "placement_id", "track_type", "track_index", "native_method", "method_arguments",
        "raw_lua_type", "raw_value", "read_outcome", "error", "provenance",
        "fixture_oracle_ref", "coordinate_basis_status", "endpoint_status", "rate_evidence",
        "snapshot_currentness_evidence", "semantic_qualification_status", "transcript_ref",
        "exact_command", "probe_commit", "probe_sha256", "gate_result",
    }
    assert c["provenance_classes"] == {"P2": "reviewed_probe", "P3": "operator_manual_console"}
    assert c["require_complete_probe_capture"] == ["BOOT", "OBS", "END"]
    assert c["manual_transcript_editing"] is False


def test_case_sections_and_package_contract():
    c = schema()
    text = RUNBOOK.read_text(encoding="utf-8-sig")
    required = {
        "Purpose", "Prerequisites", "Independent oracle", "Exact fixture preparation instructions",
        "Allowed operator actions", "Forbidden operator actions", "Exact native reads",
        "Raw output retention requirements", "Expected evidence schema", "Allowed conclusions",
        "Forbidden conclusions", "PASS / CONFLICT / UNKNOWN / INCOMPLETE conditions",
        "Cleanup / stop point",
    }
    for case in ("C01", "C02", "C03", "I0", "I1"):
        section = text.split(f"## {case} ", 1)[1].split("\n## ", 1)[0]
        assert all(f"**{heading}:**" in section for heading in required)
    index = json.loads(Path(
        "canonical_assets/first-package-candidate-v1/package-index.candidate.json"
    ).read_text(encoding="utf-8"))
    assert c["package_digest"] == index["package_digest"]
    assert "51109edb40573bcf98c1373dae2e049c81da99db44186841779075624d650137" in text
    assert "GetEnd(A) == GetStart(B) is not an adjacency oracle" in text


def test_no_scope_expansion():
    c = schema()
    assert c["not_authorized"] == [
        "F2", "F3", "IPC", "listener", "persistence", "mutation_automation",
        "UI_automation", "parity_runner", "distribution", "installer", "macOS_packaging"
    ]
    assert c["shared_core_changes"] == []
    assert c["lua_probe_changes"] == []


def test_c03_oracle_has_three_independent_ui_positions():
    c = schema()["c03_protocol"]
    assert c["source_roles"] == {
        "A": "canonical:ASSET_VIDEO_ONLY:v1", "B": "canonical:ASSET_ALPHA:v1"
    }
    assert c["ui_position_sequence"] == ["A0719", "EMPTY_GAP", "B0000"]
    assert c["individual_ui_positions_required"] == 3
    assert c["native_getters_are_gap_oracle"] is False
    assert c["snap_or_collection_order_is_oracle"] is False
    assert c["comparison_requires_independent_gap_evidence"] is True
    text = RUNBOOK.read_text(encoding="utf-8-sig")
    section = text.split("## C03 ", 1)[1].split("\n## ", 1)[0]
    for position in ("U0", "U1", "U2"):
        assert f"| {position} |" in section


def test_c03_competing_hypotheses_are_not_endpoint_repairs():
    c = schema()["c03_protocol"]
    assert c["hypotheses"] == ["H1", "H2", "H3"]
    assert c["selected_hypothesis"] is None
    assert c["gate_result"] is None
    assert c["pass_scope"] == "BOUNDED_CASE_ONLY"
    assert c["endpoint_status"] == "NOT_ESTABLISHED"
    assert c["frame_range_authorized"] is False
    assert c["native_methods_added"] == []
    assert c["compare_to_c02_without_rebase"] is True
    assert c["codex_executes_case"] is False
