"""
Password hashing, JWT token creation/verification, MFA TOTP handling.
All cryptographic operations live here — nowhere else.
"""
import pyotp
import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import get_settings

settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Passwords ────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def password_meets_policy(plain: str) -> tuple[bool, str]:
    """Returns (ok, reason). Reason is empty string when ok."""
    if len(plain) < 12:
        return False, "Password must be at least 12 characters."
    if not any(c.isupper() for c in plain):
        return False, "Password must contain at least one uppercase letter."
    if not any(c.islower() for c in plain):
        return False, "Password must contain at least one lowercase letter."
    if not any(c.isdigit() for c in plain):
        return False, "Password must contain at least one number."
    if not any(c in "!@#$%^&*()_+-=[]{}|;':\",./<>?" for c in plain):
        return False, "Password must contain at least one special character."
    return True, ""


# ── JWT Tokens ───────────────────────────────────────────────────────────────

def _make_token(data: dict, expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    payload["iat"] = datetime.now(timezone.utc)
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: str, role: str, mfa_verified: bool = False) -> str:
    return _make_token(
        {"sub": user_id, "role": role, "mfa": mfa_verified, "type": "access"},
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: str) -> str:
    # jti (unique token id) lets the refresh endpoint enforce one-time use /
    # rotation — a used or replayed refresh token is rejected.
    return _make_token(
        {"sub": user_id, "type": "refresh", "jti": secrets.token_urlsafe(16)},
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    """Raises JWTError if invalid or expired."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ── MFA / TOTP ───────────────────────────────────────────────────────────────

def generate_mfa_secret() -> str:
    return pyotp.random_base32()


def get_mfa_provisioning_uri(secret: str, email: str) -> str:
    totp = pyotp.TOTP(secret)
    return totp.provisioning_uri(name=email, issuer_name=settings.MFA_ISSUER)


def verify_mfa_token(secret: str, token: str) -> bool:
    totp = pyotp.TOTP(secret)
    return totp.verify(token, valid_window=2)


# ── Secure random ────────────────────────────────────────────────────────────

def generate_secure_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)
