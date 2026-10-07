"""Bounded local package construction, exact comparison and collision-safe sealing."""

import os
import shutil
import subprocess
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from pathlib import Path

from .audio_pattern import pcm
from .checksums import (
    canonical_json,
    checksum_bytes,
    file_hash,
    parse_checksums,
    parse_json,
    staging_path,
)
from .ffmpeg import (
    ToolchainProfile,
    _capture,
    decode_tokens,
    encode_tokens,
    mux_tokens,
    probe_tokens,
    verify_toolchain,
)
from .manifest import AssetRecord, lock_bytes, manifest_bytes, validate_lock, validate_manifest
from .model import AssetRole, BuildError, FailureStatus, Recipe
from .validate import (
    StreamFacts,
    object_value,
    parse_streams,
    validate_audio,
    validate_frame_records,
)
from .video_pattern import frame, source_digest
from .wav import wav_bytes, wav_data

AUTHORITATIVE_PATHS = tuple(
    sorted(
        tuple(r.relative_path for r in AssetRole)
        + ("manifest.v1.json", "generator.lock.json", "checksums.sha256")
    )
)


@dataclass(frozen=True)
class PackageComparison:
    package_digest: str
    equal_paths: tuple[str, ...]


class SealStatus(str, Enum):
    SEALED = "SEALED"
    EXISTING_IDENTICAL = "EXISTING_IDENTICAL"


@dataclass(frozen=True)
class SealResult:
    destination: Path
    status: SealStatus
    comparison: PackageComparison


def _inventory(root: Path) -> None:
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Real package directory required")
    paths = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ValueError("Symlink package entry forbidden")
        if path.is_file():
            paths.append(path.relative_to(root).as_posix())
        elif path.relative_to(root).as_posix() != "assets":
            raise ValueError("Unexpected package directory")
    if tuple(sorted(paths)) != AUTHORITATIVE_PATHS:
        raise ValueError("Missing or extra authoritative files")


def verify_package(root: Path, expected_digest: str | None = None) -> str:
    try:
        _inventory(root)
        blob = (root / "checksums.sha256").read_bytes()
        entries = parse_checksums(blob)
        if tuple(p for p, _ in entries) != tuple(
            p for p in AUTHORITATIVE_PATHS if p != "checksums.sha256"
        ):
            raise ValueError("Checksum path inventory mismatch")
        for path, digest in entries:
            if file_hash(staging_path(root, path)) != digest:
                raise ValueError("Checksum mismatch: " + path)
        validate_manifest((root / "manifest.v1.json").read_bytes())
        validate_lock((root / "generator.lock.json").read_bytes())
        digest = sha256(blob).hexdigest()
        if expected_digest is not None and digest != expected_digest:
            raise ValueError("Package digest mismatch")
        return digest
    except (OSError, ValueError) as error:
        raise BuildError(FailureStatus.CHECKSUM_FAILURE, str(error)) from error


def _equal_files(a: Path, b: Path) -> bool:
    if a.stat().st_size != b.stat().st_size:
        return False
    with a.open("rb") as left, b.open("rb") as right:
        while True:
            x = left.read(1024 * 1024)
            y = right.read(1024 * 1024)
            if x != y:
                return False
            if not x:
                return True


def compare_packages(a: Path, b: Path) -> PackageComparison:
    if a.resolve() == b.resolve():
        raise BuildError(
            FailureStatus.NONDETERMINISTIC_OUTPUT, "Two independent directories required"
        )
    try:
        first = verify_package(a)
        second = verify_package(b)
        different = tuple(p for p in AUTHORITATIVE_PATHS if not _equal_files(a / p, b / p))
        if first != second or different:
            raise ValueError("Differing paths: " + ",".join(different))
        return PackageComparison(first, AUTHORITATIVE_PATHS)
    except (OSError, ValueError) as error:
        raise BuildError(FailureStatus.NONDETERMINISTIC_OUTPUT, str(error)) from error


def _validate_media(
    root: Path, relative: str, role: AssetRole, tool: ToolchainProfile, source_pcm: bytes | None
) -> StreamFacts:
    facts = parse_streams(
        _capture(probe_tokens(tool, root, relative), FailureStatus.STRUCTURE_MISMATCH), role
    )
    if role.has_video:
        _capture(
            decode_tokens(tool, root, relative, audio=False), FailureStatus.FRAME_COUNT_MISMATCH
        )
        validate_frame_records(
            _capture(
                probe_tokens(tool, root, relative, frames=True), FailureStatus.FRAME_COUNT_MISMATCH
            )
        )
    if role.has_audio:
        assert source_pcm is not None
        decoded = (
            _capture(
                decode_tokens(tool, root, relative, audio=True), FailureStatus.AUDIO_DECODE_MISMATCH
            )
            if role.has_video
            else wav_data(staging_path(root, relative).read_bytes())
        )
        validate_audio(source_pcm, decoded)
    return facts


def _encode(tool: ToolchainProfile, root: Path, role: AssetRole, output: str) -> str:
    digest = sha256()
    log = staging_path(root, "encode-error.log")
    try:
        with log.open("xb") as errors:
            process = subprocess.Popen(
                encode_tokens(tool, root, output),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=errors,
                shell=False,
            )
            try:
                assert process.stdin is not None
                for index in range(720):
                    pixels = frame(role, index).tobytes(order="C")
                    digest.update(pixels)
                    process.stdin.write(pixels)
                process.stdin.close()
                code = process.wait(timeout=600)
            except BaseException:
                process.kill()
                process.wait()
                raise
        if code != 0 or log.read_bytes().strip():
            raise BuildError(
                FailureStatus.ENCODE_FAILURE,
                log.read_text(encoding="utf-8", errors="replace")[-4000:],
            )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise BuildError(FailureStatus.ENCODE_FAILURE, str(error)) from error
    finally:
        if log.exists():
            log.unlink()
    return digest.hexdigest()


