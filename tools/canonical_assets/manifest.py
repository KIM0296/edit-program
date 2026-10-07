"""Semantic manifest and normalized toolchain provenance, never self-referential hashes."""

import re
from dataclasses import dataclass
from pathlib import Path

from .checksums import JSON, canonical_json, parse_json, valid_hash
from .ffmpeg import ToolchainProfile, decode_tokens, encode_tokens, mux_tokens, probe_tokens
from .model import AssetRole, BuildError, FailureStatus, Recipe, role_check
from .validate import StreamFacts, object_value


@dataclass(frozen=True)
class AssetRecord:
    role: AssetRole
    streams: StreamFacts
    source_rgb24_digest: str | None
    source_pcm_digest: str | None

    def __post_init__(self) -> None:
        role_check(self.role)
        if not isinstance(self.streams, StreamFacts) or self.streams.role != self.role:
            raise BuildError(FailureStatus.MANIFEST_FAILURE, "Observed stream binding mismatch")
        for needed, digest in (
            (self.role.has_video, self.source_rgb24_digest),
            (self.role.has_audio, self.source_pcm_digest),
        ):
            if (needed and (digest is None or not valid_hash(digest))) or (
                not needed and digest is not None
            ):
                raise BuildError(
                    FailureStatus.MANIFEST_FAILURE, "Source provenance digest mismatch"
                )

    def record(self) -> dict[str, JSON]:
        return {
            "asset_id": self.role.asset_id,
            "role": self.role.value,
            "asset_revision": "v1",
            "relative_path": self.role.relative_path,
            "media_kind": "AV"
            if self.role.has_video and self.role.has_audio
            else "VIDEO"
            if self.role.has_video
            else "AUDIO",
            "duration_frames": 720 if self.role.has_video else None,
            "duration_samples": 1440000 if self.role.has_audio else None,
            "stream_count": int(self.role.has_video) + int(self.role.has_audio),
            "streams": self.streams.record(),
            "diagnostic_pattern_version": "v1",
            "checksum_algorithm": "SHA-256",
            "source_rgb24_digest": self.source_rgb24_digest,
            "source_pcm_digest": self.source_pcm_digest,
        }


def manifest_bytes(records: tuple[AssetRecord, ...]) -> bytes:
    if len(records) != 6 or {r.role for r in records} != set(AssetRole):
        raise BuildError(
            FailureStatus.MANIFEST_FAILURE, "Exactly six unique validated assets required"
        )
    data: dict[str, JSON] = {
        "contract_version": "v1",
        "package_name": Recipe.package_name,
        "package_version": Recipe.package_version,
        "fixture_catalog_version": "v1",
        "video_profile": "DNxHR LB / 1280x720 / 24/1 progressive / yuv422p / SAR 1:1",
        "audio_profile": "PCM signed 24-bit / 48000 Hz / stereo / 1440000 samples",
        "assets": [r.record() for r in sorted(records, key=lambda r: r.role.value)],
    }
    return canonical_json(data)


def validate_manifest(blob: bytes) -> None:
    try:
        data = object_value(parse_json(blob))
        records = data["assets"]
        if not isinstance(records, list):
            raise TypeError("Assets list required")
        if len(records) != 6:
            raise ValueError("Exactly six assets required")
        expected_roles = sorted(AssetRole, key=lambda r: r.value)
        for raw, role in zip(records, expected_roles, strict=True):
            item = object_value(raw)
            # Exact constants compared against observed facts stored in the record.
            streams = object_value(item["streams"])
            from .validate import AudioFacts, VideoFacts

            facts = StreamFacts(
                role,
                VideoFacts(
                    "dnxhd", "DNXHR LB", 1280, 720, "yuv422p", "24/1", "24/1", "progressive", "1:1"
                )
                if role.has_video
                else None,
                AudioFacts("pcm_s24le", 48000, 2, 24, "stereo") if role.has_audio else None,
            )
            if streams != facts.record():
                raise ValueError("Stream facts mismatch")
            rgb = item["source_rgb24_digest"]
            audio = item["source_pcm_digest"]
            if rgb is not None and not isinstance(rgb, str):
                raise ValueError("RGB digest string required")
            if audio is not None and not isinstance(audio, str):
                raise ValueError("PCM digest string required")
            if item != AssetRecord(role, facts, rgb, audio).record():
                raise ValueError("Unexpected asset schema")
        first = records[0]
        assert isinstance(first, dict)
        expected = {
            "contract_version": "v1",
            "package_name": Recipe.package_name,
            "package_version": Recipe.package_version,
            "fixture_catalog_version": "v1",
            "video_profile": "DNxHR LB / 1280x720 / 24/1 progressive / yuv422p / SAR 1:1",
            "audio_profile": "PCM signed 24-bit / 48000 Hz / stereo / 1440000 samples",
            "assets": records,
        }
        if data != expected or canonical_json(data) != blob:
            raise ValueError("Noncanonical manifest")
    except (KeyError, ValueError, TypeError) as error:
        raise BuildError(FailureStatus.MANIFEST_FAILURE, str(error)) from error


