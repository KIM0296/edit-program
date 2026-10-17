"""CSA-002 pinned FFmpeg/ffprobe synthetic qualification runner.

This runner consumes only a committed synthetic AAC-LC 48 kHz fixture.
It never reads user/project media, never accesses Resolve, and does not grant G2.
The committed receipt describes a GitHub-hosted Linux reference toolchain only.

Authority model:

- The receipt is evidence, never authority. Its canonical digest must equal
  ``APPROVED_RECEIPT_SHA256`` (fixed in this trusted code) before any
  substantive receipt field is consumed.
- Independently of the digest, the command, fixture, known-answer, binary and
  environment contracts are re-checked against constants in this file.
- Candidate executables are located, resolved and hashed as bytes only. No
  candidate process is started unless BOTH ffmpeg and ffprobe match the
  approved path and SHA-256.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "tests/fixtures/csa_toolchain/ci_reference_receipt.json"
DEFAULT_FIXTURE = ROOT / "tests/fixtures/csa_toolchain/synthetic_aac48_stereo.m4a.b64"

RECEIPT_SCHEMA = "csa-002-ci-reference-receipt-v1"
RECEIPT_QUALIFICATION = "CI_REFERENCE_SYNTHETIC_PIN_CANDIDATE"

# Canonical digest (sorted keys, compact separators) of the Chat Gate reviewed
# receipt. Changing any receipt field requires a reviewed change to this line.
APPROVED_RECEIPT_SHA256 = "38f844c392bf4a5f5fab5f703536579c4fb9a443b901aaff38d846ff6c27b7ec"

APPROVED_ENVIRONMENT: dict[str, str] = {
    "os_family": "linux",
    "runner": "github-hosted-ubuntu-latest",
    "note": "Reference CI environment only; not a Windows/G2 acquisition qualification.",
    "apt_package": "ffmpeg",
    "apt_package_version": "7:6.1.1-3ubuntu5",
    "install_policy": "TEMPORARY_CI_REFERENCE_ONLY",
    "linked_library_pin_scope": "FFMPEG_CORE_LIBRARIES_ONLY",
}

APPROVED_BINARIES: dict[str, dict[str, str]] = {
    "ffmpeg": {
        "path": "/usr/bin/ffmpeg",
        "sha256": "ed16af623947494a72e284b6eb8ff225f2da22b38b5d5069c2fd4b4ba3384e41",
    },
    "ffprobe": {
        "path": "/usr/bin/ffprobe",
        "sha256": "272f6ebc634a63d9c8b4ca68e964119d980f25154e5aa2c35e5487da48e9a58f",
    },
}

APPROVED_SYNTHETIC_FIXTURE: dict[str, object] = {
    "file": "synthetic_aac48_stereo.m4a.b64",
    "decoded_source_sha256": "ead1fe9beaff5010eaf4b9adde660b389dc8d90dd422ab2b0124874d4795e12a",
    "decoded_source_bytes": 6819,
    "audio_stream_index": 0,
    "codec_name": "aac",
    "codec_profile": "LC",
    "sample_rate": 48000,
    "channels": 2,
    "channel_layout": "stereo",
    "expected_pcm_sha256": "39dc39bef5e87dd3e8b324257899f44bfaf7f5c54db9829873dcbfc6c01d1c47",
    "expected_pcm_bytes": 49152,
    "expected_sample_frames": 12288,
    "probe_second_decode_byte_identical": True,
}

SOURCE_PLACEHOLDER = "{SOURCE}"
OUTPUT_PLACEHOLDER = "{OUTPUT}"

APPROVED_PROBE_ARGS: tuple[str, ...] = (
    "-v",
    "error",
    "-show_format",
    "-show_streams",
    "-of",
    "json",
    SOURCE_PLACEHOLDER,
)

APPROVED_DECODE_ARGS: tuple[str, ...] = (
    "-v",
    "error",
    "-nostdin",
    "-threads",
    "1",
    "-i",
    SOURCE_PLACEHOLDER,
    "-map",
    "0:0",
    "-vn",
    "-sn",
    "-dn",
    "-c:a",
    "pcm_s16le",
    "-f",
    "s16le",
    OUTPUT_PLACEHOLDER,
)

# Exact placeholder layout: (token, index) in order of appearance.
APPROVED_PROBE_PLACEHOLDERS: tuple[tuple[str, int], ...] = ((SOURCE_PLACEHOLDER, 6),)
APPROVED_DECODE_PLACEHOLDERS: tuple[tuple[str, int], ...] = (
    (SOURCE_PLACEHOLDER, 6),
    (OUTPUT_PLACEHOLDER, 16),
)

FORBIDDEN_COMMAND_FLAGS = frozenset(
    {
        "-ss",
        "-sseof",
        "-t",
        "-to",
        "-ar",
        "-ac",
        "-af",
        "-filter",
        "-filter:a",
        "-filter_complex",
        "-lavfi",
        "-vf",
        "-filter_script",
        "-filter_complex_script",
        "-channel_layout",
        "-ch_layout",
        "-sample_fmt",
        "-async",
        "-atempo",
        "-itsoffset",
    }
)

RECEIPT_KEYS = frozenset(
    {
        "schema",
        "qualification",
        "source_probe",
        "environment",
        "ffmpeg",
        "ffprobe",
        "synthetic_fixture",
        "command_contract",
    }
)
SOURCE_PROBE_KEYS = frozenset({"workflow_run_id", "job_id", "branch_commit"})
PIN_KEYS = frozenset(
    {
        "path",
        "sha256",
        "version_first_line",
        "version_text_sha256",
        "buildconf_sha256",
        "libraries",
    }
)
LIBRARY_KEYS = frozenset({"name", "path", "sha256"})
COMMAND_CONTRACT_KEYS = frozenset({"decode_args", "probe_args"})

SHA256_RE = re.compile(r"[0-9a-f]{64}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}")

REFERENCE_HOST_PLATFORM_PREFIX = "linux"
LDD_PATH = "/usr/bin/ldd"

# Minimal, explicit environment for every subprocess this runner starts.
# Nothing material is inherited from the invoking shell.
CONTROLLED_ENV: dict[str, str] = {
    "PATH": "/usr/bin:/bin",
    "LC_ALL": "C",
    "LANG": "C",
}


class QualificationError(RuntimeError):
    """Fail-closed synthetic toolchain qualification error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_controlled(args: list[str]) -> bytes:
    """Single subprocess gate: controlled env, no stdin, fail on non-zero exit."""
    proc = subprocess.run(
        args,
        check=True,
        capture_output=True,
        stdin=subprocess.DEVNULL,
        env=dict(CONTROLLED_ENV),
    )
    return proc.stdout


