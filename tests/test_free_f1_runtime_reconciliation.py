from pathlib import Path

REPORT = Path("docs/reports/TASK_023_FREE_BRIDGE_FEASIBILITY.md")


def evidence():
    return REPORT.read_text(encoding="utf-8").split(
        "# F1 RUNTIME EVIDENCE RECONCILIATION REPORT - C01 / C02 / I0", 1
    )[1]


def test_approved_case_gates_do_not_promote_semantics():
    text = evidence()
    for value in (
        "C01 gate: PASS (bounded case only)",
        "I0 gate: PASS (same-context immediate reread only)",
        "C02 attempt 1: INCOMPLETE", "C02 attempt 2 gate: PASS (bounded case only)",
        "Coordinate status: CORRESPONDENCE_CANDIDATE",
        "Endpoint convention: NOT_ESTABLISHED", "FrameRange construction: NOT AUTHORIZED",
    ):
        assert value in text


def test_manual_summaries_are_not_fabricated_transcripts():
    text = evidence()
    assert "P2 reviewed probe: NOT EXECUTED" in text
    assert "complete raw transcript: NOT SUPPLIED" in text
    assert "FREE_F1|OBS|" not in text
    assert "capture timestamps/run IDs/exact commands: NOT SUPPLIED" in text
    for comment in (6062948335, 6063086255, 6063288838, 6064002073):
        assert f"issuecomment-{comment}" in text


def test_attempts_and_identity_scope_remain_separate():
    text = evidence()
    assert "unexpected A1 audio placement" in text
    assert "No deletion, repair, trimming or retry-until-green" in text
    assert "additional V2 track" in text
    assert "I1/I2/I3/I4: NOT OBSERVED" in text
    assert "No SESSION_LOCAL_VERIFIED or PERSISTENT_VERIFIED promotion" in text
    for field in ("project ID", "timeline ID", "placement ID", "source ID", "start", "end", "duration"):
        row = next(line for line in text.splitlines() if line.startswith(f"| {field} |"))
        assert "STABLE_OBSERVED_AT_LEVEL" in row


def test_placement_and_source_bindings_are_preserved():
    text = evidence()
    for identifier in (
        "8023de71-f9c7-41fc-8fbf-fa1baebf613a", "c3ebf612-d464-4734-9fd1-0dfe815edee9",
        "85211282-1005-4112-9719-cd237febd1df", "ad23d34e-1ef3-4d51-b835-b7f6674af9f2",
        "b806fe92-67ac-493c-8c48-5514cae8dd97", "61a533ed-55be-4cb9-88e4-54380c839878",
        "45505566-5157-4a7b-8455-3fcadee6d2bc", "b698a0ec-2685-43b8-a1df-d1311b04727e",
    ):
        assert identifier in text
    assert "86400 / 87120 / 720" in text
    assert "87120 / 87840 / 720" in text
    assert "__flags = 4194304" in text
