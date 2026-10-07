from hashlib import sha256

import pytest
from test_canonical_tooling import profile

from tools.canonical_assets.checksums import canonical_json, checksum_bytes, file_hash, parse_json
from tools.canonical_assets.manifest import (
    AssetRecord,
    lock_bytes,
    manifest_bytes,
    validate_lock,
    validate_manifest,
)
from tools.canonical_assets.model import AssetRole, BuildError, FailureStatus
from tools.canonical_assets.package import (
    SealStatus,
    build_package,
    compare_packages,
    seal_packages,
    verify_package,
)
from tools.canonical_assets.validate import AudioFacts, StreamFacts, VideoFacts


def records():
    return tuple(
        AssetRecord(
            role,
            StreamFacts(
                role,
                VideoFacts(
                    "dnxhd", "DNXHR LB", 1280, 720, "yuv422p", "24/1", "24/1", "progressive", "1:1"
                )
                if role.has_video
                else None,
                AudioFacts("pcm_s24le", 48000, 2, 24, "stereo") if role.has_audio else None,
            ),
            sha256(role.value.encode()).hexdigest() if role.has_video else None,
            sha256(role.value.encode()).hexdigest() if role.has_audio else None,
        )
        for role in AssetRole
    )


def tiny_package(root):
    root.mkdir()
    (root / "assets").mkdir()
    for role in AssetRole:
        (root / role.relative_path).write_bytes(role.value.encode())
    (root / "manifest.v1.json").write_bytes(manifest_bytes(records()))
    (root / "generator.lock.json").write_bytes(lock_bytes(profile(root), "a" * 40, "b" * 64))
    paths = tuple(role.relative_path for role in AssetRole) + (
        "manifest.v1.json",
        "generator.lock.json",
    )
    (root / "checksums.sha256").write_bytes(
        checksum_bytes(tuple((path, file_hash(root / path)) for path in paths))
    )
    return root


def test_manifest_and_lock_canonical_schema(tmp_path):
    blob = manifest_bytes(records())
    validate_manifest(blob)
    assert blob == canonical_json(parse_json(blob)) and b"package_digest" not in blob
    lock = lock_bytes(profile(tmp_path), "a" * 40, "b" * 64)
    validate_lock(lock)
    assert str(tmp_path).encode() not in lock
    assert b"dnxhr_lb" in lock and b"3.11.16" in lock
    for raw in (b"{}\n", blob[:-1]):
        with pytest.raises(BuildError):
            validate_manifest(raw)
    with pytest.raises(BuildError):
        manifest_bytes(records()[:-1])
    with pytest.raises(BuildError):
        validate_lock(b"{}\n")
    with pytest.raises(BuildError):
        lock_bytes(profile(tmp_path), "not-a-commit", "b" * 64)


def test_checksum_integrity_and_exact_reproduction(tmp_path):
    a = tiny_package(tmp_path / "a")
    b = tiny_package(tmp_path / "b")
    digest = verify_package(a)
    assert digest == sha256((a / "checksums.sha256").read_bytes()).hexdigest()
    comparison = compare_packages(a, b)
    assert comparison.package_digest == digest
    assert len(comparison.equal_paths) == 9
    (b / AssetRole.ALPHA.relative_path).write_bytes(b"changed")
    with pytest.raises(BuildError):
        verify_package(b)
    with pytest.raises(BuildError) as caught:
        compare_packages(a, b)
    assert caught.value.status == FailureStatus.NONDETERMINISTIC_OUTPUT


def test_seal_two_runs_only_no_overwrite_and_collision(tmp_path, monkeypatch):
    # This test isolates filesystem collision policy; media validation has separate tests.
    from tools.canonical_assets import package

    monkeypatch.setattr(package, "_validate_complete", lambda root, tool: None)
    tool = profile(tmp_path)
    a = tiny_package(tmp_path / "a")
    b = tiny_package(tmp_path / "b")
    destination = tmp_path / "sealed"
    with pytest.raises(BuildError):
        seal_packages(a, a, destination, tool)
    result = seal_packages(a, b, destination, tool)
    assert result.status == SealStatus.SEALED
    original = (destination / "checksums.sha256").read_bytes()
    assert seal_packages(a, b, destination, tool).status == SealStatus.EXISTING_IDENTICAL
    assert (destination / "checksums.sha256").read_bytes() == original
    (destination / "manifest.v1.json").write_bytes(b"changed")
    with pytest.raises(BuildError) as caught:
        seal_packages(a, b, destination, tool)
    assert caught.value.status == FailureStatus.PACKAGE_VERSION_COLLISION


def test_extra_file_and_hash_replacement_rejected(tmp_path):
    root = tiny_package(tmp_path / "a")
    (root / "extra").write_bytes(b"extra")
    with pytest.raises(BuildError):
        verify_package(root)


