"""CSA-002 receipt/fixture/preflight contract tests. No FFmpeg subprocess is run here."""

from __future__ import annotations

import base64
import copy
import json
import os
import re
import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

import pytest

from tools import csa_toolchain_qualification as q

FIXTURES = Path(__file__).parent / "fixtures/csa_toolchain"
RECEIPT = FIXTURES / "ci_reference_receipt.json"
FIXTURE = FIXTURES / "synthetic_aac48_stereo.m4a.b64"
SHA_RE = re.compile(r"[0-9a-f]{64}")


def load_receipt() -> dict[str, Any]:
    return cast(dict[str, Any], json.loads(RECEIPT.read_text(encoding="utf-8")))


def test_synthetic_fixture_is_exactly_pinned() -> None:
    receipt = load_receipt()
    raw = base64.b64decode(FIXTURE.read_text(encoding="utf-8").strip(), validate=True)
    expected = receipt["synthetic_fixture"]
    assert q.sha256_bytes(raw) == expected["decoded_source_sha256"]
    assert len(raw) == expected["decoded_source_bytes"] == 6819
    assert expected["codec_name"] == "aac"
    assert expected["codec_profile"] == "LC"
    assert expected["sample_rate"] == 48000
    assert expected["channels"] == 2


def test_ci_reference_pin_scope_is_explicitly_non_g2() -> None:
    receipt = load_receipt()
    environment = receipt["environment"]
    assert receipt["qualification"] == "CI_REFERENCE_SYNTHETIC_PIN_CANDIDATE"
    assert environment["runner"] == "github-hosted-ubuntu-latest"
    assert environment["apt_package_version"] == "7:6.1.1-3ubuntu5"
    assert environment["install_policy"] == "TEMPORARY_CI_REFERENCE_ONLY"
    assert environment["note"].endswith("not a Windows/G2 acquisition qualification.")


def test_tool_binary_and_core_library_hashes_are_pinned() -> None:
    receipt = load_receipt()
    expected_names = {
        "libavcodec.so.60",
        "libavdevice.so.60",
        "libavfilter.so.9",
        "libavformat.so.60",
        "libavutil.so.58",
        "libpostproc.so.57",
        "libswresample.so.4",
        "libswscale.so.7",
    }
    for tool in ("ffmpeg", "ffprobe"):
        pin = receipt[tool]
        assert SHA_RE.fullmatch(pin["sha256"])
        assert SHA_RE.fullmatch(pin["version_text_sha256"])
        assert SHA_RE.fullmatch(pin["buildconf_sha256"])
        assert {item["name"] for item in pin["libraries"]} == expected_names
        assert all(SHA_RE.fullmatch(item["sha256"]) for item in pin["libraries"])


def test_decode_command_contract_has_no_processing_or_seek() -> None:
    args = load_receipt()["command_contract"]["decode_args"]
    assert args == [
        "-v",
        "error",
        "-nostdin",
        "-threads",
        "1",
        "-i",
        "{SOURCE}",
        "-map",
        "0:0",
        "-vn",
        "-sn",
        "-dn",
        "-c:a",
        "pcm_s16le",
        "-f",
        "s16le",
        "{OUTPUT}",
    ]
    for forbidden in ("-ss", "-t", "-to", "-ar", "-ac", "-af", "-filter:a", "-filter_complex"):
        assert forbidden not in args


def test_materialize_args_only_replaces_declared_placeholders(tmp_path: Path) -> None:
    source = tmp_path / "synthetic.m4a"
    output = tmp_path / "out.pcm"
    result = q.materialize_args(
        ["-i", "{SOURCE}", "-f", "s16le", "{OUTPUT}"], source=source, output=output
    )
    assert result == ["-i", str(source), "-f", "s16le", str(output)]
    with pytest.raises(q.QualificationError, match="OUTPUT_PLACEHOLDER_WITHOUT_OUTPUT"):
        q.materialize_args(["{OUTPUT}"], source=source)