def run_text(args: list[str]) -> str:
    return run_controlled(args).decode("utf-8", errors="strict")


# ---------------------------------------------------------------------------
# P1-1: receipt is evidence, not authority
# ---------------------------------------------------------------------------


def _reject_duplicate_keys(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise QualificationError("RECEIPT_DUPLICATE_KEY")
        result[key] = value
    return result


def _reject_constant(token: str) -> Any:
    raise QualificationError("RECEIPT_NON_FINITE_NUMBER")


def canonical_receipt_digest(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return sha256_bytes(canonical)


def _require_exact(label: str, actual: object, expected: object) -> None:
    """Type-strict structural equality (rejects bool/int and int/float aliasing)."""
    if type(actual) is not type(expected):
        raise QualificationError(f"{label}_TYPE_MISMATCH")
    if isinstance(expected, dict):
        actual_map = cast(dict[str, object], actual)
        if set(actual_map) != set(expected):
            raise QualificationError(f"{label}_KEYS_MISMATCH")
        for key, value in expected.items():
            _require_exact(label, actual_map[key], value)
    elif isinstance(expected, list | tuple):
        actual_seq = cast(list[object], actual)
        if len(actual_seq) != len(expected):
            raise QualificationError(f"{label}_LENGTH_MISMATCH")
        for item, value in zip(actual_seq, expected, strict=True):
            _require_exact(label, item, value)
    elif actual != expected:
        raise QualificationError(f"{label}_MISMATCH")


def _require_mapping(label: str, value: object, keys: frozenset[str]) -> dict[str, Any]:
    if type(value) is not dict:
        raise QualificationError(f"{label}_TYPE_MISMATCH")
    mapping = cast(dict[str, Any], value)
    if set(mapping) != keys:
        raise QualificationError(f"{label}_KEYS_MISMATCH")
    return mapping


def _require_str(label: str, value: object, pattern: re.Pattern[str] | None = None) -> str:
    if type(value) is not str or not value:
        raise QualificationError(f"{label}_TYPE_MISMATCH")
    if pattern is not None and pattern.fullmatch(value) is None:
        raise QualificationError(f"{label}_FORMAT_MISMATCH")
    return value


def _require_positive_int(label: str, value: object) -> int:
    if type(value) is not int or value <= 0:
        raise QualificationError(f"{label}_TYPE_MISMATCH")
    return value


def placeholder_layout(
    args: list[str] | tuple[str, ...], label: str = "COMMAND_CONTRACT"
) -> tuple[tuple[str, int], ...]:
    """Return (placeholder, index) pairs; any other brace token is refused."""
    layout: list[tuple[str, int]] = []
    for index, token in enumerate(args):
        if token in (SOURCE_PLACEHOLDER, OUTPUT_PLACEHOLDER):
            layout.append((token, index))
        elif "{" in token or "}" in token:
            raise QualificationError(f"{label}_UNKNOWN_PLACEHOLDER")
    return tuple(layout)


def validate_command_args(
    label: str,
    value: object,
    approved: tuple[str, ...],
    approved_layout: tuple[tuple[str, int], ...],
) -> tuple[str, ...]:
    if type(value) is not list:
        raise QualificationError(f"{label}_TYPE_MISMATCH")
    args = cast(list[object], value)
    if any(type(item) is not str for item in args):
        raise QualificationError(f"{label}_TYPE_MISMATCH")
    text_args = cast(list[str], args)
    if placeholder_layout(text_args, label) != approved_layout:
        raise QualificationError(f"{label}_PLACEHOLDER_MISMATCH")
    for token in text_args:
        flag = token.split("=", 1)[0]
        if flag in FORBIDDEN_COMMAND_FLAGS or flag.startswith(("-af:", "-filter:", "-ar:", "-ac:")):
            raise QualificationError(f"{label}_FORBIDDEN_FLAG")
    if tuple(text_args) != approved:
        raise QualificationError(f"{label}_DRIFT")
    return approved


def _validate_pin(label: str, value: object, tool: str) -> dict[str, Any]:
    pin = _require_mapping(label, value, PIN_KEYS)
    approved = APPROVED_BINARIES[tool]
    if _require_str(f"{label}_PATH", pin["path"]) != approved["path"]:
        raise QualificationError(f"{label}_PATH_NOT_APPROVED")
    if _require_str(f"{label}_SHA256", pin["sha256"], SHA256_RE) != approved["sha256"]:
        raise QualificationError(f"{label}_SHA256_NOT_APPROVED")
    _require_str(f"{label}_VERSION_FIRST_LINE", pin["version_first_line"])
    _require_str(f"{label}_VERSION_TEXT_SHA256", pin["version_text_sha256"], SHA256_RE)
    _require_str(f"{label}_BUILDCONF_SHA256", pin["buildconf_sha256"], SHA256_RE)
    if type(pin["libraries"]) is not list or not pin["libraries"]:
        raise QualificationError(f"{label}_LIBRARIES_TYPE_MISMATCH")
    for item in cast(list[object], pin["libraries"]):
        lib = _require_mapping(f"{label}_LIBRARY", item, LIBRARY_KEYS)
        _require_str(f"{label}_LIBRARY_NAME", lib["name"])
        if not _require_str(f"{label}_LIBRARY_PATH", lib["path"]).startswith("/"):
            raise QualificationError(f"{label}_LIBRARY_PATH_FORMAT_MISMATCH")
        _require_str(f"{label}_LIBRARY_SHA256", lib["sha256"], SHA256_RE)
    return pin


def validate_receipt_contract(payload: object) -> dict[str, Any]:
    """Code-side contract check, independent of the receipt digest."""
    receipt = _require_mapping("RECEIPT", payload, RECEIPT_KEYS)
    if receipt["schema"] != RECEIPT_SCHEMA:
        raise QualificationError("RECEIPT_SCHEMA_MISMATCH")
    if receipt["qualification"] != RECEIPT_QUALIFICATION:
        raise QualificationError("RECEIPT_QUALIFICATION_MISMATCH")

    probe = _require_mapping("RECEIPT_SOURCE_PROBE", receipt["source_probe"], SOURCE_PROBE_KEYS)
    _require_positive_int("RECEIPT_SOURCE_PROBE_RUN", probe["workflow_run_id"])
    _require_positive_int("RECEIPT_SOURCE_PROBE_JOB", probe["job_id"])
    _require_str("RECEIPT_SOURCE_PROBE_COMMIT", probe["branch_commit"], COMMIT_RE)

    environment = receipt["environment"]
    if type(environment) is dict and environment.get("os_family") != "linux":
        raise QualificationError("RECEIPT_ENVIRONMENT_NOT_LINUX_REFERENCE")
    _require_exact("RECEIPT_ENVIRONMENT", environment, APPROVED_ENVIRONMENT)

    _validate_pin("RECEIPT_FFMPEG", receipt["ffmpeg"], "ffmpeg")
    _validate_pin("RECEIPT_FFPROBE", receipt["ffprobe"], "ffprobe")

    _require_exact(
        "RECEIPT_SYNTHETIC_FIXTURE", receipt["synthetic_fixture"], APPROVED_SYNTHETIC_FIXTURE
    )

    contract = _require_mapping(
        "RECEIPT_COMMAND_CONTRACT", receipt["command_contract"], COMMAND_CONTRACT_KEYS
    )
    validate_command_args(
        "PROBE_COMMAND_CONTRACT",
        contract["probe_args"],
        APPROVED_PROBE_ARGS,
        APPROVED_PROBE_PLACEHOLDERS,
    )
    validate_command_args(
        "DECODE_COMMAND_CONTRACT",
        contract["decode_args"],
        APPROVED_DECODE_ARGS,
        APPROVED_DECODE_PLACEHOLDERS,
    )
    return receipt


def load_receipt(path: Path, *, approved_sha256: str = APPROVED_RECEIPT_SHA256) -> dict[str, Any]:
    """Load the receipt, refusing it unless its digest is the approved one.

    ``approved_sha256`` comes from trusted code only (it is never read from the
    receipt or the CLI). The code-side contract is enforced after the digest.
    """
    payload = json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=_reject_duplicate_keys,
        parse_constant=_reject_constant,
    )
    if type(payload) is not dict:
        raise QualificationError("RECEIPT_TYPE_MISMATCH")
    if canonical_receipt_digest(cast(dict[str, Any], payload)) != approved_sha256:
        raise QualificationError("RECEIPT_DIGEST_NOT_APPROVED")
    return validate_receipt_contract(payload)


# ---------------------------------------------------------------------------
# P1-2: never execute an unapproved binary
# ---------------------------------------------------------------------------


def locate_candidate(name: str, search_path: str | None) -> Path:
    found = shutil.which(name, path=search_path)
    if found is None:
        raise QualificationError(f"{name.upper()}_NOT_FOUND")
    return Path(found).resolve()


def preflight_binaries(
    expected: Mapping[str, Mapping[str, Any]], *, search_path: str | None
) -> dict[str, Path]:
    """Locate, resolve and hash BOTH tools as bytes only. Starts no process.

    Every tool is checked before deciding, so one bad binary blocks the other.
    """
    resolved: dict[str, Path] = {}
    failures: list[str] = []
    for name in ("ffmpeg", "ffprobe"):
        try:
            path = locate_candidate(name, search_path)
        except QualificationError as exc:
            failures.append(str(exc))
            continue
        pin = expected[name]
        if str(path) != pin["path"]:
            failures.append(f"{name.upper()}_PATH_NOT_APPROVED")
            continue
        if sha256_file(path) != pin["sha256"]:
            failures.append(f"{name.upper()}_SHA256_NOT_APPROVED")
            continue
        resolved[name] = path
    if failures:
        raise QualificationError("BINARY_PREFLIGHT_REFUSED:" + ",".join(failures))
    return resolved


CORE_LIBRARY_PREFIXES = (
    "libavutil",
    "libavcodec",
    "libavformat",
    "libavdevice",
    "libavfilter",
    "libswscale",
    "libswresample",
    "libpostproc",
)


def linked_library_pins(executable: Path) -> list[dict[str, str]]:
    text = run_text([LDD_PATH, str(executable)])
    pins: list[dict[str, str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        candidate = ""
        name = ""
        if "=>" in line:
            left, right = line.split("=>", 1)
            name = left.strip()
            candidate = right.strip().split(" ", 1)[0]
        elif line.startswith("/"):
            candidate = line.split(" ", 1)[0]
            name = Path(candidate).name
        if candidate.startswith("/") and any(name.startswith(p) for p in CORE_LIBRARY_PREFIXES):
            path = Path(candidate)
            if path.is_file():
                pins.append(
                    {
                        "name": name or path.name,
                        "path": str(path.resolve()),
                        "sha256": sha256_file(path),
                    }
                )
    pins.sort(key=lambda item: (item["name"], item["path"]))
    return pins


def inspect_binary(path: Path) -> dict[str, Any]:
    """Inspect an executable that already passed the path+hash preflight."""
    version_text = run_text([str(path), "-version"])
    buildconf_text = run_text([str(path), "-buildconf"])
    lines = version_text.splitlines()
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "version_first_line": lines[0] if lines else "",
        "version_text_sha256": sha256_bytes(version_text.encode()),
        "buildconf_sha256": sha256_bytes(buildconf_text.encode()),
        "libraries": linked_library_pins(path),
    }


def compare_pin(label: str, actual: dict[str, Any], expected: Mapping[str, Any]) -> None:
    keys = (
        "path",
        "sha256",
        "version_first_line",
        "version_text_sha256",
        "buildconf_sha256",
        "libraries",
    )
    for key in keys:
        if actual[key] != expected[key]:
            raise QualificationError(f"{label.upper()}_{key.upper()}_DRIFT")


def qualify_binaries(
    expected: Mapping[str, Mapping[str, Any]], *, search_path: str | None
) -> dict[str, dict[str, Any]]:
    resolved = preflight_binaries(expected, search_path=search_path)
    pins: dict[str, dict[str, Any]] = {}
    for name in ("ffmpeg", "ffprobe"):
        pins[name] = inspect_binary(resolved[name])
        compare_pin(name, pins[name], expected[name])
    return pins


def recheck_binary_bytes(pins: Mapping[str, Mapping[str, Any]]) -> None:
    """Detect replacement of an approved binary while qualification ran."""
    for name in ("ffmpeg", "ffprobe"):
        if sha256_file(Path(pins[name]["path"])) != pins[name]["sha256"]:
            raise QualificationError(f"{name.upper()}_CHANGED_DURING_QUALIFICATION")


# ---------------------------------------------------------------------------
# Synthetic qualification
# ---------------------------------------------------------------------------


def materialize_args(
    template: list[str] | tuple[str, ...], *, source: Path, output: Path | None = None
) -> list[str]:
    args: list[str] = []
    for value in template:
        if value == SOURCE_PLACEHOLDER:
            args.append(str(source))
        elif value == OUTPUT_PLACEHOLDER:
            if output is None:
                raise QualificationError("OUTPUT_PLACEHOLDER_WITHOUT_OUTPUT")
            args.append(str(output))
        else:
            args.append(value)
    return args


def load_fixture(fixture_path: Path) -> bytes:
    fixture = base64.b64decode(fixture_path.read_text(encoding="utf-8").strip(), validate=True)
    if sha256_bytes(fixture) != APPROVED_SYNTHETIC_FIXTURE["decoded_source_sha256"]:
        raise QualificationError("SYNTHETIC_SOURCE_HASH_MISMATCH")
    if len(fixture) != APPROVED_SYNTHETIC_FIXTURE["decoded_source_bytes"]:
        raise QualificationError("SYNTHETIC_SOURCE_LENGTH_MISMATCH")
    return fixture


def verify(
    receipt_path: Path,
    fixture_path: Path,
    *,
    search_path: str | None = None,
    host_platform: str = sys.platform,
) -> dict[str, Any]:
    receipt = load_receipt(receipt_path)
    if not host_platform.startswith(REFERENCE_HOST_PLATFORM_PREFIX):
        raise QualificationError("HOST_PLATFORM_NOT_LINUX_REFERENCE")
    fixture = load_fixture(fixture_path)
    pins = qualify_binaries(
        {"ffmpeg": receipt["ffmpeg"], "ffprobe": receipt["ffprobe"]}, search_path=search_path
    )
    expected = APPROVED_SYNTHETIC_FIXTURE

    with tempfile.TemporaryDirectory(prefix="csa002-verify-") as tmp:
        root = Path(tmp)
        source = root / "synthetic.m4a"
        out_a = root / "a.pcm"
        out_b = root / "b.pcm"
        source.write_bytes(fixture)

        probe_args = [
            pins["ffprobe"]["path"],
            *materialize_args(APPROVED_PROBE_ARGS, source=source),
        ]
        probe_payload = json.loads(run_text(probe_args))
        audio = [s for s in probe_payload["streams"] if s.get("codec_type") == "audio"]
        if len(audio) != 1:
            raise QualificationError("SYNTHETIC_STREAM_COUNT_MISMATCH")
        stream = audio[0]
        facts = {
            "audio_stream_index": int(stream["index"]),
            "codec_name": stream.get("codec_name"),
            "codec_profile": stream.get("profile"),
            "sample_rate": int(stream.get("sample_rate", 0)),
            "channels": int(stream.get("channels", 0)),
            "channel_layout": stream.get("channel_layout"),
        }
        for key, value in facts.items():
            if value != expected[key]:
                raise QualificationError(f"SYNTHETIC_{key.upper()}_MISMATCH")

        for output in (out_a, out_b):
            args = [
                pins["ffmpeg"]["path"],
                *materialize_args(APPROVED_DECODE_ARGS, source=source, output=output),
            ]
            run_controlled(args)

        first = out_a.read_bytes()
        second = out_b.read_bytes()
        channels = cast(int, expected["channels"])
        if first != second:
            raise QualificationError("SECOND_DECODE_MISMATCH")
        if sha256_bytes(first) != expected["expected_pcm_sha256"]:
            raise QualificationError("PCM_HASH_MISMATCH")
        if len(first) != expected["expected_pcm_bytes"]:
            raise QualificationError("PCM_LENGTH_MISMATCH")
        if channels <= 0 or len(first) % (channels * 2):
            raise QualificationError("PCM_ALIGNMENT_MISMATCH")
        sample_frames = len(first) // (channels * 2)
        if sample_frames != expected["expected_sample_frames"]:
            raise QualificationError("PCM_SAMPLE_FRAME_MISMATCH")

    recheck_binary_bytes(pins)
    return {
        "schema": "csa-002-ci-reference-qualification-result-v1",
        "result": "CI_REFERENCE_TOOLCHAIN_SYNTHETIC_QUALIFIED",
        "scope": "GITHUB_HOSTED_UBUNTU_REFERENCE_ONLY",
        "receipt_sha256": APPROVED_RECEIPT_SHA256,
        "ffmpeg_sha256": pins["ffmpeg"]["sha256"],
        "ffprobe_sha256": pins["ffprobe"]["sha256"],
        "synthetic_source_sha256": expected["decoded_source_sha256"],
        "pcm_sha256": expected["expected_pcm_sha256"],
        "pcm_bytes": expected["expected_pcm_bytes"],
        "sample_frames": expected["expected_sample_frames"],
        "second_decode_byte_identical": True,
        "g2_authorized": False,
        "windows_host_qualified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--receipt", type=Path, default=DEFAULT_RECEIPT)
    parser.add_argument("--fixture", type=Path, default=DEFAULT_FIXTURE)
    args = parser.parse_args()
    if not args.verify:
        raise SystemExit("CSA002_VERIFY_MODE_REQUIRED")
    result = verify(args.receipt, args.fixture)
    print("CSA002_QUALIFICATION_JSON=" + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
