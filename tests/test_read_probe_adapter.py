from dataclasses import FrozenInstanceError, replace

import pytest
from read_probe_fakes import fixture_runtime

from davinci_ai_editor.resolve_probe.fixtures import RoleStatus, assess_fixture
from davinci_ai_editor.resolve_probe.model import Context, FixtureResult
from davinci_ai_editor.resolve_probe.values import freeze


def test_capture_is_complete_immutable_and_roots_reacquired():
    adapter, binding, fixture, calls, *_ = fixture_runtime()
    snapshot = adapter.capture(binding, fixture.context, fixture.timeline_id, 1)
    assert snapshot.complete and snapshot.consistent
    assert assess_fixture(snapshot, fixture).status == FixtureResult.MATCH
    assert len([c for c in calls if c[0] == "GetCurrentProject"]) == 2
    assert all(c[0].startswith("Get") for c in calls)
    with pytest.raises(FrozenInstanceError):
        snapshot.sequence = 3


@pytest.mark.parametrize(
    "context", [Context.F0, Context.F1, Context.F2, Context.F4_A, Context.F4_B]
)
def test_canonical_roles_and_exact_track_states(context):
    adapter, binding, fixture, *_ = fixture_runtime(context)
    result = assess_fixture(adapter.capture(binding, context, fixture.timeline_id, 1), fixture)
    assert result.status == FixtureResult.MATCH
    assert all(r.status == RoleStatus.UNIQUE for r in result.roles)


def test_repeated_media_keeps_same_source_different_placements():
    adapter, binding, fixture, *_ = fixture_runtime(Context.F1)
    s = adapter.capture(binding, fixture.context, fixture.timeline_id, 1)
    result = assess_fixture(s, fixture)
    assert len(result.roles) == 6
    one = s.field("item/F1_R1/video", "RV-031")
    two = s.field("item/F1_R2/video", "RV-031")
    assert one == two
    assert s.field("item/F1_R1/video", "RV-027") == s.field("item/F1_R2/video", "RV-027")
    assert s.field("item/F1_R1/video", "RV-024") != s.field("item/F1_R2/video", "RV-024")


def test_enumeration_reordering_only_normalizes_semantics():
    a, b, f, *_ = fixture_runtime()
    c, _, _, *_ = fixture_runtime(reverse=True)
    left = a.capture(b, f.context, f.timeline_id, 1)
    right = c.capture(b, f.context, f.timeline_id, 2)
    assert left.reads != right.reads
    assert left.semantic_fields == right.semantic_fields


def test_duplicate_placement_never_collapses():
    a, b, f, *_ = fixture_runtime(extra=True)
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert not s.complete
    assert "AMBIGUOUS_DUPLICATE_PLACEMENT_ID" in s.findings
    assert assess_fixture(s, f).status != FixtureResult.MATCH


def test_wrong_project_stops_body_without_name_fallback():
    a, b, f, calls, _, project, *_ = fixture_runtime()
    project.methods["GetUniqueId"] = "wrong"
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert "STALE_CONTEXT:RV-006" in s.findings
    assert not any(c[0] == "GetItemListInTrack" for c in calls)
    assert assess_fixture(s, f).status == FixtureResult.STALE


def test_profile_drift_is_not_rebased():
    a, b, f, _, root, *_ = fixture_runtime()
    root.methods["GetVersionString"] = "different"
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert not s.complete
    assert s.binding == b and "STALE_CONTEXT:RV-003" in s.findings


def test_float_geometry_is_unknown_and_raw_retained():
    a, b, f, _, _, _, _, tracks = fixture_runtime()
    tracks[("video", 1)][0].methods["GetStart"] = lambda x: 86500.0
    s = a.capture(b, f.context, f.timeline_id, 1)
    r = next(r for r in s.reads if r.key == ("item/F0_A/video", "RV-024"))
    assert r.raw == freeze(86500.0) and not r.valid and r.semantic_value is None


def test_fence_drift_retained():
    a, b, f, _, _, project, *_ = fixture_runtime()
    count = 0

    def identity():
        nonlocal count
        count += 1
        return "project-id" if count == 1 else "changed"

    project.methods["GetUniqueId"] = identity
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert not s.consistent and not s.complete
    assert s.end_fence


def test_missing_geometry_never_uses_filename_or_position_only():
    a, b, f, _, _, _, _, tracks = fixture_runtime()
    tracks[("video", 1)][0].methods["GetSourceStartFrame"] = None
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert assess_fixture(s, f).status != FixtureResult.MATCH
    assert s.field("item/F0_A/video", "RV-027") is None


def test_operator_interference_never_clean():
    a, b, f, *_ = fixture_runtime()
    s = a.capture(b, f.context, f.timeline_id, 1, operator_interference=True)
    assert assess_fixture(s, f).status == FixtureResult.ABORTED


def test_unknown_coordinate_proof_blocks_match():
    a, b, f, *_ = fixture_runtime()
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert (
        assess_fixture(s, replace(f, coordinate_evidence_ref=None)).status
        == FixtureResult.INCOMPLETE
    )