def test_receipt_loader_fails_closed_on_schema_or_promotion(tmp_path: Path) -> None:
    bad_schema = load_receipt()
    bad_schema["schema"] = "other"
    assert_refused_both_ways(tmp_path, bad_schema, "RECEIPT_SCHEMA_MISMATCH")

    promoted = load_receipt()
    promoted["qualification"] = "VERIFIED_LIVE"
    assert_refused_both_ways(tmp_path, promoted, "RECEIPT_QUALIFICATION_MISMATCH")


def test_pin_comparator_detects_any_bound_field_drift() -> None:
    expected = cast(dict[str, Any], load_receipt()["ffmpeg"])
    actual = dict(expected)
    actual["sha256"] = "0" * 64
    with pytest.raises(q.QualificationError, match="FFMPEG_SHA256_DRIFT"):
        q.compare_pin("ffmpeg", actual, expected)


def test_expected_known_answer_counts_are_exact() -> None:
    expected = load_receipt()["synthetic_fixture"]
    assert expected["expected_pcm_sha256"] == (
        "39dc39bef5e87dd3e8b324257899f44bfaf7f5c54db9829873dcbfc6c01d1c47"
    )
    assert expected["expected_pcm_bytes"] == 49152
    assert expected["expected_sample_frames"] == 12288
    assert expected["probe_second_decode_byte_identical"] is True


def test_receipt_contains_no_user_windows_path() -> None:
    text = RECEIPT.read_text(encoding="utf-8")
    assert "C:\\" not in text
    assert "/Users/" not in text


# ---------------------------------------------------------------------------
# P1-1 regressions: the receipt cannot define its own approval basis.
# ---------------------------------------------------------------------------


def write_receipt(path: Path, payload: dict[str, Any]) -> Path:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def mutated_receipt() -> dict[str, Any]:
    return copy.deepcopy(load_receipt())


def assert_refused_both_ways(tmp_path: Path, payload: dict[str, Any], contract_error: str) -> None:
    """Refused by the approved digest, and still refused if that digest were re-approved."""
    path = write_receipt(tmp_path / "receipt.json", payload)
    with pytest.raises(q.QualificationError, match="RECEIPT_DIGEST_NOT_APPROVED"):
        q.load_receipt(path)
    with pytest.raises(q.QualificationError, match=contract_error):
        q.load_receipt(path, approved_sha256=q.canonical_receipt_digest(payload))


def test_committed_receipt_matches_trusted_approved_digest() -> None:
    receipt = q.load_receipt(RECEIPT)
    assert q.canonical_receipt_digest(receipt) == q.APPROVED_RECEIPT_SHA256
    assert q.APPROVED_RECEIPT_SHA256 == (
        "38f844c392bf4a5f5fab5f703536579c4fb9a443b901aaff38d846ff6c27b7ec"
    )


def test_receipt_with_added_filter_flag_is_refused(tmp_path: Path) -> None:
    payload = mutated_receipt()
    payload["command_contract"]["decode_args"][-1:-1] = ["-af", "volume=2"]
    assert_refused_both_ways(tmp_path, payload, "DECODE_COMMAND_CONTRACT_PLACEHOLDER_MISMATCH")
    # Same flag substituted without shifting the placeholder layout.
    payload = mutated_receipt()
    payload["command_contract"]["decode_args"][9] = "-af"
    assert_refused_both_ways(tmp_path, payload, "DECODE_COMMAND_CONTRACT_FORBIDDEN_FLAG")


@pytest.mark.parametrize(
    ("index", "flag"),
    [(9, "-ar"), (10, "-ac"), (11, "-filter_complex"), (0, "-ss"), (1, "-filter:a")],
)
def test_receipt_with_resample_or_downmix_flag_is_refused(
    tmp_path: Path, index: int, flag: str
) -> None:
    payload = mutated_receipt()
    payload["command_contract"]["decode_args"][index] = flag
    assert_refused_both_ways(tmp_path, payload, "DECODE_COMMAND_CONTRACT_FORBIDDEN_FLAG")


def test_receipt_with_unlisted_command_drift_is_refused(tmp_path: Path) -> None:
    payload = mutated_receipt()
    payload["command_contract"]["decode_args"][8] = "0:1"
    assert_refused_both_ways(tmp_path, payload, "DECODE_COMMAND_CONTRACT_DRIFT")
    payload = mutated_receipt()
    payload["command_contract"]["probe_args"][5] = "xml"
    assert_refused_both_ways(tmp_path, payload, "PROBE_COMMAND_CONTRACT_DRIFT")


