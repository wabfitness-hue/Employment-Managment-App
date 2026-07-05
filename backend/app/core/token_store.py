"""
Refresh-token rotation support: tracks consumed refresh-token ids (jti) so a
refresh token can only be used once. On use, the presented token's jti is
recorded in Redis with a TTL matching the token's remaining lifetime; presenting
the same jti again is rejected as a replay.

Fails OPEN if Redis is unavailable (or absent, e.g. under pytest): refresh still
works, it just isn't tracked during the outage — consistent with rate_limit.py.
"""
import logging
import time

import redis

from .config import get_settings

settings = get_settings()
logger = logging.getLogger("token_store")

_client: "redis.Redis | None" = None
_redis_ok = True


def _redis() -> "redis.Redis | None":
    global _client, _redis_ok
    if not _redis_ok:
        return None
    if _client is None:
        try:
            _client = redis.Redis.from_url(
                settings.REDIS_URL, decode_responses=True,
                socket_connect_timeout=2, socket_timeout=2,
            )
            _client.ping()
        except Exception as exc:
            logger.warning("token_store: Redis unavailable, refresh rotation disabled: %s", exc)
            _redis_ok = False
            _client = None
    return _client


def consume_refresh_jti(jti: str, exp: "int | float | None") -> bool:
    """
    Atomically mark a refresh-token jti as used.

    Returns True if this is the first use (proceed), False if it was already used
    (reject as replay). Fails open (returns True) when Redis is unavailable.
    """
    if not jti:
        return True  # legacy token without a jti — nothing to track
    r = _redis()
    if r is None:
        return True  # fail open
    ttl = int((exp - time.time())) if exp else settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400
    ttl = max(ttl, 1)
    try:
        # SET NX returns True only if the key did not already exist.
        was_new = r.set(f"refresh:used:{jti}", "1", nx=True, ex=ttl)
        return bool(was_new)
    except redis.RedisError as exc:
        logger.warning("token_store: consume_refresh_jti Redis error, allowing: %s", exc)
        return True  # fail open
