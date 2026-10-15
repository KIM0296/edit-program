"""CSA-002 synthetic FFmpeg/ffprobe toolchain probe.

This script uses only generated synthetic audio. It never reads project/user media,
never accesses Resolve, and does not grant G2 qualification.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import shutil
import struct
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def run_text(args: list[str]) -> str:
    proc = subprocess.run(args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout.decode("utf-8", errors="strict")


def write_synthetic_wav(path: Path) -> None:
    rate = 48_000
    frames = 12_000  # 250 ms
    payload = bytearray()
    for i in range(frames):
        left = ((i * 257) % 65536) - 32768
        right = (((frames - 1 - i) * 911) % 65536) - 32768
        payload += struct.pack("<hh", left, right)
    with wave.open(str(path), "wb") as handle:
        handle.setnchannels(2)
        handle.setsampwidth(2)
        handle.setframerate(rate)
        handle.writeframes(bytes(payload))


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
        raise RuntimeError(f"{name.upper()}_NOT_FOUND")
    path = Path(found).resolve()
    version_text = run_text([str(path), "-version"])
    buildconf_text = run_text([str(path), "-buildconf"])
    return {
        "name": name,
        "path": str(path),
        "sha256": sha256_file(path),
        "version_text": version_text,
        "version_text_sha256": sha256_bytes(version_text.encode()),
        "buildconf_sha256": sha256_bytes(buildconf_text.encode()),
        "libraries": linked_library_pins(path),
    }


def probe() -> dict[str, Any]:
    ffmpeg = binary_pin("ffmpeg")
    ffprobe = binary_pin("ffprobe")
    with tempfile.TemporaryDirectory(prefix="csa002-") as tmp:
        root = Path(tmp)
        wav = root / "synthetic.wav"
        m4a = root / "synthetic.m4a"
        pcm_a = root / "a.pcm"
        pcm_b = root / "b.pcm"
        write_synthetic_wav(wav)

        encode_args = [
            ffmpeg["path"],
            "-v",
            "error",
            "-nostdin",
            "-threads",
            "1",
            "-i",
            str(wav),
            "-c:a",
            "aac",
            "-profile:a",
            "aac_low",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(m4a),
        ]
        subprocess.run(encode_args, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        probe_args = [
            ffprobe["path"],
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(m4a),
        ]
        probe_json = json.loads(run_text(probe_args))
        audio_streams = [stream for stream in probe_json["streams"] if stream.get("codec_type") == "audio"]
        if len(audio_streams) != 1:
            raise RuntimeError("SYNTHETIC_STREAM_COUNT_MISMATCH")
        stream = audio_streams[0]
        stream_index = int(stream["index"])
        if stream.get("codec_name") != "aac" or stream.get("profile") != "LC":
            raise RuntimeError("SYNTHETIC_CODEC_PROFILE_MISMATCH")
        if int(stream.get("sample_rate", 0)) != 48_000:
            raise RuntimeError("SYNTHETIC_SAMPLE_RATE_MISMATCH")
        if int(stream.get("channels", 0)) != 2:
            raise RuntimeError("SYNTHETIC_CHANNEL_COUNT_MISMATCH")

        decode_template = [
            ffmpeg["path"],
            "-v",
            "error",
            "-nostdin",
            "-threads",
            "1",
            "-i",
            str(m4a),
            "-map",
            f"0:{stream_index}",
            "-vn",
            "-sn",
            "-dn",
            "-c:a",
            "pcm_s16le",
            "-f",
            "s16le",
        ]
        for output in (pcm_a, pcm_b):
            subprocess.run(
                [*decode_template, str(output)],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )

        a = pcm_a.read_bytes()
        b = pcm_b.read_bytes()
        if a != b:
            raise RuntimeError("SYNTHETIC_SECOND_DECODE_MISMATCH")
        if len(a) % 4:
            raise RuntimeError("SYNTHETIC_PCM_BYTE_ALIGNMENT_MISMATCH")

        m4a_bytes = m4a.read_bytes()
        return {
            "schema": "csa-002-toolchain-probe-v1",
            "qualification": "SYNTHETIC_PROBE_ONLY",
            "ffmpeg": ffmpeg,
            "ffprobe": ffprobe,
            "synthetic": {
                "wav_sha256": sha256_file(wav),
                "m4a_sha256": sha256_bytes(m4a_bytes),
                "m4a_bytes": len(m4a_bytes),
                "m4a_base64": base64.b64encode(m4a_bytes).decode("ascii"),
                "audio_stream_index": stream_index,
                "codec_name": stream.get("codec_name"),
                "codec_profile": stream.get("profile"),
                "sample_rate": int(stream.get("sample_rate", 0)),
                "channels": int(stream.get("channels", 0)),
                "channel_layout": stream.get("channel_layout"),
                "pcm_sha256": sha256_bytes(a),
                "pcm_bytes": len(a),
                "sample_frames": len(a) // 4,
                "second_decode_byte_identical": True,
            },
            "ordered_encode_args": encode_args[1:-1],
            "ordered_probe_args": probe_args[1:-1],
            "ordered_decode_args": decode_template[1:],
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--probe", action="store_true")
    args = parser.parse_args()
    if not args.probe:
        raise SystemExit("CSA002_PROBE_MODE_REQUIRED")
    result = probe()
    print("CSA002_PROBE_JSON=" + json.dumps(result, sort_keys=True, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
