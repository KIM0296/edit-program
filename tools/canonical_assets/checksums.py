"""Canonical UTF-8 JSON, safe relative names and SHA-256 authority."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import TypeAlias, cast

JSON: TypeAlias = None | bool | int | float | str | list["JSON"] | dict[str, "JSON"]


def canonical_json(value: JSON) -> bytes:
    return (
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        + "\n"
    ).encode("utf-8")


def _pairs(pairs: list[tuple[str, JSON]]) -> dict[str, JSON]:
    out: dict[str, JSON] = {}
    for key, value in pairs:
        if key in out:
            raise ValueError("Duplicate JSON key")
        out[key] = value
    return out


def _constant(value: str) -> None:
    raise ValueError("Nonfinite JSON constant: " + value)


def parse_json(blob: bytes) -> JSON:
    if blob.startswith(b"\xef\xbb\xbf"):
        raise ValueError("BOM forbidden")
    return cast(
        JSON, json.loads(blob.decode("utf-8"), object_pairs_hook=_pairs, parse_constant=_constant)
    )


def safe_relative(value: str) -> str:
    if type(value) is not str:
        raise TypeError("Relative string required")
    value = value.replace("\\", "/")
    if (
        not value
        or any(c in value for c in ":\r\n\0")
        or any(ord(c) < 32 for c in value)
        or any(x in ("", ".", "..") for x in value.split("/"))
        or PurePosixPath(value).is_absolute()
    ):
        raise ValueError("Unsafe relative path")
    return value


def staging_path(root: Path, relative: str) -> Path:
    if not isinstance(root, Path):
        raise TypeError("Explicit staging Path required")
    path = root.joinpath(*safe_relative(relative).split("/"))
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError("Path escapes staging root")
    if path.is_symlink():
        raise ValueError("Symlink artifact forbidden")
    return path


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def valid_hash(value: str) -> bool:
    return re.fullmatch("[0-9a-f]{64}", value) is not None


def checksum_bytes(entries: tuple[tuple[str, str], ...]) -> bytes:
    normalized = tuple((safe_relative(path), digest) for path, digest in entries)
    if len({p for p, _ in normalized}) != len(normalized):
        raise ValueError("Duplicate checksum path")
    if any(not valid_hash(d) for _, d in normalized):
        raise ValueError("Lowercase SHA-256 required")
    return "".join(f"{digest}  {path}\n" for path, digest in sorted(normalized)).encode("utf-8")


def parse_checksums(blob: bytes) -> tuple[tuple[str, str], ...]:
    entries = []
    for line in blob.decode("utf-8").splitlines():
        if len(line) < 67 or line[64:66] != "  ":
            raise ValueError("Malformed checksum entry")
        entries.append((line[66:], line[:64]))
    result = tuple(entries)
    if not result or checksum_bytes(result) != blob:
        raise ValueError("Noncanonical checksums")
    return result
