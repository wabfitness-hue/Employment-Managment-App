"""
Encrypted token store for Outlook OAuth credentials.

Tokens are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256).
The encryption key is derived from the app's SECRET_KEY so no separate
key needs to be managed — rotating SECRET_KEY invalidates stored tokens
and forces re-auth, which is the correct behaviour.
"""
import base64
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

from cryptography.fernet import Fernet
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.outlook_token import OutlookToken

settings = get_settings()


def _fernet() -> Fernet:
    """Derive a 32-byte Fernet key from SECRET_KEY."""
    raw = settings.SECRET_KEY.encode()
    key_bytes = hashlib.sha256(raw).digest()   # 32 bytes
    b64_key = base64.urlsafe_b64encode(key_bytes)
    return Fernet(b64_key)


def _encrypt(plaintext: str) -> str:
    return _fernet().encrypt(plaintext.encode()).decode()


def _decrypt(ciphertext: str) -> str:
    return _fernet().decrypt(ciphertext.encode()).decode()


# ── Public API ────────────────────────────────────────────────────────────────

def save_tokens(
    db: Session,
    owner_id: str,
    access_token: str,
    refresh_token: Optional[str],
    expires_in: int,
    outlook_email: Optional[str],
    scope: Optional[str],
) -> OutlookToken:
    """Create or update the Outlook token record for an owner."""
    import uuid
    uid = uuid.UUID(owner_id)

    record = db.query(OutlookToken).filter(OutlookToken.owner_id == uid).first()
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    if record:
        record.access_token_enc = _encrypt(access_token)
        record.refresh_token_enc = _encrypt(refresh_token) if refresh_token else None
        record.token_expires_at = expires_at
        record.outlook_email = outlook_email
        record.scope = scope
    else:
        record = OutlookToken(
            owner_id=uid,
            access_token_enc=_encrypt(access_token),
            refresh_token_enc=_encrypt(refresh_token) if refresh_token else None,
            token_expires_at=expires_at,
            outlook_email=outlook_email,
            scope=scope,
        )
        db.add(record)

    db.flush()
    return record


def get_access_token(db: Session, owner_id: str) -> Optional[str]:
    """
    Return the current access token for an owner, refreshing it if expired.
    Returns None if no token is stored or refresh fails.
    """
    import uuid
    uid = uuid.UUID(owner_id)
    record = db.query(OutlookToken).filter(OutlookToken.owner_id == uid).first()
    if not record:
        return None

    now = datetime.now(timezone.utc)
    expires_at = record.token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    # Token still valid (with 2-min buffer)
    if expires_at and now < expires_at - timedelta(minutes=2):
        return _decrypt(record.access_token_enc)

    # Try refresh
    if record.refresh_token_enc:
        try:
            refresh_token = _decrypt(record.refresh_token_enc)
            new_tokens = _refresh_access_token(refresh_token)
            record.access_token_enc = _encrypt(new_tokens["access_token"])
            if new_tokens.get("refresh_token"):
                record.refresh_token_enc = _encrypt(new_tokens["refresh_token"])
            record.token_expires_at = (
                now + timedelta(seconds=new_tokens.get("expires_in", 3600))
            )
            db.flush()
            return new_tokens["access_token"]
        except Exception as exc:
            logger.warning("Outlook token refresh failed for owner %s: %s", owner_id, exc)
            return None

    return None


def delete_tokens(db: Session, owner_id: str) -> bool:
    import uuid
    uid = uuid.UUID(owner_id)
    record = db.query(OutlookToken).filter(OutlookToken.owner_id == uid).first()
    if record:
        db.delete(record)
        db.flush()
        return True
    return False


def connection_status(db: Session, owner_id: str) -> dict:
    import uuid
    uid = uuid.UUID(owner_id)
    record = db.query(OutlookToken).filter(OutlookToken.owner_id == uid).first()
    if not record:
        return {"connected": False}

    now = datetime.now(timezone.utc)
    expires_at = record.token_expires_at
    if expires_at and expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    return {
        "connected": True,
        "outlook_email": record.outlook_email,
        "token_expires_at": expires_at.isoformat() if expires_at else None,
        "token_expired": (expires_at is None or now >= expires_at),
        "can_refresh": record.refresh_token_enc is not None,
    }


def _refresh_access_token(refresh_token: str) -> dict:
    """Call the Microsoft token endpoint to exchange a refresh token."""
    import httpx

    data = {
        "client_id": settings.MS_CLIENT_ID,
        "client_secret": settings.MS_CLIENT_SECRET,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "scope": "offline_access Mail.ReadWrite",
    }
    resp = httpx.post(
        "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        data=data,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()
