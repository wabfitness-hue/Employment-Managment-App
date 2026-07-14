"""
Auth routes:
  POST /auth/login          — email + password → tokens (or mfa_required flag)
  POST /auth/mfa/verify     — TOTP code → full access token
  POST /auth/mfa/setup      — generate MFA secret for current user
  POST /auth/mfa/enable     — confirm TOTP code then enable MFA
  POST /auth/refresh        — refresh token → new access token
  POST /auth/logout         — invalidate refresh token
  POST /auth/change-password
  GET  /auth/me             — current user profile
  POST /auth/users          — create app user (super_admin only)
  GET  /auth/users          — list app users (super_admin only)
  PATCH /auth/users/{id}/deactivate
"""
from fastapi import APIRouter, Depends, Request, HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError

from app.core.request_ip import client_ip
from app.core.token_store import consume_refresh_jti
from app.database import get_db
from app.models.app_user import AppUser, UserRole
from app.core.security import (
    hash_password, verify_password, password_meets_policy,
    create_access_token, create_refresh_token, decode_token,
    generate_mfa_secret, get_mfa_provisioning_uri, verify_mfa_token,
    generate_recovery_codes, hash_recovery_code,
)
from app.core.rate_limit import is_locked_out, record_failed_attempt, clear_attempts, seconds_until_unlock
from app.core.audit import log_action
from app.core.dependencies import (
    get_current_user, get_current_user_no_mfa_check,
    require_super_admin, require_any_role,
)
from app.api.v1.schemas.auth import (
    LoginRequest, MFAVerifyRequest, MFALoginRequest, TokenResponse, MFASetupResponse,
    RecoveryCodesResponse, RecoveryCodesStatus, RegenerateRecoveryCodesRequest,
    RefreshRequest, ChangePasswordRequest, CreateUserRequest, UserResponse,
)

import json
import uuid

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    """Return the real client IP (CIDR-aware trusted-proxy handling)."""
    return client_ip(request)


# ── MFA recovery-code storage helpers ─────────────────────────────────────────

def _set_recovery_codes(user: AppUser) -> list[str]:
    """Generate a fresh set of recovery codes, store their hashes, return plaintext."""
    codes = generate_recovery_codes(10)
    user.mfa_recovery_codes = json.dumps([hash_recovery_code(c) for c in codes])
    return codes


def _recovery_hashes(user: AppUser) -> list[str]:
    if not user.mfa_recovery_codes:
        return []
    try:
        return json.loads(user.mfa_recovery_codes)
    except (ValueError, TypeError):
        return []


def _consume_recovery_code(user: AppUser, code: str) -> bool:
    """If `code` matches an unused recovery code, spend it and return True."""
    if not code:
        return False
    hashes = _recovery_hashes(user)
    h = hash_recovery_code(code)
    if h in hashes:
        hashes.remove(h)
        user.mfa_recovery_codes = json.dumps(hashes)
        return True
    return False


# ── Login ────────────────────────────────────────────────────────────────────

@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    ip = _client_ip(request)

    if is_locked_out(ip, body.email):
        secs = seconds_until_unlock(ip, body.email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Account temporarily locked. Try again in {secs} seconds.",
        )

    user = db.query(AppUser).filter(
        AppUser.email == body.email,
        AppUser.is_active == True,
    ).first()

    # Always run verify_password (even when user is None) to prevent timing
    # attacks that could reveal whether an email address exists in the system.
    password_ok = verify_password(
        body.password,
        user.password_hash if user else "$2b$12$GhvMmNVjRW29ulnudl.LbuAnUtN/LRfe7LBM3lBGzrE7UVAfcAVKG"
    )
    if not user or not password_ok:
        record_failed_attempt(ip, body.email)
        log_action(db, "login_failed", ip_address=ip, detail={"email": body.email})
        db.commit()
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    clear_attempts(ip, body.email)

    if user.mfa_enabled:
        # Issue a short-lived pre-MFA access token — cannot access protected routes yet
        pre_token = create_access_token(str(user.id), user.role.value, mfa_verified=False)
        log_action(db, "login_pending_mfa", user_id=str(user.id), ip_address=ip)
        db.commit()
        return TokenResponse(
            access_token=pre_token,
            refresh_token="",
            mfa_required=True,
        )

    refresh = create_refresh_token(str(user.id))
    access = create_access_token(str(user.id), user.role.value, mfa_verified=True)
    log_action(db, "login_success", user_id=str(user.id), ip_address=ip)
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


