"""
Shared helper for determining the real client IP behind a reverse proxy.

X-Forwarded-For is only trusted when the direct TCP peer is a configured trusted
proxy (TRUSTED_PROXY_IPS, CIDR-aware). Otherwise the header is ignored, so an
untrusted client cannot spoof its IP to bypass rate limiting or forge audit logs.
"""
from fastapi import Request

from .config import get_settings


def client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    if get_settings().is_trusted_proxy(direct_ip):
        forwarded = request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return direct_ip
