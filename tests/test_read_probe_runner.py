from dataclasses import replace

import pytest
from read_probe_fakes import fixture_runtime

from davinci_ai_editor.resolve_probe.model import Context, FixtureResult, RuntimeResult
from davinci_ai_editor.resolve_probe.qualification import classify_series
from davinci_ai_editor.resolve_probe.runner import OperatorPreflight, QualificationRunner
from davinci_ai_editor.resolve_probe.writer import EvidenceWriter, verify_evidence


def operator():
    return OperatorPreflight(True, True, True, True, True, True, True)


def test_s1_exact_ten_pairs_twenty_complete_captures_no_retry(tmp_path):
    a, b, f, *_ = fixture_runtime()
    writer = EvidenceWriter(tmp_path / "run", b)
    runner = QualificationRunner(a, b, operator(), writer)
    series = runner.s1(f, b)
    assert len(series.pairs) == 10
    assert all(p.a.complete and p.b.complete for p in series.pairs)
    assert [p.number for p in series.pairs] == list(range(1, 11))
    assert len({s.sequence for p in series.pairs for s in (p.a, p.b)}) == 20
    assert classify_series(series, "RV-012") == RuntimeResult.SUPPORTED_STABLE
    with pytest.raises(ValueError):
        runner.s1(f, b)
    assert len(list((tmp_path / "run").rglob("pair-result.json"))) == 10


def test_preflight_mismatch_no_qualifying_pairs(tmp_path):
    a, b, f, _, _, _, timeline, _ = fixture_runtime()
    timeline.methods["GetIsTrackLocked"] = lambda *args: True
    runner = QualificationRunner(a, b, operator(), EvidenceWriter(tmp_path / "r", b))
    series = runner.s1(f, b)
    assert series.audit_result.status == FixtureResult.MISMATCH
    assert not series.pairs
    assert classify_series(series, "RV-012") == RuntimeResult.UNKNOWN


def test_binding_change_rejected_before_native_reads(tmp_path):
    a, b, f, calls, *_ = fixture_runtime()
    runner = QualificationRunner(a, b, operator(), EvidenceWriter(tmp_path / "r", b))
    with pytest.raises(ValueError):
        runner.s1(f, replace(b, project_generation=2))
    assert not calls


def test_operator_not_ready_blocks_native_calls(tmp_path):
    a, b, f, calls, *_ = fixture_runtime()
    runner = QualificationRunner(
        a, b, replace(operator(), no_concurrent_edit=False), EvidenceWriter(tmp_path / "r", b)
    )
    with pytest.raises(ValueError):
        runner.s1(f, b)
    assert not calls


def test_failed_pair_is_retained_and_never_renumbered(tmp_path):
    a, b, f, _, _, _, timeline, _ = fixture_runtime()
    n = 0

    def name():
        nonlocal n
        n += 1
        return "drift" if n == 15 else "diagnostic-name"

    timeline.methods["GetName"] = name
    runner = QualificationRunner(a, b, operator(), EvidenceWriter(tmp_path / "r", b))
    series = runner.s1(f, b)
    assert len(series.pairs) == 10
    assert any(not p.accepted for p in series.pairs)
    assert classify_series(series, "RV-011") == RuntimeResult.SUPPORTED_UNSTABLE
    assert (
        tmp_path / "r" / "fixtures" / f.context.value / "s1" / "pair-04" / "pair-result.json"
    ).exists()


def test_evidence_seal_report_and_checksum(tmp_path):
    a, b, f, *_ = fixture_runtime()
    writer = EvidenceWriter(tmp_path / "r", b)
    runner = QualificationRunner(a, b, operator(), writer)
    runner.s1(f, b)
    writer.finalize(runner.series, runner.roundtrips, ("OTHER_CONTEXTS_NOT_EXECUTED",))
    verify_evidence(tmp_path / "r")
    report = (tmp_path / "r" / "summary" / "TASK_020_RUNTIME_REPORT.md").read_text()
    assert all(f"RV-{i:03d}" in report for i in range(1, 45))
    assert "HOLD" in report and "PERSISTENT_VERIFIED" in report
    with pytest.raises(ValueError):
        writer.write("extra.json", {})
    (tmp_path / "r" / "run.json").write_text("{}")
    with pytest.raises(ValueError):
        verify_evidence(tmp_path / "r")


def test_raw_and_semantic_evidence_are_separate(tmp_path):
    a, b, f, *_ = fixture_runtime()
    w = EvidenceWriter(tmp_path / "r", b)
    runner = QualificationRunner(a, b, operator(), w)
    runner.s1(f, b)
    p = tmp_path / "r" / "fixtures" / f.context.value / "s1" / "pair-01"
    assert (p / "capture-A.raw.json").read_bytes() != (p / "capture-A.semantic.json").read_bytes()


def test_s2_requires_s1_and_explicit_operator_switches(tmp_path):
    a, b, f, *_ = fixture_runtime(Context.F4_A)
    runner = QualificationRunner(a, b, operator(), EvidenceWriter(tmp_path / "r", b))
    with pytest.raises(ValueError):
        runner.s2_capture(1, "A-before", f, b, "switch-proof")