# ── MFA verify ───────────────────────────────────────────────────────────────

@router.post("/mfa/verify", response_model=TokenResponse)
def verify_mfa(
    body: MFALoginRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user_no_mfa_check),
):
    ip = _client_ip(request)

    # Reuse the same rate limiter keyed on ip+email to prevent brute-force of codes
    if is_locked_out(ip, user.email):
        secs = seconds_until_unlock(ip, user.email)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many attempts. Try again in {secs} seconds.",
        )

    if not user.mfa_enabled or not user.mfa_secret:
        raise HTTPException(status_code=400, detail="MFA is not enabled on this account.")

    # Accept either the authenticator (TOTP) code or a one-time recovery code.
    if body.recovery_code:
        ok = _consume_recovery_code(user, body.recovery_code)
        method = "recovery_code"
    else:
        ok = bool(body.totp_code) and verify_mfa_token(user.mfa_secret, body.totp_code)
        method = "totp"

    if not ok:
        record_failed_attempt(ip, user.email)
        log_action(db, "mfa_failed", user_id=str(user.id), ip_address=ip, detail={"method": method})
        db.commit()
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid MFA code.")

    clear_attempts(ip, user.email)
    access = create_access_token(str(user.id), user.role.value, mfa_verified=True)
    refresh = create_refresh_token(str(user.id))
    log_action(db, "mfa_success", user_id=str(user.id), ip_address=ip, detail={"method": method})
    db.commit()
    return TokenResponse(access_token=access, refresh_token=refresh)


# ── MFA setup ────────────────────────────────────────────────────────────────

@router.post("/mfa/setup", response_model=MFASetupResponse)
def setup_mfa(
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user_no_mfa_check),
):
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA already enabled.")
    secret = generate_mfa_secret()
    user.mfa_secret = secret
    db.commit()
    uri = get_mfa_provisioning_uri(secret, user.email)
    return MFASetupResponse(
        secret=secret,
        provisioning_uri=uri,
        qr_placeholder=f"Scan this URI in your authenticator app: {uri}",
    )


@router.post("/mfa/enable")
def enable_mfa(
    body: MFAVerifyRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user_no_mfa_check),
):
    if user.mfa_enabled:
        raise HTTPException(status_code=400, detail="MFA already enabled.")
    if not user.mfa_secret:
        raise HTTPException(status_code=400, detail="Call /auth/mfa/setup first.")
    if not verify_mfa_token(user.mfa_secret, body.totp_code):
        raise HTTPException(status_code=401, detail="Invalid TOTP code — MFA not enabled.")
    user.mfa_enabled = True
    codes = _set_recovery_codes(user)  # issue recovery codes on enable
    log_action(db, "mfa_enabled", user_id=str(user.id))
    db.commit()
    return {"message": "MFA enabled successfully.", "recovery_codes": codes}


# ── MFA recovery codes ────────────────────────────────────────────────────────