def normalized_recipes(tool: ToolchainProfile) -> dict[str, JSON]:
    root = Path.cwd().resolve() / "__CANONICAL_STAGING__"

    def normalize(tokens: tuple[str, ...]) -> list[JSON]:
        return [
            token.replace(str(root), "$STAGING")
            .replace(str(tool.ffmpeg), "$FFMPEG")
            .replace(str(tool.ffprobe), "$FFPROBE")
            .replace("\\", "/")
            for token in tokens
        ]

    return {
        "encode": normalize(encode_tokens(tool, root, "work/video.mov")),
        "mux": normalize(
            mux_tokens(tool, root, "work/video.mov", "work/audio.wav", "package/assets/output.mov")
        ),
        "structure": normalize(probe_tokens(tool, root, "package/assets/output.mov")),
        "frames": normalize(probe_tokens(tool, root, "package/assets/output.mov", frames=True)),
        "video_decode": normalize(
            decode_tokens(tool, root, "package/assets/output.mov", audio=False)
        ),
        "audio_decode": normalize(
            decode_tokens(tool, root, "package/assets/output.mov", audio=True)
        ),
    }


def lock_bytes(tool: ToolchainProfile, source_commit: str, recipe_digest: str) -> bytes:
    if re.fullmatch("[0-9a-f]{40}", source_commit) is None or not valid_hash(recipe_digest):
        raise BuildError(
            FailureStatus.MANIFEST_FAILURE, "Real source commit / recipe hash required"
        )
    data: dict[str, JSON] = {
        "generator_name": "canonical_assets",
        "generator_version": "v1",
        "contract_version": "v1",
        "recipe_version": "v1",
        "generator_source_commit": source_commit,
        "recipe_sha256": recipe_digest,
        "python_version": tool.python_version,
        "numpy_version": tool.numpy_version,
        "ffmpeg_version": tool.ffmpeg_version,
        "ffprobe_version": tool.ffprobe_version,
        "configuration_digest": tool.configuration_digest,
        "ffmpeg_sha256": tool.ffmpeg_sha256,
        "ffprobe_sha256": tool.ffprobe_sha256,
        "toolchain_contract_version": tool.contract_version,
        "capabilities": list(tool.capabilities),
        "commands": normalized_recipes(tool),
        "metadata_normalization_version": "v1",
        "structural_validation_version": "v1",
        "decode_validation_version": "v1",
    }
    return canonical_json(data)


def validate_lock(blob: bytes) -> None:
    try:
        data = object_value(parse_json(blob))

        def text(key: str) -> str:
            value = data[key]
            if not isinstance(value, str):
                raise TypeError("Required string field " + key)
            return value

        capabilities = data["capabilities"]
        if not isinstance(capabilities, list) or not all(isinstance(x, str) for x in capabilities):
            raise ValueError("Capability list required")
        tool = ToolchainProfile(
            Path("$FFMPEG"),
            Path("$FFPROBE"),
            text("python_version"),
            text("numpy_version"),
            text("ffmpeg_version"),
            text("ffprobe_version"),
            text("configuration_digest"),
            text("ffmpeg_sha256"),
            text("ffprobe_sha256"),
            tuple(str(x) for x in capabilities),
            text("toolchain_contract_version"),
        )
        if lock_bytes(tool, text("generator_source_commit"), text("recipe_sha256")) != blob:
            raise ValueError("Noncanonical or altered generator lock")
    except (KeyError, ValueError, TypeError) as error:
        raise BuildError(FailureStatus.MANIFEST_FAILURE, str(error)) from error