def test_native_timeline_end_mismatch_is_not_repaired():
    a, b, f, _, _, _, timeline, _ = fixture_runtime()
    timeline.methods["GetEndFrame"] = 99999
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert assess_fixture(s, f).status == FixtureResult.MISMATCH
    assert s.field("timeline", "RV-013") == freeze(99999)


def test_f0_missing_link_is_fixture_mismatch_not_unsupported():
    a, b, f, _, _, _, _, tracks = fixture_runtime()
    tracks[("video", 1)][0].methods["GetLinkedItems"] = []
    s = a.capture(b, f.context, f.timeline_id, 1)
    assert s.field("item/F0_A/video", "RV-034") == freeze([])
    assert assess_fixture(s, f).status == FixtureResult.MISMATCH


def test_f3_markers_subtitle_exact_values_and_explicit_host():
    from read_probe_fakes import Native

    a, b, f, calls, _, _, timeline, tracks = fixture_runtime(Context.F3)
    f = replace(f, item_marker_host_id="F3_HOST/video")
    timeline.methods["GetTrackCount"] = lambda kind: 1
    timeline.methods["GetMarkers"] = {
        120: {
            "duration": 12,
            "color": "Blue",
            "name": "TL_MARK_A",
            "note": "probe timeline marker",
            "customData": "probe:tl:a",
        }
    }
    tracks[("video", 1)][0].methods["GetMarkers"] = {
        40: {
            "duration": 8,
            "color": "Green",
            "name": "ITEM_MARK_A",
            "note": "probe item marker",
            "customData": "probe:item:a",
        }
    }
    tracks[("subtitle", 1)] = []
    for label, start, end in (("PROBE ALPHA 01", 160, 220), ("PROBE BETA 02", 260, 320)):
        tracks[("subtitle", 1)].append(
            Native(
                {
                    "GetUniqueId": label + "-id",
                    "GetName": label,
                    "GetStart": lambda sub=False, n=start: 86400 + n,
                    "GetEnd": lambda sub=False, n=end: 86400 + n,
                    "GetDuration": lambda sub=False, n=end - start: n,
                    "GetTrackTypeAndIndex": ["subtitle", 1],
                    "GetClipEnabled": True,
                    "GetMarkers": {},
                },
                calls,
            )
        )
    snapshot = a.capture(b, f.context, f.timeline_id, 1)
    assert snapshot.complete
    assert assess_fixture(snapshot, f).status == FixtureResult.MATCH
    assert (
        assess_fixture(snapshot, replace(f, item_marker_host_id=None)).status
        == FixtureResult.INCOMPLETE
    )
    tracks[("subtitle", 1)][0].methods["GetName"] = "not-canonical"
    changed = a.capture(b, f.context, f.timeline_id, 2)
    assert assess_fixture(changed, f).status == FixtureResult.MISMATCH


def test_zero_and_ambiguous_full_tuple_bindings_no_first_match():
    from read_probe_fakes import Native

    a, b, f, calls, _, _, _, tracks = fixture_runtime(Context.F1)
    first = tracks[("video", 1)][0]
    duplicate = Native(dict(first.methods), calls)
    duplicate.methods["GetUniqueId"] = "different-placement-same-full-geometry"
    tracks[("video", 1)].append(duplicate)
    snapshot = a.capture(b, f.context, f.timeline_id, 1)
    result = assess_fixture(snapshot, f)
    assert any(r.status == RoleStatus.AMBIGUOUS for r in result.roles)
    assert result.status == FixtureResult.MISMATCH
    tracks[("video", 1)] = []
    result = assess_fixture(a.capture(b, f.context, f.timeline_id, 2), f)
    assert any(r.status == RoleStatus.UNRESOLVED for r in result.roles)


def test_absent_installed_method_and_bridge_disagreement_are_distinct():
    from davinci_ai_editor.resolve_probe.adapter import InstalledSurface, ReadOnlyProbeAdapter
    from davinci_ai_editor.resolve_probe.surface import READS

    a, b, f, _, root, _, timeline, _ = fixture_runtime()
    inventory = InstalledSurface(
        "a" * 64, tuple((r.owner, r.method) for r in READS if r.key != "track_locked")
    )
    snap = ReadOnlyProbeAdapter(lambda: root, inventory).capture(b, f.context, f.timeline_id, 1)
    locked = next(r for r in snap.reads if r.case_id == "RV-020")
    assert locked.documented_absent and locked.raw is None
    del timeline.methods["GetIsTrackLocked"]
    snap = a.capture(b, f.context, f.timeline_id, 2)
    locked = next(r for r in snap.reads if r.case_id == "RV-020")
    assert not locked.documented_absent and locked.error and not locked.valid


def test_read_only_module_does_not_import_execution_paths():
    import ast
    from pathlib import Path

    directory = Path("src/davinci_ai_editor/resolve_probe")
    forbidden = {
        "fake_timeline",
        "safety",
        "safety_preflight",
        "transaction",
        "authority",
        "dependency",
        "pause_planning",
        "cut_geometry",
        "expected_diff",
    }
    for p in directory.glob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8-sig"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert node.module not in forbidden
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                assert node.func.id not in ("eval", "exec")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                assert not node.func.attr.startswith(
                    (
                        "SetCurrent",
                        "SetTrack",
                        "AddTrack",
                        "Delete",
                        "ImportMedia",
                        "AppendToTimeline",
                    )
                )
