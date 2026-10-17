"""Per-project working directories under a configurable temp root (no database).

Project IDs are 32 random lowercase hex characters (``secrets.token_hex(16)``)
and are validated before any path is built, so a request can never address a
path outside the root. Projects older than ``max_age_hours`` are deleted by
:meth:`ProjectStore.cleanup`.
"""

import json
import os
import re
import secrets
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
META = "meta.json"
TRANSCRIPT = "transcript.json"
APPROVAL = "approval.xml"
CONFIRMED = "confirmed.json"
FILES = frozenset({META, TRANSCRIPT, APPROVAL, CONFIRMED})


class ProjectNotFound(LookupError):
    """Unknown, expired or malformed project ID (never echoed back raw)."""


def default_root() -> Path:
    return Path(tempfile.gettempdir()) / "aie-web-projects"


@dataclass(frozen=True)
class Settings:
    root: Path = field(default_factory=default_root)
    max_age_hours: float = 24.0
    max_transcript_bytes: int = 5 * 1024 * 1024
    max_xml_bytes: int = 8 * 1024 * 1024
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")

    @property
    def max_request_bytes(self) -> int:
        return max(self.max_transcript_bytes, self.max_xml_bytes) + 256 * 1024

    @classmethod
    def from_env(cls) -> "Settings":
        root = os.environ.get("AIE_WEB_ROOT")
        hours = os.environ.get("AIE_WEB_MAX_AGE_HOURS")
        return cls(
            root=Path(root) if root else default_root(),
            max_age_hours=float(hours) if hours else 24.0,
        )


class ProjectStore:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.root = settings.root.resolve()

    def _dir(self, project_id: str) -> Path:
        if not isinstance(project_id, str) or not PROJECT_ID_RE.match(project_id):
            raise ProjectNotFound("invalid project id")
        path = (self.root / project_id).resolve()
        if path.parent != self.root:
            raise ProjectNotFound("invalid project id")
        return path

    def path(self, project_id: str, name: str) -> Path:
        if name not in FILES:
            raise ValueError("unknown project file")
        directory = self._dir(project_id)
        if not (directory / META).is_file():
            raise ProjectNotFound("no such project")
        return directory / name

    def create(self, meta: dict[str, object], transcript: bytes) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            project_id = secrets.token_hex(16)
            directory = self._dir(project_id)
            try:
                directory.mkdir()
                break
            except FileExistsError:  # pragma: no cover - 128-bit collision
                continue
        self._write(directory / TRANSCRIPT, transcript)
        record = {"created_at": time.time(), **meta}
        self._write(directory / META, json.dumps(record, ensure_ascii=False).encode("utf-8"))
        return project_id

    def exists(self, project_id: str) -> bool:
        try:
            self.path(project_id, META)
        except ProjectNotFound:
            return False
        return True

    def meta(self, project_id: str) -> dict[str, object]:
        data = json.loads(self.path(project_id, META).read_text("utf-8"))
        if not isinstance(data, dict):
            raise ProjectNotFound("corrupt project")
        return data

    def read(self, project_id: str, name: str) -> bytes | None:
        path = self.path(project_id, name)
        return path.read_bytes() if path.is_file() else None

    def write(self, project_id: str, name: str, data: bytes) -> None:
        self._write(self.path(project_id, name), data)

    def remove(self, project_id: str, name: str) -> None:
        path = self.path(project_id, name)
        if path.is_file():
            path.unlink()

    def delete(self, project_id: str) -> bool:
        try:
            directory = self._dir(project_id)
        except ProjectNotFound:
            return False
        if not directory.is_dir():
            return False
        shutil.rmtree(directory)
        return True

    def cleanup(self, now: float | None = None) -> int:
        """Delete projects whose creation time is older than ``max_age_hours``."""
        if not self.root.is_dir():
            return 0
        cutoff = (time.time() if now is None else now) - self.settings.max_age_hours * 3600
        removed = 0
        for entry in self.root.iterdir():
            if not entry.is_dir() or not PROJECT_ID_RE.match(entry.name):
                continue
            created = _created_at(entry)
            if created < cutoff:
                shutil.rmtree(entry, ignore_errors=True)
                removed += 1
        return removed

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)


def _created_at(directory: Path) -> float:
    try:
        data = json.loads((directory / META).read_text("utf-8"))
        value = data.get("created_at") if isinstance(data, dict) else None
        if isinstance(value, (int, float)):
            return float(value)
    except (OSError, ValueError):
        pass
    try:
        return directory.stat().st_mtime
    except OSError:
        return 0.0