def test_build_refuses_unsupported_toolchain_without_staging(tmp_path):
    with pytest.raises(BuildError):
        build_package(tmp_path / "new", profile(tmp_path), "a" * 40)
    assert not (tmp_path / "new").exists()


def test_sealing_requires_real_media_validation(tmp_path):
    a = tiny_package(tmp_path / "a")
    b = tiny_package(tmp_path / "b")
    with pytest.raises(BuildError):
        seal_packages(a, b, tmp_path / "sealed", profile(tmp_path))
    assert not (tmp_path / "sealed").exists()


def test_corrupt_manifest_lock_and_checksum_digest_fail_closed(tmp_path):
    root = tiny_package(tmp_path / "a")
    with pytest.raises(BuildError):
        verify_package(root, "0" * 64)
    lock = parse_json((root / "generator.lock.json").read_bytes())
    lock["commands"]["encode"].append("-untrusted-option")
    with pytest.raises(BuildError):
        validate_lock(canonical_json(lock))
    manifest = parse_json((root / "manifest.v1.json").read_bytes())
    manifest["assets"][0]["source_pcm_digest"] = "not-a-digest"
    with pytest.raises(BuildError):
        validate_manifest(canonical_json(manifest))


def test_seal_reservation_owned_by_other_writer_is_never_deleted(tmp_path, monkeypatch):
    from tools.canonical_assets import package

    monkeypatch.setattr(package, "_validate_complete", lambda root, tool: None)
    a = tiny_package(tmp_path / "a")
    b = tiny_package(tmp_path / "b")
    destination = tmp_path / "sealed"
    reservation = tmp_path / "sealed.seal-lock"
    reservation.write_bytes(b"other-writer")
    with pytest.raises(BuildError):
        seal_packages(a, b, destination, profile(tmp_path))
    assert reservation.read_bytes() == b"other-writer"
    assert not destination.exists()


def test_symlink_escape_rejected_when_available(tmp_path):
    from tools.canonical_assets.checksums import staging_path

    root = tmp_path / "root"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        (root / "link").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("Host does not permit symlink creation")
    with pytest.raises(ValueError):
        staging_path(root, "link/asset.mov")


def test_seal_checks_supplied_toolchain_against_authoritative_lock(tmp_path, monkeypatch):
    from dataclasses import replace

    from tools.canonical_assets import package

    root = tiny_package(tmp_path / "a")
    monkeypatch.setattr(package, "verify_toolchain", lambda tool: None)

    def forbidden(*args, **kwargs):
        raise AssertionError("media call before exact lock binding")

    monkeypatch.setattr(package, "_validate_media", forbidden)
    with pytest.raises(BuildError):
        package._validate_complete(root, replace(profile(tmp_path), ffmpeg_sha256="d" * 64))


@pytest.mark.parametrize("corrupt_source", ["pcm", "rgb"])
def test_sealing_rejects_source_provenance_mismatch(tmp_path, monkeypatch, corrupt_source):
    from pathlib import Path

    from tools.canonical_assets import package

    root = tiny_package(tmp_path / "a")
    tool = profile(root)
    (root / "generator.lock.json").write_bytes(
        lock_bytes(tool, "a" * 40, file_hash(Path(package.__file__).with_name("recipe.v1.json")))
    )
    (root / "checksums.sha256").write_bytes(
        checksum_bytes(
            tuple(
                (path, file_hash(root / path))
                for path in package.AUTHORITATIVE_PATHS
                if path != "checksums.sha256"
            )
        )
    )
    monkeypatch.setattr(package, "verify_toolchain", lambda tool: None)
    monkeypatch.setattr(package, "_validate_media", lambda *args: None)
    monkeypatch.setattr(
        package, "pcm", lambda role: b"bad" if corrupt_source == "pcm" else role.value.encode()
    )
    monkeypatch.setattr(package, "source_digest", lambda frames: "0" * 64)
    with pytest.raises(BuildError) as caught:
        package._validate_complete(root, tool)
    assert caught.value.status == FailureStatus.SOURCE_GENERATION_FAILURE
    assert ("PCM" if corrupt_source == "pcm" else "RGB") in str(caught.value)


def test_encoder_failure_does_not_retry(tmp_path, monkeypatch):
    import io

    import numpy as np

    from tools.canonical_assets import package

    calls = []

    class FailedEncoder:
        stdin = io.BytesIO()

        def wait(self, timeout=None):
            return 1

    def popen(tokens, **kwargs):
        calls.append((tokens, kwargs))
        return FailedEncoder()

    monkeypatch.setattr(package.subprocess, "Popen", popen)
    monkeypatch.setattr(package, "frame", lambda role, index: np.zeros((1,), dtype=np.uint8))
    with pytest.raises(BuildError) as caught:
        package._encode(profile(tmp_path), tmp_path, AssetRole.ALPHA, "output.mov")
    assert caught.value.status == FailureStatus.ENCODE_FAILURE
    assert len(calls) == 1 and calls[0][1]["shell"] is False
