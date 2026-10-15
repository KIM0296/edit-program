"""CSA-002 pinned FFmpeg/ffprobe synthetic qualification runner.

This runner consumes only a committed synthetic AAC-LC 48 kHz fixture.
It never reads user/project media, never accesses Resolve, and does not grant G2.
The committed receipt describes a GitHub-hosted Linux reference toolchain only.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RECEIPT = ROOT / "tests/fixtures/csa_toolchain/ci_reference_receipt.json"
DEFAULT_FIXTURE = ROOT / "tests/fixtures/csa_toolchain/synthetic_aac48_stereo.m4a.b64"


class QualificationError(RuntimeError):
    """Fail-closed synthetic toolchain qualification error."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_text(args: list[str]) -> str:
    proc = subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout.decode("utf-8", errors="strict")


def linked_library_pins(executable: Path) -> list[dict[str, str]]:
    text = run_text(["ldd", str(executable)])
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
        if candidate.startswith("/"):
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


def binary_pin(name: str) -> dict[str, Any]:
    found = shutil.which(name)
    if found is None:
        raise QualificationError(f"{name.upper()}_NOT_FOUND")
    path = Path(found).resolve()
    version_text = run_text([str(path), "-version"])
    buildconf_text = run_text([str(path), "-buildconf"])
    return {
        "path": str(path),
        "sha256": sha256_file(path),
        "version_first_line": version_text.splitlines()[0],
        "version_text_sha256": sha256_bytes(version_text.encode()),
        "buildconf_sha256": sha256_bytes(buildconf_text.encode()),
        "libraries": linked_library_pins(path),
    }


def load_receipt(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "csa-002-ci-reference-receipt-v1":
        raise QualificationError("RECEIPT_SCHEMA_MISMATCH")
    if payload.get("qualification") != "CI_REFERENCE_SYNTHETIC_PIN_CANDIDATE":
        raise QualificationError("RECEIPT_QUALIFICATION_MISMATCH")
    return payload


def compare_pin(label: str, actual: dict[str, Any], expected: dict[str, Any]) -> None:
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


def materialize_args(template: list[str], *, source: Path, output: Path | None = None) -> list[str]:
    args: list[str] = []
    for value in template:
        if value == "{SOURCE}":
            args.append(str(source))
        elif value == "{OUTPUT}":
            if output is None:
                raise QualificationError("OUTPUT_PLACEHOLDER_WITHOUT_OUTPUT")
            args.append(str(output))
        else:
            args.append(value)
    return args


def verify(receipt_path: Path, fixture_path: Path) -> dict[str, Any]:
    receipt = load_receipt(receipt_path)
    ffmpeg = binary_pin("ffmpeg")
    ffprobe = binary_pin("ffprobe")
    compare_pin("ffmpeg", ffmpeg, receipt["ffmpeg"])
    compare_pin("ffprobe", ffprobe, receipt["ffprobe"])

    fixture = base64.b64decode(fixture_path.read_text(encoding="utf-8").strip(), validate=True)
    expected = receipt["synthetic_fixture"]
    if sha256_bytes(fixture) != expected["decoded_source_sha256"]:
        raise QualificationError("SYNTHETIC_SOURCE_HASH_MISMATCH")
    if len(fixture) != expected["decoded_source_bytes"]:
        raise QualificationError("SYNTHETIC_SOURCE_LENGTH_MISMATCH")

    with tempfile.TemporaryDirectory(prefix="csa002-verify-") as tmp:
        root = Path(tmp)
        source = root / "synthetic.m4a"
        out_a = root / "a.pcm"
        out_b = root / "b.pcm"
        source.write_bytes(fixture)

        probe_args = [
            ffprobe["path"],
            *materialize_args(receipt["command_contract"]["probe_args"], source=source),
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

        decode_template = receipt["command_contract"]["decode_args"]
        for output in (out_a, out_b):
            args = [ffmpeg["path"], *materialize_args(decode_template, source=source, output=output)]
            subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        first = out_a.read_bytes()
        second = out_b.read_bytes()
        if first != second:
            raise QualificationError("SECOND_DECODE_MISMATCH")
        if sha256_bytes(first) != expected["expected_pcm_sha256"]:
            raise QualificationError("PCM_HASH_MISMATCH")
        if len(first) != expected["expected_pcm_bytes"]:
            raise QualificationError("PCM_LENGTH_MISMATCH")
        if expected["channels"] <= 0 or len(first) % (expected["channels"] * 2):
            raise QualificationError("PCM_ALIGNMENT_MISMATCH")
        sample_frames = len(first) // (expected["channels"] * 2)
        if sample_frames != expected["expected_sample_frames"]:
            raise QualificationError("PCM_SAMPLE_FRAME_MISMATCH")

    canonical_receipt = json.dumps(receipt, sort_keys=True, separators=(",", ":")).encode()
    return {
        "schema": "csa-002-ci-reference-qualification-result-v1",
        "result": "CI_REFERENCE_TOOLCHAIN_SYNTHETIC_QUALIFIED",
        "scope": "GITHUB_HOSTED_UBUNTU_REFERENCE_ONLY",
        "receipt_sha256": sha256_bytes(canonical_receipt),
        "ffmpeg_sha256": ffmpeg["sha256"],
        "ffprobe_sha256": ffprobe["sha256"],
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
