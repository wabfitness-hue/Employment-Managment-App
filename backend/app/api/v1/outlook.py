"""
Outlook / Microsoft Graph API routes:

  GET  /outlook/connect           — generate OAuth authorization URL
  GET  /outlook/callback          — handle OAuth callback, store tokens
  GET  /outlook/status            — check connection status
  DELETE /outlook/disconnect      — revoke and delete stored tokens
  POST /outlook/scan              — scan HR-Intake folder for photo emails
  GET  /outlook/scan/results/{job_id} — get scan results
"""
import base64
import hashlib
import json
import logging
import secrets
from typing import Optional

import redis as _redis_lib
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_user import AppUser
from app.core.dependencies import require_super_admin, require_hr_or_above
from app.core.config import get_settings
from app.core.audit import log_action
from app.services.outlook.token_store import (
    save_tokens, get_access_token, delete_tokens, connection_status
)
from app.services.photos.outlook_extractor import process_intake_emails

router = APIRouter(prefix="/outlook", tags=["outlook"])
settings = get_settings()

GRAPH_SCOPES = "offline_access Mail.ReadWrite User.Read"
AUTH_URL_BASE = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
TOKEN_URL = "https://login.microsoftonline.com/common/oauth2/v2.0/token"

logger = logging.getLogger("outlook")

from app.core.request_ip import client_ip as _client_ip

# ── OAuth state store ─────────────────────────────────────────────────────────
# Holds {owner_id, code_verifier} per state so the CSRF `state` and the PKCE
# verifier survive the round-trip to Microsoft. Uses Redis when available (so it
# works across multiple web workers in the full-stack setup); falls back to a
# per-process in-memory store when Redis is absent — correct for the single-
# process desktop build, and safe otherwise since OAuth state is short-lived.
_STATE_TTL = 600  # 10 minutes
_mem_state: dict[str, tuple[float, str]] = {}  # state -> (expires_at, json payload)


def _oauth_redis() -> "_redis_lib.Redis | None":
    try:
        r = _redis_lib.Redis.from_url(
            settings.REDIS_URL, decode_responses=True,
            socket_connect_timeout=2, socket_timeout=2,
        )
        r.ping()
        return r
    except Exception:
        return None


def _store_oauth_state(state: str, owner_id: str, verifier: str) -> None:
    payload = json.dumps({"owner_id": owner_id, "verifier": verifier})
    r = _oauth_redis()
    if r is not None:
        r.set(f"oauth:state:{state}", payload, ex=_STATE_TTL, nx=True)
        return
    # in-memory fallback (single process)
    import time
    _mem_state[state] = (time.time() + _STATE_TTL, payload)


def _pop_oauth_state(state: str) -> Optional[dict]:
    r = _oauth_redis()
    if r is not None:
        key = f"oauth:state:{state}"
        val = r.get(key)
        if val is None:
            return None
        r.delete(key)  # single-use
        return json.loads(val)
    # in-memory fallback
    import time
    entry = _mem_state.pop(state, None)
    if entry is None:
        return None
    expires_at, payload = entry
    if time.time() > expires_at:
        return None
    return json.loads(payload)


def _pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = secrets.token_urlsafe(64)  # 43–128 chars per RFC 7636
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).decode().rstrip("=")
    return verifier, challenge


# ── Connect ───────────────────────────────────────────────────────────────────

@router.get("/connect")
def outlook_connect(
    current_user: AppUser = Depends(require_super_admin),
):
    """
    Generate and return the Microsoft OAuth authorization URL.
    The frontend opens this URL in a new tab/window. Microsoft redirects
    back to /outlook/callback with a code.
    """
    if not settings.MS_CLIENT_ID:
        raise HTTPException(
            status_code=503,
            detail="Microsoft OAuth is not configured. Set MS_CLIENT_ID and MS_CLIENT_SECRET in .env",
        )

    state = secrets.token_urlsafe(32)
    verifier, challenge = _pkce_pair()
    try:
        _store_oauth_state(state, str(current_user.id), verifier)
    except _redis_lib.RedisError as exc:
        logger.warning("outlook_connect: could not store OAuth state: %s", exc)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please try again.")

    params = (
        f"client_id={settings.MS_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.MS_REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope={GRAPH_SCOPES.replace(' ', '%20')}"
        f"&state={state}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
        f"&prompt=select_account"
    )
    auth_url = f"{AUTH_URL_BASE}?{params}"

    return {
        "auth_url": auth_url,
        "message": "Open auth_url in a browser to authorize the Outlook connection.",
    }