def build_package(staging: Path, tool: ToolchainProfile, source_commit: str) -> Path:
    """New directory only. A result is not sealed or published by this function."""
    try:
        verify_toolchain(tool)
    except (OSError, ValueError) as error:
        raise BuildError(FailureStatus.TOOLCHAIN_UNSUPPORTED, str(error)) from error
    recipe_digest = file_hash(Path(__file__).with_name("recipe.v1.json"))
    lock = lock_bytes(tool, source_commit, recipe_digest)
    staging.mkdir(parents=False, exist_ok=False)
    root = staging / "package"
    root.mkdir()
    (root / "assets").mkdir()
    work = staging / "work"
    work.mkdir()
    records = []
    for role in AssetRole:
        rgb = None
        audio = pcm(role) if role.has_audio else None
        if role.has_video:
            rgb = _encode(tool, staging, role, "work/video.mov")
            _validate_media(staging, "work/video.mov", AssetRole.VIDEO_ONLY, tool, None)
            if audio is not None:
                (work / "audio.wav").write_bytes(wav_bytes(audio))
                _capture(
                    mux_tokens(
                        tool,
                        staging,
                        "work/video.mov",
                        "work/audio.wav",
                        "package/" + role.relative_path,
                    ),
                    FailureStatus.MUX_FAILURE,
                )
                (work / "audio.wav").unlink()
            else:
                shutil.copyfile(work / "video.mov", root / role.relative_path)
            (work / "video.mov").unlink()
        else:
            assert audio is not None
            (root / role.relative_path).write_bytes(wav_bytes(audio))
        facts = _validate_media(root, role.relative_path, role, tool, audio)
        records.append(
            AssetRecord(role, facts, rgb, sha256(audio).hexdigest() if audio is not None else None)
        )
    (root / "manifest.v1.json").write_bytes(manifest_bytes(tuple(records)))
    (root / "generator.lock.json").write_bytes(lock)
    entries = tuple(
        (p, file_hash(root / p)) for p in AUTHORITATIVE_PATHS if p != "checksums.sha256"
    )
    (root / "checksums.sha256").write_bytes(checksum_bytes(entries))
    verify_package(root)
    return root


def _validate_complete(root: Path, tool: ToolchainProfile) -> None:
    """Sealing never accepts merely matching hashes of unvalidated synthetic bytes."""
    verify_toolchain(tool)
    verify_package(root)
    manifest = object_value(parse_json((root / "manifest.v1.json").read_bytes()))
    records = manifest["assets"]
    assert isinstance(records, list)
    for raw in records:
        record = object_value(raw)
        role = AssetRole(str(record["role"]))
        audio = pcm(role) if role.has_audio else None
        _validate_media(root, role.relative_path, role, tool, audio)
        if audio is not None and record["source_pcm_digest"] != sha256(audio).hexdigest():
            raise BuildError(FailureStatus.SOURCE_GENERATION_FAILURE, "Source PCM digest mismatch")
        if role.has_video and record["source_rgb24_digest"] != source_digest(
            frame(role, i) for i in range(720)
        ):
            raise BuildError(FailureStatus.SOURCE_GENERATION_FAILURE, "Source RGB digest mismatch")


def seal_packages(a: Path, b: Path, destination: Path, tool: ToolchainProfile) -> SealResult:
    comparison = compare_packages(a, b)
    _validate_complete(a, tool)
    _validate_complete(b, tool)
    if destination.resolve().is_relative_to(a.resolve()) or destination.resolve().is_relative_to(
        b.resolve()
    ):
        raise BuildError(
            FailureStatus.PACKAGE_VERSION_COLLISION, "Seal destination must be independent"
        )
    destination.parent.mkdir(parents=True, exist_ok=True)
    # Cooperative exclusive reservation; authoritative directory appears only after a complete copy.
    reservation = destination.with_name(destination.name + ".seal-lock")
    owned = False
    try:
        with reservation.open("xb"):
            owned = True
            if destination.exists():
                try:
                    verify_package(destination, comparison.package_digest)
                except ValueError as error:
                    raise BuildError(FailureStatus.PACKAGE_VERSION_COLLISION, str(error)) from error
                return SealResult(destination, SealStatus.EXISTING_IDENTICAL, comparison)
            pending = destination.with_name(destination.name + ".pending")
            shutil.copytree(a, pending, symlinks=False)
            verify_package(pending, comparison.package_digest)
            if destination.exists():
                raise BuildError(
                    FailureStatus.PACKAGE_VERSION_COLLISION, "Destination appeared during sealing"
                )
            os.rename(pending, destination)
            return SealResult(destination, SealStatus.SEALED, comparison)
    except FileExistsError as error:
        raise BuildError(
            FailureStatus.PACKAGE_VERSION_COLLISION, "Existing reservation or pending package"
        ) from error
    finally:
        if owned:
            reservation.unlink()


def package_index(root: Path) -> bytes:
    digest = verify_package(root)
    return canonical_json(
        {
            "package_name": Recipe.package_name,
            "package_version": Recipe.package_version,
            "package_digest": digest,
            "fixture_catalog_version": "v1",
            "asset_contract_version": "v1",
            "generator_contract_version": "v1",
            "recipe_version": "v1",
            "manifest_sha256": file_hash(root / "manifest.v1.json"),
            "generator_lock_sha256": file_hash(root / "generator.lock.json"),
            "assets": [
                {"asset_id": r.asset_id, "sha256": file_hash(root / r.relative_path)}
                for r in AssetRole
            ],
            "chat_approval": "pending",
            "publication_reference": None,
        }
    )