def _reverse(args: list[str]) -> None:
    args.reverse()


def _extra_output(args: list[str]) -> None:
    args.append("{OUTPUT}")


def _missing_output(args: list[str]) -> None:
    args.remove("{OUTPUT}")


def _extra_source(args: list[str]) -> None:
    args.insert(0, "{SOURCE}")


def _swap_placeholders(args: list[str]) -> None:
    args[6], args[16] = args[16], args[6]


def _unknown_placeholder(args: list[str]) -> None:
    args[16] = "{OUT}"


@pytest.mark.parametrize(
    "mutate",
    [
        _reverse,
        _extra_output,
        _missing_output,
        _extra_source,
        _swap_placeholders,
        _unknown_placeholder,
    ],
)
def test_receipt_with_malformed_placeholders_is_refused(
    tmp_path: Path, mutate: Callable[[list[str]], None]
) -> None:
    payload = mutated_receipt()
    mutate(payload["command_contract"]["decode_args"])
    assert_refused_both_ways(tmp_path, payload, "DECODE_COMMAND_CONTRACT_.*PLACEHOLDER")


def test_receipt_with_non_list_or_non_string_command_is_refused(tmp_path: Path) -> None:
    payload = mutated_receipt()
    payload["command_contract"]["decode_args"][4] = 1
    assert_refused_both_ways(tmp_path, payload, "DECODE_COMMAND_CONTRACT_TYPE_MISMATCH")
    payload = mutated_receipt()
    payload["command_contract"]["probe_args"] = " ".join(q.APPROVED_PROBE_ARGS)
    assert_refused_both_ways(tmp_path, payload, "PROBE_COMMAND_CONTRACT_TYPE_MISMATCH")


def test_receipt_and_fixture_modified_together_are_refused(tmp_path: Path) -> None:
    forged = b"\x00forged-synthetic-source"
    fixture = tmp_path / "forged.m4a.b64"
    fixture.write_text(base64.b64encode(forged).decode(), encoding="utf-8")
    payload = mutated_receipt()
    payload["synthetic_fixture"]["decoded_source_sha256"] = q.sha256_bytes(forged)
    payload["synthetic_fixture"]["decoded_source_bytes"] = len(forged)
    receipt = write_receipt(tmp_path / "receipt.json", payload)
    with pytest.raises(q.QualificationError, match="RECEIPT_DIGEST_NOT_APPROVED"):
        q.verify(receipt, fixture, host_platform="linux")
    assert_refused_both_ways(tmp_path, payload, "RECEIPT_SYNTHETIC_FIXTURE_MISMATCH")
    with pytest.raises(q.QualificationError, match="SYNTHETIC_SOURCE_HASH_MISMATCH"):
        q.load_fixture(fixture)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("expected_pcm_sha256", "0" * 64),
        ("expected_pcm_bytes", 49156),
        ("expected_sample_frames", 12289),
        ("expected_pcm_bytes", 49152.0),
        ("probe_second_decode_byte_identical", 1),
        ("sample_rate", 44100),
    ],
)
def test_receipt_with_changed_known_answer_is_refused(
    tmp_path: Path, key: str, value: object
) -> None:
    payload = mutated_receipt()
    payload["synthetic_fixture"][key] = value
    assert_refused_both_ways(tmp_path, payload, "RECEIPT_SYNTHETIC_FIXTURE_")


@pytest.mark.parametrize("os_family", ["windows", "darwin"])
def test_receipt_with_non_linux_environment_is_refused(tmp_path: Path, os_family: str) -> None:
    payload = mutated_receipt()
    payload["environment"]["os_family"] = os_family
    assert_refused_both_ways(tmp_path, payload, "RECEIPT_ENVIRONMENT_NOT_LINUX_REFERENCE")
    payload = mutated_receipt()
    payload["environment"]["install_policy"] = "WINDOWS_HOST_QUALIFIED"
    assert_refused_both_ways(tmp_path, payload, "RECEIPT_ENVIRONMENT_MISMATCH")


