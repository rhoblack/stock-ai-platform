"""v0.9 Phase A -- In-memory brute force protection for POST /api/auth/login.

Design notes
------------
* **Memory-only.** No DB or cache dependency. State is lost on restart, which
  is acceptable for single-process deployments. Multi-process / distributed
  deployments would need a shared cache (Redis); that is out of scope for v0.9.
* **Composite key.** Failures are tracked per ``(username, source_ip_hash)``
  pair so a lockout on one IP does not block other IPs for the same user.
  Neither username nor IP is stored verbatim in any log or struct -- the
  guard derives its own internal key via SHA256.
* **Plain IP never stored.** The caller passes the already-hashed IP (via
  ``app.auth.security.hash_for_audit``). The guard's internal key is a second
  SHA256 over the composite string, so the original IP is doubly hashed.
* **Thread-safe.** A single ``threading.Lock`` protects the internal dict.
  Under asyncio + uvicorn the GIL provides equivalent protection, but the
  explicit lock keeps behaviour correct if a sync executor is used.
* **Window semantics.** Failures are counted within a rolling window. The
  window resets on the first failure after the window expires, not on each
  request. This is a simple sliding-window approximation.
* **Lockout audit.** Callers are responsible for logging LOCKOUT_REJECTED
  audit entries; the guard raises ``BruteForceLockedError`` and does nothing
  else.  This keeps the guard free of DB / repository dependencies.
"""

from __future__ import annotations

import hashlib
import threading
import time


class BruteForceLockedError(Exception):
    """Raised by ``BruteForceGuard.check_allowed`` when the key is locked.

    The route layer MUST catch this and return a generic 401 that is
    indistinguishable from a wrong-password failure -- no lockout timing
    hint should reach the client.
    """


class BruteForceGuard:
    """Track login failures per (username + source_ip_hash) and enforce lockout.

    Parameters
    ----------
    max_failures:
        Number of failures within ``window_seconds`` that triggers lockout.
    window_seconds:
        Duration of the failure-counting window.
    lockout_seconds:
        How long the key remains locked after ``max_failures`` is reached.
    """

    def __init__(
        self,
        *,
        max_failures: int = 5,
        window_seconds: int = 300,
        lockout_seconds: int = 900,
    ) -> None:
        self.max_failures = max_failures
        self.window_seconds = window_seconds
        self.lockout_seconds = lockout_seconds
        # Key -> (failure_count, window_start_monotonic, locked_until_monotonic)
        self._records: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_key(self, username: str, source_ip_hash: str | None) -> str:
        ip_part = source_ip_hash or "unknown"
        raw = f"{username}:{ip_part}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def _get_record(self, key: str) -> list[float]:
        # [failure_count, window_start, locked_until]
        return self._records.get(key, [0.0, 0.0, 0.0])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_allowed(self, username: str, source_ip_hash: str | None) -> None:
        """Raise ``BruteForceLockedError`` if this key is currently locked.

        Must be called BEFORE the actual credential check so a locked request
        does not reach the DB at all.
        """
        key = self._make_key(username, source_ip_hash)
        now = time.monotonic()
        with self._lock:
            rec = self._get_record(key)
            locked_until = rec[2]
            if locked_until > now:
                raise BruteForceLockedError("Too many login failures. Try again later.")

    def record_failure(self, username: str, source_ip_hash: str | None) -> None:
        """Increment the failure counter; lock the key if threshold is reached."""
        key = self._make_key(username, source_ip_hash)
        now = time.monotonic()
        with self._lock:
            rec = self._get_record(key)
            count, window_start, locked_until = rec[0], rec[1], rec[2]

            # Reset window if it has expired (and not currently locked).
            if locked_until <= now and (now - window_start) > self.window_seconds:
                count = 0.0
                window_start = now

            count += 1
            new_locked_until = locked_until
            if count >= self.max_failures:
                new_locked_until = now + self.lockout_seconds

            self._records[key] = [count, window_start, new_locked_until]

    def record_success(self, username: str, source_ip_hash: str | None) -> None:
        """Clear the failure record on a successful login for this key."""
        key = self._make_key(username, source_ip_hash)
        with self._lock:
            self._records.pop(key, None)

    def is_locked(self, username: str, source_ip_hash: str | None) -> bool:
        """Return ``True`` if the key is currently within a lockout window."""
        key = self._make_key(username, source_ip_hash)
        now = time.monotonic()
        with self._lock:
            rec = self._get_record(key)
            return rec[2] > now

    def reset(self) -> None:
        """Clear all records. Intended for test teardown only."""
        with self._lock:
            self._records.clear()
