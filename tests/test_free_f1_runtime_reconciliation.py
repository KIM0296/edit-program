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


def i1_evidence():
    return REPORT.read_text(encoding="utf-8").split(
        "# F1 I1 RUNTIME EVIDENCE RECONCILIATION REPORT", 1
    )[1]


def test_i1_preserves_exact_pair_and_activity():
    text = i1_evidence()
    expected = {
        "target match count": "1",
        "project ID": "8023de71-f9c7-41fc-8fbf-fa1baebf613a",
        "timeline ID": "b806fe92-67ac-493c-8c48-5514cae8dd97",
        "placement ID": "61a533ed-55be-4cb9-88e4-54380c839878",
        "source ID": "ad23d34e-1ef3-4d51-b835-b7f6674af9f2",
        "start": "86400", "end": "87120", "duration": "720",
    }
    for field, value in expected.items():
        row = next(line for line in text.splitlines() if line.startswith(f"| {field} |"))
        assert row.split("|")[2:4] == [f" {value} ", f" {value} "]
        if field != "target match count":
            assert "STABLE_OBSERVED_AT_LEVEL" in row
    assert "02:05:20 KST" in text and "11:35:20 KST" in text
    assert "9 hours 30 minutes" in text
    for activity in ("Resolve edit: NO", "playback/scrub: NO", "timeline switch: NO",
                     "project close/reopen: NO", "other activity: PC idle"):
        assert activity in text


def test_i1_does_not_promote_scope_or_fabricate_capture():
    text = i1_evidence()
    for limit in (
        "exact observed interval only", "I2/I3/I4: NOT OBSERVED / NOT AUTHORIZED",
        "No SESSION_LOCAL_VERIFIED or PERSISTENT_VERIFIED promotion",
        "Calendar dates, run IDs and exact command transcripts: NOT SUPPLIED",
        "P2 reviewed probe: NOT EXECUTED", "Endpoint convention: NOT_ESTABLISHED",
        "FrameRange construction: NOT AUTHORIZED", "Coordinate status: CORRESPONDENCE_CANDIDATE",
    ):
        assert limit in text
    assert "FREE_F1|OBS|" not in text


def c03_evidence():
    return REPORT.read_text(encoding="utf-8").split(
        "# F1 C03 RUNTIME EVIDENCE RECONCILIATION REPORT", 1
    )[1]


def test_c03_retains_independent_three_position_oracle_and_native_facts():
    text = c03_evidence()
    for value in (
        "U0 | A visible frame 0719 | 01:00:29:23",
        "U1 | EMPTY_GAP | 01:00:30:00",
        "U2 | B visible frame 0000 | 01:00:30:01",
        "30c4875c-0c2c-4601-aba7-741c6e10f682",
        "cc44d760-69a9-4020-bdd2-803e4a2447d8",
        "e422c5e4-fb8b-4dfc-acc3-98e7d61ce0cc",
        "86400 / 87120 / 720", "87121 / 87841 / 720",
        "__flags = 4194304", "720 + 1 gap + 720 = 1441",
    ):
        assert value in text
    assert "playhead only moved; clip did not move" in text
    assert "screenshots: NOT SUPPLIED" in text


def test_c03_bounded_discriminator_preserves_semantic_limits():
    text = c03_evidence()
    for value in (
        "C03 attempt 1 gate: PASS - bounded case only",
        "C02 | zero gap | 87120 | 87120 | 0 | 0 | 1",
        "C03 | one-frame gap | 87120 | 87121 | 1 | 1 | 2",
        "H1: SUPPORTED", "H2: CONTRADICTED", "H3: NOT globally eliminated",
        "Coordinate status: CORRESPONDENCE_CANDIDATE",
        "Endpoint convention: NOT_ESTABLISHED globally",
        "FrameRange construction: NOT AUTHORIZED",
        "P2 reviewed probe: NOT EXECUTED",
    ):
        assert value in text
    assert "FREE_F1|OBS|" not in text
