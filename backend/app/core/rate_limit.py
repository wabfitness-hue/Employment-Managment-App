"""
Rate limiting for the login endpoint.

Tracks failed login attempts per (IP, email) and locks the pair out after
MAX_LOGIN_ATTEMPTS within a sliding LOCKOUT_MINUTES window.

Primary store is Redis, so the limit is shared across all uvicorn workers — an
in-memory dict alone would be per-process, roughly doubling the effective threshold
with `--workers 2`. If Redis is unreachable (or absent, e.g. under pytest), the code
falls back to a per-process in-memory store, which still enforces the limit within a
worker rather than disabling protection entirely.
"""
import logging
import time
from collections import defaultdict
from threading import Lock

import redis

from .config import get_settings

settings = get_settings()
logger = logging.getLogger("rate_limit")

# ── In-memory fallback (also used by the test suite, which has no Redis) ─────────
_lock = Lock()
_attempts: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}

# ── Redis client (lazily created; connection pool is thread-safe) ───────────────
_client: "redis.Redis | None" = None
_redis_ok = True  # flips to False after a failure so we stop retrying every call


def _redis() -> "redis.Redis | None":
    global _client, _redis_ok
    if not _redis_ok:
        return None
    if _client is None:
        try:
            _client = redis.Redis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            _client.ping()
        except Exception as exc:
            logger.warning("rate_limit: Redis unavailable, using in-memory fallback: %s", exc)
            _redis_ok = False
            _client = None
    return _client


def _key(ip: str, email: str) -> str:
    return f"{ip}:{email.lower()}"


def _window() -> int:
    return settings.LOCKOUT_MINUTES * 60


# ── Public API ──────────────────────────────────────────────────────────────────

def is_locked_out(ip: str, email: str) -> bool:
    r = _redis()
    if r is not None:
        try:
            return bool(r.exists(f"login:lockout:{_key(ip, email)}"))
        except redis.RedisError as exc:
            logger.warning("rate_limit: is_locked_out Redis error, falling back: %s", exc)
    return _mem_is_locked_out(ip, email)


def seconds_until_unlock(ip: str, email: str) -> int:
    r = _redis()
    if r is not None:
        try:
            ttl = r.ttl(f"login:lockout:{_key(ip, email)}")
            return ttl if ttl and ttl > 0 else 0
        except redis.RedisError as exc:
            logger.warning("rate_limit: seconds_until_unlock Redis error, falling back: %s", exc)
    return _mem_seconds_until_unlock(ip, email)


def record_failed_attempt(ip: str, email: str) -> int:
    """Records a failure in a sliding window. Returns the current failure count."""
    r = _redis()
    if r is not None:
        try:
            now = time.time()
            window = _window()
            akey = f"login:attempts:{_key(ip, email)}"
            pipe = r.pipeline()
            pipe.zremrangebyscore(akey, 0, now - window)  # evict entries outside window
            pipe.zadd(akey, {f"{now}": now})              # record this attempt
            pipe.zcard(akey)                              # count within window
            pipe.expire(akey, window)                     # auto-clean idle keys
            count = int(pipe.execute()[2])
            if count >= settings.MAX_LOGIN_ATTEMPTS:
                r.set(f"login:lockout:{_key(ip, email)}", str(now + window), ex=window)
            return count
        except redis.RedisError as exc:
            logger.warning("rate_limit: record_failed_attempt Redis error, falling back: %s", exc)
    return _mem_record_failed_attempt(ip, email)


def clear_attempts(ip: str, email: str) -> None:
    r = _redis()
    if r is not None:
        try:
            r.delete(f"login:attempts:{_key(ip, email)}", f"login:lockout:{_key(ip, email)}")
            _mem_clear(ip, email)  # clear any stale fallback state too
            return
        except redis.RedisError as exc:
            logger.warning("rate_limit: clear_attempts Redis error, falling back: %s", exc)
    _mem_clear(ip, email)


# ── In-memory fallback implementation ───────────────────────────────────────────

def _mem_is_locked_out(ip: str, email: str) -> bool:
    k = _key(ip, email)
    with _lock:
        locked_until = _lockouts.get(k)
        if locked_until and time.time() < locked_until:
            return True
        if locked_until:
            del _lockouts[k]
            _attempts[k] = []
        return False


def _mem_seconds_until_unlock(ip: str, email: str) -> int:
    k = _key(ip, email)
    with _lock:
        remaining = _lockouts.get(k, 0) - time.time()
        return max(0, int(remaining))


def _mem_record_failed_attempt(ip: str, email: str) -> int:
    k = _key(ip, email)
    now = time.time()
    window = _window()
    with _lock:
        _attempts[k] = [t for t in _attempts[k] if now - t < window]
        _attempts[k].append(now)
        count = len(_attempts[k])
        if count >= settings.MAX_LOGIN_ATTEMPTS:
            _lockouts[k] = now + window
        return count


def _mem_clear(ip: str, email: str) -> None:
    k = _key(ip, email)
    with _lock:
        _attempts.pop(k, None)
        _lockouts.pop(k, None)
