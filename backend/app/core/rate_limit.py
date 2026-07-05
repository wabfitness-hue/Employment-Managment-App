"""
In-memory rate limiting for login endpoint.
Uses a simple dictionary store — Redis replaces this in production Docker build.
Tracks failed attempts per IP and per email, locks out after MAX_LOGIN_ATTEMPTS.
"""
import time
from collections import defaultdict
from threading import Lock
from .config import get_settings

settings = get_settings()

_lock = Lock()
_attempts: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}


def _key(ip: str, email: str) -> str:
    return f"{ip}:{email.lower()}"


def _now() -> float:
    return time.time()


def _window() -> float:
    return settings.LOCKOUT_MINUTES * 60


def is_locked_out(ip: str, email: str) -> bool:
    k = _key(ip, email)
    with _lock:
        locked_until = _lockouts.get(k)
        if locked_until and _now() < locked_until:
            return True
        if locked_until:
            del _lockouts[k]
            _attempts[k] = []
        return False


def seconds_until_unlock(ip: str, email: str) -> int:
    k = _key(ip, email)
    with _lock:
        locked_until = _lockouts.get(k, 0)
        remaining = locked_until - _now()
        return max(0, int(remaining))


def record_failed_attempt(ip: str, email: str) -> int:
    """Records a failure. Returns current failure count."""
    k = _key(ip, email)
    now = _now()
    window = _window()
    with _lock:
        _attempts[k] = [t for t in _attempts[k] if now - t < window]
        _attempts[k].append(now)
        count = len(_attempts[k])
        if count >= settings.MAX_LOGIN_ATTEMPTS:
            _lockouts[k] = now + window
        return count


def clear_attempts(ip: str, email: str) -> None:
    k = _key(ip, email)
    with _lock:
        _attempts.pop(k, None)
        _lockouts.pop(k, None)