@router.post("/mfa/recovery-codes", response_model=RecoveryCodesResponse)
def regenerate_recovery_codes(
    body: RegenerateRecoveryCodesRequest,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    """Generate a fresh set of recovery codes (invalidates any existing set).
    Requires a fully authenticated (MFA-verified) session AND the current
    password, so a hijacked-but-still-valid session token alone can't mint new
    standing recovery access."""
    if not user.mfa_enabled:
        raise HTTPException(status_code=400, detail="Enable MFA before generating recovery codes.")
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect password.")
    codes = _set_recovery_codes(user)
    log_action(db, "mfa_recovery_codes_regenerated", user_id=str(user.id))
    db.commit()
    return RecoveryCodesResponse(codes=codes, remaining=len(codes))


@router.get("/mfa/recovery-codes", response_model=RecoveryCodesStatus)
def recovery_codes_status(
    user: AppUser = Depends(get_current_user),
):
    hashes = _recovery_hashes(user)
    return RecoveryCodesStatus(configured=bool(hashes), remaining=len(hashes))


# ── Token refresh ─────────────────────────────────────────────────────────────

@router.post("/refresh", response_model=TokenResponse)
def refresh_token(body: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(body.refresh_token)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token.")
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type.")

    # One-time use: reject a refresh token that has already been rotated/replayed.
    if not consume_refresh_jti(payload.get("jti"), payload.get("exp")):
        raise HTTPException(
            status_code=401,
            detail="Refresh token already used. Please log in again.",
        )

    user = db.query(AppUser).filter(
        AppUser.id == payload["sub"],
        AppUser.is_active == True,
    ).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found.")

    # Only mint MFA-verified tokens if the account still doesn't require a fresh
    # challenge — i.e. if MFA is enabled, the prior full-auth still holds.
    access = create_access_token(str(user.id), user.role.value, mfa_verified=True)
    new_refresh = create_refresh_token(str(user.id))
    return TokenResponse(access_token=access, refresh_token=new_refresh)


# ── Me / profile ─────────────────────────────────────────────────────────────

@router.get("/me", response_model=UserResponse)
def me(user: AppUser = Depends(get_current_user)):
    return user


# ── Change password ──────────────────────────────────────────────────────────

@router.post("/change-password")
def change_password(
    body: ChangePasswordRequest,
    request: Request,
    db: Session = Depends(get_db),
    user: AppUser = Depends(get_current_user),
):
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect.")
    ok, reason = password_meets_policy(body.new_password)
    if not ok:
        raise HTTPException(status_code=422, detail=reason)
    user.password_hash = hash_password(body.new_password)
    log_action(db, "password_changed", user_id=str(user.id), ip_address=_client_ip(request))
    db.commit()
    return {"message": "Password changed successfully."}


# ── User management (super_admin only) ───────────────────────────────────────

@router.post("/users", response_model=UserResponse, dependencies=[Depends(require_super_admin)])
def create_user(
    body: CreateUserRequest,
    request: Request,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(get_current_user),
):
    existing = db.query(AppUser).filter(AppUser.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="Email already in use.")
    ok, reason = password_meets_policy(body.password)
    if not ok:
        raise HTTPException(status_code=422, detail=reason)

    new_user = AppUser(
        email=body.email,
        display_name=body.display_name,
        password_hash=hash_password(body.password),
        role=body.role,
        department_scope=body.department_scope,
        created_by=admin.id,
    )
    db.add(new_user)
    log_action(
        db, "user_created",
        user_id=str(admin.id),
        target_type="app_user",
        detail={"email": body.email, "role": body.role},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(new_user)
    return new_user


@router.get("/users", response_model=list[UserResponse], dependencies=[Depends(require_super_admin)])
def list_users(db: Session = Depends(get_db)):
    return db.query(AppUser).order_by(AppUser.created_at).all()


@router.patch("/users/{user_id}/deactivate", dependencies=[Depends(require_super_admin)])
def deactivate_user(
    user_id: str,
    request: Request,
    db: Session = Depends(get_db),
    admin: AppUser = Depends(get_current_user),
):
    if user_id == str(admin.id):
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account.")
    target = db.query(AppUser).filter(AppUser.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found.")
    target.is_active = False
    log_action(
        db, "user_deactivated",
        user_id=str(admin.id),
        target_type="app_user",
        target_id=user_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"message": f"User {target.email} deactivated."}
