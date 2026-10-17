"""Trial invite codes for the external Free demo (enabled by ``AIE_WEB_TRIAL=1``).

Policy (user decision 2026-10-17):

- a code is valid for ``valid_hours`` (default 72) counted from its **first use**;
- within that window it may create up to ``max_projects`` projects (default 5);
- when the code expires, or an admin revokes it, every project, media file and
  result created under it is deleted (:meth:`InviteStore.dead_code_ids` +
  :meth:`ProjectStore.delete_for_codes`);
- only a SHA-256 of the normalized code is stored; the raw code is shown once
  when it is issued and is otherwise only in the tester's own cookie.

The store is one small JSON file written atomically (``os.replace``). A
process-wide lock serializes the web server's own updates; the admin CLI is
expected to be used by one operator at a time.
"""

import hashlib
import json
import os
import secrets
import threading
import time
from dataclasses import asdict, dataclass, replace
from pathlib import Path

_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # no 0/O, 1/I/L
_LOCK = threading.Lock()


def normalize(code: str) -> str:
    return "".join(ch for ch in code.strip().upper() if ch.isalnum())


def code_hash(code: str) -> str:
    return hashlib.sha256(("aie-trial-v1:" + normalize(code)).encode("utf-8")).hexdigest()


def code_id(code: str) -> str:
    return code_hash(code)[:12]


def generate_code() -> str:
    body = "".join(secrets.choice(_ALPHABET) for _ in range(12))
    return f"AIE-{body[:4]}-{body[4:8]}-{body[8:]}"


@dataclass(frozen=True)
class Invite:
    code_id: str
    label: str
    created_at: float
    valid_hours: float
    max_projects: int
    first_used_at: float | None = None
    projects_created: int = 0
    revoked: bool = False

    @property
    def expires_at(self) -> float | None:
        if self.first_used_at is None:
            return None
        return self.first_used_at + self.valid_hours * 3600

    def expired(self, now: float) -> bool:
        expires = self.expires_at
        return expires is not None and now >= expires

    def usable(self, now: float) -> bool:
        return not self.revoked and not self.expired(now)

    def remaining_projects(self) -> int:
        return max(0, self.max_projects - self.projects_created)

    def status(self, now: float) -> str:
        if self.revoked:
            return "REVOKED"
        if self.expired(now):
            return "EXPIRED"
        return "ACTIVE" if self.first_used_at is not None else "UNUSED"


class InviteError(ValueError):
    def __init__(self, message: str, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


class InviteStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    # ------------------------------------------------------------ persistence

    def _load(self) -> dict[str, Invite]:
        try:
            data = json.loads(self.path.read_text("utf-8"))
        except FileNotFoundError:
            return {}
        codes = data.get("codes", {}) if isinstance(data, dict) else {}
        result: dict[str, Invite] = {}
        for digest, record in codes.items():
            if isinstance(record, dict):
                result[str(digest)] = Invite(**record)
        return result

    def _save(self, invites: dict[str, Invite]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"version": 1, "codes": {k: asdict(v) for k, v in invites.items()}}
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(json.dumps(payload, indent=1, sort_keys=True), "utf-8")
        os.replace(temporary, self.path)

    # ------------------------------------------------------------ admin

    def issue(
        self,
        valid_hours: float,
        max_projects: int,
        label: str = "",
        code: str | None = None,
        now: float | None = None,
    ) -> tuple[str, Invite]:
        """Create a code (random unless given). Returns the raw code (shown once)."""
        if valid_hours <= 0 or max_projects <= 0:
            raise ValueError("valid_hours and max_projects must be positive")
        raw = code if code is not None else generate_code()
        if len(normalize(raw)) < 8:
            raise ValueError("invite codes need at least 8 letters or digits")
        with _LOCK:
            invites = self._load()
            digest = code_hash(raw)
            if digest in invites:
                return raw, invites[digest]
            invite = Invite(
                code_id=digest[:12],
                label=label[:80],
                created_at=time.time() if now is None else now,
                valid_hours=float(valid_hours),
                max_projects=int(max_projects),
            )
            invites[digest] = invite
            self._save(invites)
        return raw, invite

    def list(self) -> list[Invite]:
        return sorted(self._load().values(), key=lambda i: i.created_at)

    def revoke(self, code_or_id: str) -> Invite | None:
        with _LOCK:
            invites = self._load()
            for digest, invite in invites.items():
                if invite.code_id == code_or_id.strip().lower() or digest == code_hash(code_or_id):
                    invites[digest] = replace(invite, revoked=True)
                    self._save(invites)
                    return invites[digest]
        return None

    def dead_code_ids(self, now: float | None = None) -> set[str]:
        """Codes whose projects must be deleted (expired or revoked)."""
        moment = time.time() if now is None else now
        return {i.code_id for i in self._load().values() if not i.usable(moment)}

    # ------------------------------------------------------------ tester

    def lookup(self, code: str, now: float | None = None) -> Invite | None:
        """The usable invite for a raw code, or None (unknown, expired or revoked)."""
        if not code or len(code) > 64:
            return None
        invite = self._load().get(code_hash(code))
        moment = time.time() if now is None else now
        return invite if invite is not None and invite.usable(moment) else None

    def start(self, code: str, now: float | None = None) -> Invite:
        """Validate a code on the consent page; the 72-hour window starts at first use."""
        moment = time.time() if now is None else now
        with _LOCK:
            invites = self._load()
            digest = code_hash(code) if code and len(code) <= 64 else ""
            invite = invites.get(digest)
            if invite is None or not invite.usable(moment):
                raise InviteError("코드가 올바르지 않거나 만료되었습니다.", "INVITE_INVALID")
            if invite.first_used_at is None:
                invite = replace(invite, first_used_at=moment)
                invites[digest] = invite
                self._save(invites)
            return invite

    def consume_project(self, code: str, now: float | None = None) -> Invite:
        """Count one new project against the code (refuses above ``max_projects``)."""
        moment = time.time() if now is None else now
        with _LOCK:
            invites = self._load()
            digest = code_hash(code)
            invite = invites.get(digest)
            if invite is None or not invite.usable(moment):
                raise InviteError("체험 코드가 만료되었습니다.", "INVITE_EXPIRED")
            if invite.projects_created >= invite.max_projects:
                raise InviteError(
                    f"이 체험 코드로 만들 수 있는 프로젝트 {invite.max_projects}개를 모두 사용했습니다.",
                    "TRIAL_PROJECT_LIMIT",
                )
            invite = replace(invite, projects_created=invite.projects_created + 1)
            invites[digest] = invite
            self._save(invites)
            return invite

    def release_project(self, code_id_value: str) -> None:
        """Give a project back after an ASR failure (no partial project is kept)."""
        with _LOCK:
            invites = self._load()
            for digest, invite in invites.items():
                if invite.code_id == code_id_value and invite.projects_created > 0:
                    invites[digest] = replace(invite, projects_created=invite.projects_created - 1)
                    self._save(invites)
                    return