def test_three_s2_roundtrips_with_external_switch_only(tmp_path):
    a, b, f, _, _, project, timeline, _ = fixture_runtime(Context.F4_A)
    _, _, g, _, _, _, other, _ = fixture_runtime(Context.F4_B)
    g = replace(g, timeline_id="timeline-B")
    other.methods["GetUniqueId"] = "timeline-B"
    w = EvidenceWriter(tmp_path / "r", b)
    runner = QualificationRunner(a, b, operator(), w)
    assert runner.s1(f, b).qualified
    project.methods["GetCurrentTimeline"] = other
    assert runner.s1(g, b).qualified
    for n in range(1, 4):
        project.methods["GetCurrentTimeline"] = timeline
        runner.s2_capture(n, "A-before", f, b, f"external-A-{n}")
        project.methods["GetCurrentTimeline"] = other
        runner.s2_capture(n, "B", g, b, f"external-B-{n}")
        project.methods["GetCurrentTimeline"] = timeline
        runner.s2_capture(n, "A-after", f, b, f"external-return-{n}")
    assert len(runner.roundtrips) == 3 and all(t.accepted for t in runner.roundtrips)
    with pytest.raises(ValueError):
        runner.s2_capture(4, "A-before", f, b, "extra")
    assert len(list((tmp_path / "r").rglob("roundtrip-result.json"))) == 3


def test_operator_incident_retained_blocks_future_capture(tmp_path):
    a, b, f, calls, *_ = fixture_runtime()
    w = EvidenceWriter(tmp_path / "r", b)
    runner = QualificationRunner(a, b, operator(), w)
    runner.record_operator_interference("operator-scrubbed")
    with pytest.raises(ValueError):
        runner.s1(f, b)
    assert not calls
    assert list((tmp_path / "r" / "findings").glob("operator-*.json"))


def test_evidence_duplicate_paths_never_overwrite(tmp_path):
    _, b, *_ = fixture_runtime()
    w = EvidenceWriter(tmp_path / "r", b)
    w.write("findings/one.json", {"raw": False})
    with pytest.raises(FileExistsError):
        w.write("findings/one.json", {"raw": None})
    with pytest.raises(ValueError):
        w.write("../outside.json", {})


def test_s2_cannot_replace_s1_identity_baseline(tmp_path):
    a, b, f, _, _, project, timeline, tracks = fixture_runtime(Context.F4_A)
    _, _, g, _, _, _, other, _ = fixture_runtime(Context.F4_B)
    g = replace(g, timeline_id="B")
    other.methods["GetUniqueId"] = "B"
    runner = QualificationRunner(a, b, operator(), EvidenceWriter(tmp_path / "r", b))
    runner.s1(f, b)
    project.methods["GetCurrentTimeline"] = other
    runner.s1(g, b)
    project.methods["GetCurrentTimeline"] = timeline
    tracks[("video", 1)][0].methods["GetUniqueId"] = "changed-after-S1"
    runner.s2_capture(1, "A-before", f, b, "external-return")
    with pytest.raises(ValueError):
        runner.s2_capture(1, "B", g, b, "external-switch")
    assert list((tmp_path / "r").rglob("*.drift.json"))


def test_missing_persisted_capture_cannot_be_sealed_as_stable(tmp_path):
    a, b, f, *_ = fixture_runtime()
    w = EvidenceWriter(tmp_path / "r", b)
    runner = QualificationRunner(a, b, operator(), w)
    runner.s1(f, b)
    next((tmp_path / "r").rglob("capture-A.raw.json")).unlink()
    with pytest.raises(ValueError, match="Capture evidence"):
        w.finalize(runner.series, runner.roundtrips)


def test_discovery_unavailable_reports_all_contexts_without_qualification(tmp_path, monkeypatch):
    import json

    from davinci_ai_editor.resolve_probe import __main__ as cli

    installed = tmp_path / "installed"
    installed.mkdir()
    (installed / "DaVinciResolveScript.pyi").write_text(
        "class Resolve:\n    def GetProductName(self): ...\n    def GetVersion(self): ...\n    def GetVersionString(self): ...\n"
    )
    (installed / "README.md").write_text("installed test documentation")
    monkeypatch.setattr(cli, "INSTALLED_SCRIPTING", installed)
    monkeypatch.setattr(cli, "connect_installed", lambda: None)
    root = tmp_path / "diagnostic"
    assert cli.discovery(root) == 2
    verify_evidence(root)
    report = (root / "summary/TASK_020_RUNTIME_REPORT.md").read_text()
    assert all(f"RV-{i:03d} | UNKNOWN" in report for i in range(1, 45))
    assert report.count("| NOT_EXECUTED |") == 63
    assert json.loads((root / "run.json").read_text())["counts_toward_s1"] is False
    assert json.loads((root / "runtime_profile.json").read_text())["qualifying_profile"] is None
