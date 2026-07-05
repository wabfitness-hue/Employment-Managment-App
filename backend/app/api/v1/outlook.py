"""
Outlook / Microsoft Graph API routes:

  GET  /outlook/connect           — generate OAuth authorization URL
  GET  /outlook/callback          — handle OAuth callback, store tokens
  GET  /outlook/status            — check connection status
  DELETE /outlook/disconnect      — revoke and delete stored tokens
  POST /outlook/scan              — scan HR-Intake folder for photo emails
  GET  /outlook/scan/results/{job_id} — get scan results
"""
import secrets
from typing import Optional

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

# In-memory PKCE/state store (single-user app — one pending OAuth at a time)
_pending_state: dict[str, str] = {}   # state → owner_id


from app.core.request_ip import client_ip as _client_ip


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
    _pending_state[state] = str(current_user.id)

    params = (
        f"client_id={settings.MS_CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={settings.MS_REDIRECT_URI}"
        f"&response_mode=query"
        f"&scope={GRAPH_SCOPES.replace(' ', '%20')}"
        f"&state={state}"
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

    owner_id = _pending_state.pop(state, None)
    if not owner_id:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state. Please reconnect.")

    # Exchange code for tokens
    import httpx
    token_data = {
        "client_id": settings.MS_CLIENT_ID,
        "client_secret": settings.MS_CLIENT_SECRET,
        "code": code,
        "redirect_uri": settings.MS_REDIRECT_URI,
        "grant_type": "authorization_code",
        "scope": GRAPH_SCOPES,
    }
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.post(TOKEN_URL, data=token_data, timeout=15)
            resp.raise_for_status()
            tokens = resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Token exchange failed: {exc}")

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

    # Redirect to the frontend settings page
    return RedirectResponse(url="http://localhost:3000/settings/outlook?connected=true")


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
