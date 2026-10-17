"""Brute-force protection for invite-code entry (INT-002). In memory, one process.

Every wrong invite code — typed on the consent page or presented in the trial
cookie — counts as a failed attempt:

- **per client** (IP): after ``ip_free_failures`` failures the client is locked
  out with exponential backoff (``ip_base_seconds`` x 2^(extra failures)),
  capped at ``ip_max_seconds``; a correct code clears its record;
- **global**: more than ``global_max_failures`` failures from all clients within
  ``global_window_seconds`` locks code entry for everyone for
  ``global_lock_seconds`` (a distributed guess cannot outrun the per-IP limit).

While locked, a code is not even looked up, so a locked client learns nothing.
The client key is the socket peer address; behind a trusted tunnel / reverse
proxy (``AIE_WEB_TRUST_PROXY=1``) it is ``CF-Connecting-IP`` or the first
``X-Forwarded-For`` hop, because every request would otherwise come from the
local proxy. State is lost on restart (acceptable for a short founder-led
trial); a multi-process deployment would need a shared store.
"""

import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass

from starlette.requests import Request

from .store import Settings

MAX_TRACKED_CLIENTS = 10_000


@dataclass
class _Client:
    failures: int = 0
    locked_until: float = 0.0
    last_seen: float = 0.0


@dataclass(frozen=True)
class LimitPolicy:
    ip_free_failures: int = 5
    ip_base_seconds: float = 30.0
    ip_max_seconds: float = 3600.0
    global_max_failures: int = 50
    global_window_seconds: float = 600.0
    global_lock_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.ip_free_failures < 1 or self.global_max_failures < 1:
            raise ValueError("Failure limits must be positive")
        if min(self.ip_base_seconds, self.ip_max_seconds, self.global_lock_seconds) <= 0:
            raise ValueError("Lock durations must be positive")


class AttemptLimiter:
    def __init__(
        self, policy: LimitPolicy | None = None, clock: Callable[[], float] = time.time
    ) -> None:
        self.policy = policy or LimitPolicy()
        self._clock = clock
        self._clients: dict[str, _Client] = {}
        self._global: deque[float] = deque()
        self._global_locked_until = 0.0
        self._lock = threading.Lock()

    def retry_after(self, key: str) -> float:
        """Seconds until ``key`` may try a code again (0 = allowed now)."""
        now = self._clock()
        with self._lock:
            wait = max(0.0, self._global_locked_until - now)
            client = self._clients.get(key)
            if client is not None:
                wait = max(wait, client.locked_until - now)
            return wait

    def failure(self, key: str) -> float:
        """Record a wrong code; returns the resulting lockout in seconds (0 = none)."""
        now = self._clock()
        policy = self.policy
        with self._lock:
            self._prune(now)
            client = self._clients.setdefault(key, _Client())
            client.failures += 1
            client.last_seen = now
            extra = client.failures - policy.ip_free_failures
            if extra >= 0:
                backoff = policy.ip_base_seconds * (2 ** min(extra, 20))
                client.locked_until = now + min(policy.ip_max_seconds, backoff)
            self._global.append(now)
            while self._global and self._global[0] <= now - policy.global_window_seconds:
                self._global.popleft()
            if len(self._global) >= policy.global_max_failures:
                self._global_locked_until = now + policy.global_lock_seconds
                self._global.clear()
            return max(0.0, client.locked_until - now, self._global_locked_until - now)

    def success(self, key: str) -> None:
        with self._lock:
            self._clients.pop(key, None)

    def _prune(self, now: float) -> None:
        if len(self._clients) < MAX_TRACKED_CLIENTS:
            return
        horizon = now - 2 * self.policy.ip_max_seconds
        for key in [k for k, c in self._clients.items() if c.last_seen < horizon]:
            del self._clients[key]
        if len(self._clients) >= MAX_TRACKED_CLIENTS:  # still full: drop the oldest
            oldest = sorted(self._clients, key=lambda k: self._clients[k].last_seen)
            for key in oldest[: len(oldest) // 2]:
                del self._clients[key]


def client_key(request: Request, settings: Settings) -> str:
    if settings.trust_proxy:
        forwarded = request.headers.get("cf-connecting-ip") or request.headers.get(
            "x-forwarded-for", ""
        )
        first = forwarded.split(",")[0].strip()
        if first:
            return first[:64]
    return request.client.host if request.client is not None else "unknown"
