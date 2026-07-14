from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from app.models.app_user import UserRole


class LoginRequest(BaseModel):
    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class MFAVerifyRequest(BaseModel):
    totp_code: str

    @field_validator("totp_code")
    @classmethod
    def strip_spaces(cls, v: str) -> str:
        return v.replace(" ", "").strip()


class MFALoginRequest(BaseModel):
    """Login MFA step: either an authenticator code OR a recovery code."""
    totp_code: Optional[str] = None
    recovery_code: Optional[str] = None

    @field_validator("totp_code", "recovery_code")
    @classmethod
    def strip_spaces(cls, v):
        return v.replace(" ", "").strip() if isinstance(v, str) else v


class RegenerateRecoveryCodesRequest(BaseModel):
    """Regenerating recovery codes is a sensitive action — require re-entering
    the current password so a hijacked-but-still-valid session can't silently
    mint new standing recovery access."""
    current_password: str


class RecoveryCodesResponse(BaseModel):
    codes: list[str]
    remaining: int


class RecoveryCodesStatus(BaseModel):
    configured: bool
    remaining: int


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    mfa_required: bool = False


class MFASetupResponse(BaseModel):
    secret: str
    provisioning_uri: str
    qr_placeholder: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def check_not_same(cls, v: str, info) -> str:
        if v == info.data.get("current_password"):
            raise ValueError("New password must differ from current password.")
        return v


class CreateUserRequest(BaseModel):
    email: EmailStr
    display_name: str
    password: str
    role: UserRole
    department_scope: Optional[str] = None

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()

    @field_validator("display_name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: str
    role: UserRole
    mfa_enabled: bool
    is_active: bool
    department_scope: Optional[str]

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def _stringify_id(cls, v):
        return str(v)