def test_receipt_with_rebound_binary_pin_is_refused(tmp_path: Path) -> None:
    payload = mutated_receipt()
    payload["ffmpeg"]["path"] = "/tmp/ffmpeg"
    assert_refused_both_ways(tmp_path, payload, "RECEIPT_FFMPEG_PATH_NOT_APPROVED")
    payload = mutated_receipt()
    payload["ffprobe"]["sha256"] = "1" * 64
    assert_refused_both_ways(tmp_path, payload, "RECEIPT_FFPROBE_SHA256_NOT_APPROVED")


def test_receipt_with_extra_or_duplicate_keys_is_refused(tmp_path: Path) -> None:
    payload = mutated_receipt()
    payload["approved"] = True
    assert_refused_both_ways(tmp_path, payload, "RECEIPT_KEYS_MISMATCH")
    text = RECEIPT.read_text(encoding="utf-8").replace(
        '"schema": "csa-002-ci-reference-receipt-v1",',
        '"schema": "csa-002-ci-reference-receipt-v1",\n  "schema": "other",',
        1,
    )
    path = tmp_path / "dup.json"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(q.QualificationError, match="RECEIPT_DUPLICATE_KEY"):
        q.load_receipt(path)


def test_verify_refuses_non_linux_host_before_any_subprocess(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    with pytest.raises(q.QualificationError, match="HOST_PLATFORM_NOT_LINUX_REFERENCE"):
        q.verify(RECEIPT, FIXTURE, host_platform="win32")
    assert calls == []


# ---------------------------------------------------------------------------
# P1-2 regressions: no unapproved candidate is ever executed.
# ---------------------------------------------------------------------------

# Fake inspection output keyed by the last argument ("-version", "-buildconf",
# or the executable path for the ldd call, which reports no libraries).
FAKE_OUTPUTS = {"-version": b"", "-buildconf": b"conf\n"}


def record_subprocess_calls(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    def fake_run_controlled(args: list[str]) -> bytes:
        calls.append(list(args))
        return FAKE_OUTPUTS.get(args[-1], b"")

    def forbidden_run(*args: object, **kwargs: object) -> object:
        raise AssertionError("subprocess.run must only be reached via run_controlled")

    monkeypatch.setattr(q, "run_controlled", fake_run_controlled)
    monkeypatch.setattr(subprocess, "run", forbidden_run)
    return calls


def make_tool(directory: Path, name: str, content: bytes) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / (name + (".exe" if os.name == "nt" else ""))
    path.write_bytes(content)
    path.chmod(0o755)
    return path.resolve()


def approved_pins(tools: dict[str, Path]) -> dict[str, dict[str, Any]]:
    """Pins that match the files' bytes and the FAKE_OUTPUTS inspection."""
    return {
        name: {
            "path": str(path),
            "sha256": q.sha256_file(path),
            "version_first_line": "",
            "version_text_sha256": q.sha256_bytes(FAKE_OUTPUTS["-version"]),
            "buildconf_sha256": q.sha256_bytes(FAKE_OUTPUTS["-buildconf"]),
            "libraries": [],
        }
        for name, path in tools.items()
    }


def calls_to(calls: list[list[str]], tool: Path) -> list[list[str]]:
    return [call for call in calls if str(tool) in call]


@pytest.fixture
def approved_tools(tmp_path: Path) -> dict[str, Path]:
    approved = tmp_path / "approved"
    return {
        "ffmpeg": make_tool(approved, "ffmpeg", b"approved-ffmpeg"),
        "ffprobe": make_tool(approved, "ffprobe", b"approved-ffprobe"),
    }


def test_path_hijacked_ffmpeg_is_never_executed(
    tmp_path: Path, approved_tools: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    hijack = make_tool(tmp_path / "hijack", "ffmpeg", b"malicious")
    search = os.pathsep.join([str(hijack.parent), str(approved_tools["ffprobe"].parent)])
    with pytest.raises(q.QualificationError, match="FFMPEG_PATH_NOT_APPROVED"):
        q.qualify_binaries(approved_pins(approved_tools), search_path=search)
    assert calls == []


def test_changed_ffmpeg_bytes_at_approved_path_are_never_executed(
    approved_tools: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    pins = approved_pins(approved_tools)
    approved_tools["ffmpeg"].write_bytes(b"replaced-in-place")
    with pytest.raises(q.QualificationError, match="FFMPEG_SHA256_NOT_APPROVED"):
        q.qualify_binaries(pins, search_path=str(approved_tools["ffmpeg"].parent))
    assert calls == []


def test_valid_ffmpeg_with_changed_ffprobe_executes_neither(
    approved_tools: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    pins = approved_pins(approved_tools)
    approved_tools["ffprobe"].write_bytes(b"replaced-ffprobe")
    with pytest.raises(q.QualificationError, match="FFPROBE_SHA256_NOT_APPROVED") as info:
        q.qualify_binaries(pins, search_path=str(approved_tools["ffmpeg"].parent))
    assert "FFMPEG" not in str(info.value)
    assert calls == []


def test_ffprobe_only_path_hijack_is_never_executed(
    tmp_path: Path, approved_tools: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    hijack = make_tool(tmp_path / "hijack", "ffprobe", b"malicious-probe")
    search = os.pathsep.join([str(hijack.parent), str(approved_tools["ffmpeg"].parent)])
    with pytest.raises(q.QualificationError, match="FFPROBE_PATH_NOT_APPROVED"):
        q.qualify_binaries(approved_pins(approved_tools), search_path=search)
    assert calls == []


def test_missing_tool_blocks_execution_of_the_other(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    ffmpeg = make_tool(tmp_path / "only", "ffmpeg", b"approved-ffmpeg")
    pins = approved_pins({"ffmpeg": ffmpeg, "ffprobe": ffmpeg})
    with pytest.raises(q.QualificationError, match="FFPROBE_NOT_FOUND"):
        q.qualify_binaries(pins, search_path=str(ffmpeg.parent))
    assert calls == []


@pytest.mark.parametrize(
    ("field", "drifted"),
    [
        ("version_first_line", "ffmpeg version 7.0"),
        ("version_text_sha256", "a" * 64),
        ("buildconf_sha256", "b" * 64),
        ("libraries", [{"name": "libavcodec.so.60", "path": "/x", "sha256": "c" * 64}]),
    ],
)
def test_approved_bytes_with_build_drift_are_inspected_then_rejected(
    approved_tools: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    drifted: object,
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    pins = approved_pins(approved_tools)
    pins["ffmpeg"][field] = drifted
    with pytest.raises(q.QualificationError, match=f"FFMPEG_{field.upper()}_DRIFT"):
        q.qualify_binaries(pins, search_path=str(approved_tools["ffmpeg"].parent))
    ffmpeg = str(approved_tools["ffmpeg"])
    assert [ffmpeg, "-version"] in calls
    assert [ffmpeg, "-buildconf"] in calls
    assert [q.LDD_PATH, ffmpeg] in calls
    assert calls_to(calls, approved_tools["ffprobe"]) == []


def test_approved_binaries_pass_and_are_rechecked_after_use(
    approved_tools: dict[str, Path], monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = record_subprocess_calls(monkeypatch)
    pins = approved_pins(approved_tools)
    qualified = q.qualify_binaries(pins, search_path=str(approved_tools["ffmpeg"].parent))
    assert len(calls) == 6
    q.recheck_binary_bytes(qualified)
    approved_tools["ffprobe"].write_bytes(b"swapped-after-inspection")
    with pytest.raises(q.QualificationError, match="FFPROBE_CHANGED_DURING_QUALIFICATION"):
        q.recheck_binary_bytes(qualified)


def test_controlled_subprocess_environment_is_minimal(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    class Proc:
        stdout = b"ok"

    def fake_run(args: list[str], **kwargs: Any) -> Proc:
        seen.update(kwargs)
        return Proc()

    monkeypatch.setenv("LD_PRELOAD", "/tmp/evil.so")
    monkeypatch.setenv("PATH", "/tmp/hijack")
    monkeypatch.setattr(subprocess, "run", fake_run)
    assert q.run_controlled(["/usr/bin/ffmpeg", "-version"]) == b"ok"
    assert seen["env"] == {"PATH": "/usr/bin:/bin", "LC_ALL": "C", "LANG": "C"}
    assert seen["stdin"] is subprocess.DEVNULL
    assert seen["check"] is True
