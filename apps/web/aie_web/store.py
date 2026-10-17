"""Per-project working directories under a configurable root (no database).

Project IDs are 32 random lowercase hex characters (``secrets.token_hex(16)``)
and are validated before any path is built, so a request can never address a
path outside the root. File names inside a project are a fixed allow-list; an
uploaded media file is always stored as ``media.bin`` (its original name is
only kept as text in ``meta.json``) and is never executed or interpreted
except by the PyAV demuxer and the ASR decoder.

Retention: projects without a trial code are deleted ``max_age_hours`` after
creation; projects created under a trial invite code are deleted when that
code expires or is revoked (see :mod:`aie_web.trial`).
"""

import json
import os
import re
import secrets
import shutil
import tempfile
import time
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

PROJECT_ID_RE = re.compile(r"^[0-9a-f]{32}$")
META = "meta.json"
TRANSCRIPT = "transcript.json"
APPROVAL = "approval.xml"
CONFIRMED = "confirmed.json"
MEDIA = "media.bin"
JOB = "job.json"
OVERRIDES = "overrides.json"  # INT-002: per-track policy overrides set on the confirm page
FILES = frozenset({META, TRANSCRIPT, APPROVAL, CONFIRMED, MEDIA, JOB, OVERRIDES})
MIB = 1024 * 1024


class ProjectNotFound(LookupError):
    """Unknown, expired or malformed project ID (never echoed back raw)."""


class MediaTooLarge(ValueError):
    """The streamed media upload exceeded its byte limit (nothing is kept)."""


def default_root() -> Path:
    return Path(tempfile.gettempdir()) / "aie-web-projects"


