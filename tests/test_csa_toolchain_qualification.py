"""CSA-002 receipt/fixture contract tests. No FFmpeg subprocess is run here."""

from __future__ import annotations

import json
import re
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
    raw = q.base64.b64decode(FIXTURE.read_text(encoding="utf-8").strip(), validate=True)
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
    receipt = load_receipt()
    bad_schema = dict(receipt)
    bad_schema["schema"] = "other"
    path = tmp_path / "bad-schema.json"
    path.write_text(json.dumps(bad_schema), encoding="utf-8")
    with pytest.raises(q.QualificationError, match="RECEIPT_SCHEMA_MISMATCH"):
        q.load_receipt(path)

    promoted = dict(receipt)
    promoted["qualification"] = "VERIFIED_LIVE"
    path.write_text(json.dumps(promoted), encoding="utf-8")
    with pytest.raises(q.QualificationError, match="RECEIPT_QUALIFICATION_MISMATCH"):
        q.load_receipt(path)


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