# ── Callback ──────────────────────────────────────────────────────────────────

@router.get("/callback")
async def outlook_callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """
    Microsoft redirects here after the user authorises.
    Exchanges the code for tokens and stores them encrypted.
    """
    if error:
        raise HTTPException(
            status_code=400,
            detail=f"OAuth error: {error} — {error_description}",
        )

    if not code or not state:
        raise HTTPException(status_code=400, detail="Missing code or state parameter.")

    try:
        pending = _pop_oauth_state(state)
    except _redis_lib.RedisError as exc:
        logger.warning("outlook_callback: could not read OAuth state: %s", exc)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable. Please reconnect.")
    if not pending:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state. Please reconnect.")
    owner_id = pending["owner_id"]
    code_verifier = pending["verifier"]

    # Exchange code for tokens (PKCE: send the code_verifier)
    import httpx
    token_data = {
        "client_id": settings.MS_CLIENT_ID,
        "client_secret": settings.MS_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.MS_REDIRECT_URI,
        "grant_type": "authorization_code",
        "scope": GRAPH_SCOPES,
        "code_verifier": code_verifier,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(TOKEN_URL, data=token_data, timeout=15)
            resp.raise_for_status()
            tokens = resp.json()
    except Exception as exc:
        logger.warning("outlook_callback: token exchange failed: %s", exc)
        raise HTTPException(status_code=502, detail="Token exchange with Microsoft failed. Please reconnect.")

    # Fetch the user's Outlook email address
    outlook_email = None
    try:
        async with httpx.AsyncClient() as client:
            profile = await client.get(
                "https://graph.microsoft.com/v1.0/me",
                headers={"Authorization": f"Bearer {tokens['access_token']}"},
                timeout=10,
            )
            outlook_email = profile.json().get("mail") or profile.json().get("userPrincipalName")
    except Exception:
        pass

    save_tokens(
        db=db,
        owner_id=owner_id,
        access_token=tokens["access_token"],
        refresh_token=tokens.get("refresh_token"),
        expires_in=tokens.get("expires_in", 3600),
        outlook_email=outlook_email,
        scope=tokens.get("scope"),
    )
    db.commit()

    log_action(db, "outlook_connected", user_id=owner_id,
               detail={"outlook_email": outlook_email})
    db.commit()

    # Redirect back to the frontend settings page (same origin, served by Nginx)
    return RedirectResponse(url="/settings?outlook=connected")


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def outlook_status(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    return connection_status(db, str(current_user.id))


# ── Disconnect ────────────────────────────────────────────────────────────────

@router.delete("/disconnect")
def outlook_disconnect(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    deleted = delete_tokens(db, str(current_user.id))
    if not deleted:
        raise HTTPException(status_code=404, detail="No Outlook connection found.")
    db.commit()
    log_action(db, "outlook_disconnected", user_id=str(current_user.id),
               ip_address=_client_ip(request))
    db.commit()
    return {"disconnected": True}


# ── Scan inbox ────────────────────────────────────────────────────────────────

@router.post("/scan")
async def scan_intake_inbox(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    """
    Scan the HR-Intake folder for unread emails with photo attachments.
    Uses the stored access token of the super_admin who connected Outlook.
    Returns a list of results — HR reviews and the photos are already saved.
    """
    # Use the token of whoever owns the connection (super_admin)
    from app.models.outlook_token import OutlookToken
    token_record = db.query(OutlookToken).first()
    if not token_record:
        raise HTTPException(
            status_code=503,
            detail="Outlook is not connected. A super_admin must authorise via /outlook/connect first.",
        )

    access_token = get_access_token(db, str(token_record.owner_id))
    if not access_token:
        raise HTTPException(
            status_code=503,
            detail="Outlook token has expired and could not be refreshed. Please reconnect.",
        )

    results = await process_intake_emails(db, access_token)
    db.commit()

    saved_count = sum(1 for r in results if r.get("photo_saved"))
    unmatched_count = sum(1 for r in results if r.get("status") == "unmatched")

    log_action(
        db, "outlook_scan_completed",
        user_id=str(current_user.id),
        detail={
            "emails_processed": len(results),
            "photos_saved": saved_count,
            "unmatched": unmatched_count,
        },
        ip_address=_client_ip(request),
    )
    db.commit()

    return {
        "emails_processed": len(results),
        "photos_saved": saved_count,
        "unmatched": unmatched_count,
        "results": results,
    }
