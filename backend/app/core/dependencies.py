"""
FastAPI dependency injection — current user extraction, RBAC enforcement.
Import these into route handlers to protect endpoints.
"""
from typing import Optional
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError
from sqlalchemy.orm import Session

from .security import decode_token
from ..database import get_db
from ..models.app_user import AppUser, UserRole

bearer_scheme = HTTPBearer(auto_error=False)


class AuthError(HTTPException):
    def __init__(self, detail: str):
        super().__init__(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


class PermissionError(HTTPException):
    def __init__(self, detail: str = "Insufficient permissions."):
        super().__init__(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _get_token_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if not credentials:
        raise AuthError("No authentication token provided.")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise AuthError("Invalid or expired token.")
    if payload.get("type") != "access":
        raise AuthError("Invalid token type.")
    return payload


def get_current_user(
    payload: dict = Depends(_get_token_payload),
    db: Session = Depends(get_db),
) -> AppUser:
    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Token missing user identity.")

    user = db.query(AppUser).filter(AppUser.id == user_id, AppUser.is_active == True).first()
    if not user:
        raise AuthError("User not found or deactivated.")

    if user.mfa_enabled and not payload.get("mfa"):
        raise AuthError("MFA verification required.")

    return user


def get_current_user_no_mfa_check(
    payload: dict = Depends(_get_token_payload),
    db: Session = Depends(get_db),
) -> AppUser:
    """Used during MFA verification step — before MFA is confirmed."""
    user_id = payload.get("sub")
    if not user_id:
        raise AuthError("Token missing user identity.")
    user = db.query(AppUser).filter(AppUser.id == user_id, AppUser.is_active == True).first()
    if not user:
        raise AuthError("User not found or deactivated.")
    return user


# ── RBAC role guards — use as FastAPI dependencies ───────────────────────────

def require_roles(*roles: UserRole):
    def checker(current_user: AppUser = Depends(get_current_user)) -> AppUser:
        if current_user.role not in roles:
            raise PermissionError()
        return current_user
    return checker


require_super_admin = require_roles(UserRole.super_admin)

require_hr_or_above = require_roles(
    UserRole.super_admin,
    UserRole.hr_admin,
)

require_it_or_above = require_roles(
    UserRole.super_admin,
    UserRole.it_admin,
)

require_any_role = require_roles(
    UserRole.super_admin,
    UserRole.hr_admin,
    UserRole.it_admin,
    UserRole.manager,
)