def _env_bool(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or not value.strip():
        return default
    return value.strip().lower() in ("1", "true", "yes", "on")


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    return float(value) if value and value.strip() else default


def _env_int(name: str, default: int) -> int:
    value = os.environ.get(name)
    return int(value) if value and value.strip() else default


def _env_list(name: str) -> tuple[str, ...]:
    value = os.environ.get(name, "")
    return tuple(item.strip() for item in value.split(",") if item.strip())


@dataclass(frozen=True)
class Settings:
    """All runtime configuration. :meth:`from_env` reads ``AIE_WEB_*`` / ``AIE_ASR_*``."""

    root: Path = field(default_factory=default_root)
    max_age_hours: float = 24.0
    max_transcript_bytes: int = 5 * MIB
    max_xml_bytes: int = 8 * MIB
    allowed_hosts: tuple[str, ...] = ("127.0.0.1", "localhost")
    # media upload + local ASR (WEB-002)
    max_media_bytes: int = 1024 * MIB
    max_media_seconds: int = 600
    asr_model: str = "small"
    asr_language: str = "ko"
    asr_vad: bool = True
    asr_device: str = "cpu"
    asr_compute_type: str = "int8"
    asr_model_dir: str | None = None
    # trial mode (external demo, invite codes)
    trial_mode: bool = False
    trial_code_hours: float = 72.0
    trial_max_projects: int = 5
    invite_codes: tuple[str, ...] = ()
    invites_file: Path | None = None
    # INT-002 brute-force protection on invite-code entry (see aie_web.ratelimit)
    trial_ip_failures: int = 5
    trial_global_failures: int = 50
    # deployment behind an HTTPS tunnel / reverse proxy
    trust_proxy: bool = False
    secure_cookies: bool = False
    # SITE-001 public site: contact shown for trial-code requests (placeholder default)
    contact_email: str = "contact@safestay.kr"

    @property
    def max_request_bytes(self) -> int:
        return max(self.max_transcript_bytes, self.max_xml_bytes) + 256 * 1024

    @property
    def max_media_request_bytes(self) -> int:
        return self.max_media_bytes + MIB

    @property
    def invites_path(self) -> Path:
        return self.invites_file if self.invites_file is not None else self.root / "invites.json"

    @classmethod
    def from_env(cls) -> "Settings":
        root = os.environ.get("AIE_WEB_ROOT")
        invites = os.environ.get("AIE_WEB_INVITES_FILE")
        hosts = _env_list("AIE_WEB_ALLOWED_HOSTS")
        return cls(
            root=Path(root) if root else default_root(),
            max_age_hours=_env_float("AIE_WEB_MAX_AGE_HOURS", 24.0),
            allowed_hosts=hosts or ("127.0.0.1", "localhost"),
            max_media_bytes=_env_int("AIE_WEB_MAX_MEDIA_MB", 1024) * MIB,
            max_media_seconds=round(_env_float("AIE_WEB_MAX_MEDIA_MINUTES", 10.0) * 60),
            asr_model=os.environ.get("AIE_ASR_MODEL", "small").strip() or "small",
            asr_language=os.environ.get("AIE_ASR_LANGUAGE", "ko").strip() or "ko",
            asr_vad=_env_bool("AIE_ASR_VAD", True),
            asr_device=os.environ.get("AIE_ASR_DEVICE", "cpu").strip() or "cpu",
            asr_compute_type=os.environ.get("AIE_ASR_COMPUTE_TYPE", "int8").strip() or "int8",
            asr_model_dir=os.environ.get("AIE_ASR_MODEL_DIR") or None,
            trial_mode=_env_bool("AIE_WEB_TRIAL", False),
            trial_code_hours=_env_float("AIE_WEB_TRIAL_CODE_HOURS", 72.0),
            trial_max_projects=_env_int("AIE_WEB_TRIAL_MAX_PROJECTS", 5),
            invite_codes=_env_list("AIE_WEB_INVITE_CODES"),
            invites_file=Path(invites) if invites else None,
            trial_ip_failures=_env_int("AIE_WEB_TRIAL_IP_FAILURES", 5),
            trial_global_failures=_env_int("AIE_WEB_TRIAL_GLOBAL_FAILURES", 50),
            trust_proxy=_env_bool("AIE_WEB_TRUST_PROXY", False),
            secure_cookies=_env_bool("AIE_WEB_SECURE_COOKIES", False),
            contact_email=os.environ.get("AIE_WEB_CONTACT_EMAIL", "").strip()
            or "contact@safestay.kr",
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

    def create(self, meta: dict[str, object], transcript: bytes | None = None) -> str:
        self.root.mkdir(parents=True, exist_ok=True)
        while True:
            project_id = secrets.token_hex(16)
            directory = self._dir(project_id)
            try:
                directory.mkdir()
                break
            except FileExistsError:  # pragma: no cover - 128-bit collision
                continue
        if transcript is not None:
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

    def update_meta(self, project_id: str, **values: object) -> dict[str, object]:
        data = self.meta(project_id)
        data.update(values)
        self.write(project_id, META, json.dumps(data, ensure_ascii=False).encode("utf-8"))
        return data

    def read(self, project_id: str, name: str) -> bytes | None:
        path = self.path(project_id, name)
        return path.read_bytes() if path.is_file() else None

    def read_json(self, project_id: str, name: str) -> dict[str, object] | None:
        raw = self.read(project_id, name)
        if raw is None:
            return None
        data = json.loads(raw.decode("utf-8"))
        return data if isinstance(data, dict) else None

    def write(self, project_id: str, name: str, data: bytes) -> None:
        self._write(self.path(project_id, name), data)

    def write_json(self, project_id: str, name: str, data: dict[str, object]) -> None:
        self.write(project_id, name, json.dumps(data, ensure_ascii=False).encode("utf-8"))

    def save_stream(self, project_id: str, name: str, source: BinaryIO, limit: int) -> int:
        """Copy ``source`` into the project in chunks; refuse (and keep nothing) above ``limit``."""
        target = self.path(project_id, name)
        temporary = target.with_name(target.name + ".part")
        written = 0
        try:
            with temporary.open("wb") as handle:
                while True:
                    chunk = source.read(MIB)
                    if not chunk:
                        break
                    written += len(chunk)
                    if written > limit:
                        raise MediaTooLarge("media upload exceeds the limit")
                    handle.write(chunk)
            os.replace(temporary, target)
        finally:
            if temporary.exists():
                temporary.unlink()
        return written

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
        shutil.rmtree(directory, ignore_errors=True)
        return not directory.exists()

    def project_ids(self) -> Iterator[str]:
        if not self.root.is_dir():
            return
        for entry in self.root.iterdir():
            if entry.is_dir() and PROJECT_ID_RE.match(entry.name):
                yield entry.name

    def delete_for_codes(self, code_ids: set[str]) -> int:
        """Delete every project created under one of the given trial code IDs."""
        if not code_ids:
            return 0
        removed = 0
        for project_id in list(self.project_ids()):
            directory = self.root / project_id
            if _trial_code(directory) in code_ids:
                shutil.rmtree(directory, ignore_errors=True)
                removed += 1
        return removed

    def cleanup(self, now: float | None = None) -> int:
        """Delete non-trial projects whose creation time is older than ``max_age_hours``."""
        if not self.root.is_dir():
            return 0
        cutoff = (time.time() if now is None else now) - self.settings.max_age_hours * 3600
        removed = 0
        for project_id in list(self.project_ids()):
            directory = self.root / project_id
            if _trial_code(directory) is not None:
                continue  # governed by its invite code's expiry
            if _created_at(directory) < cutoff:
                shutil.rmtree(directory, ignore_errors=True)
                removed += 1
        return removed

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        temporary = path.with_name(path.name + ".tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)


def _read_meta(directory: Path) -> dict[str, object] | None:
    try:
        data = json.loads((directory / META).read_text("utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _trial_code(directory: Path) -> str | None:
    data = _read_meta(directory)
    value = data.get("trial_code_id") if data is not None else None
    return value if isinstance(value, str) else None


def _created_at(directory: Path) -> float:
    data = _read_meta(directory)
    value = data.get("created_at") if data is not None else None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return directory.stat().st_mtime
    except OSError:
        return 0.0
