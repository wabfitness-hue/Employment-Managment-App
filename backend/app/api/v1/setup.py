"""
First-run setup wizard routes.

The wizard is available only when NO app users exist yet (fresh install).
Once a super_admin user is created the /setup/* routes return 409 Conflict.

Steps:
  GET  /setup/status            — is setup needed?
  POST /setup/company           — step 1: create company
  POST /setup/admin             — step 2: create super_admin account + MFA
  POST /setup/prefixes          — step 3: confirm / edit ID prefixes
  GET  /setup/prefixes          — get current prefix list (for review)
  POST /setup/complete          — mark setup done, return first JWT
"""
import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_user import AppUser, UserRole
from app.models.company import Company
from app.models.id_prefix import IdPrefix, PersonType
from app.core.security import hash_password, password_meets_policy, generate_mfa_secret, get_mfa_provisioning_uri
from app.core.config import get_settings
from app.core.dependencies import require_hr_or_above

router = APIRouter(prefix="/setup", tags=["setup"])
settings = get_settings()


def _setup_guard(db: Session) -> None:
    """Raise 409 if any app user already exists."""
    if db.query(AppUser).first():
        raise HTTPException(
            status_code=409,
            detail="Setup already completed. Log in normally.",
        )


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
def setup_status(db: Session = Depends(get_db)):
    """Returns whether first-run setup is needed."""
    has_users = db.query(AppUser).first() is not None
    has_company = db.query(Company).first() is not None
    return {
        "setup_required": not has_users,
        "has_company": has_company,
        "has_users": has_users,
    }


# ── Step 1: Company ───────────────────────────────────────────────────────────

class CompanySetupRequest(BaseModel):
    name: str
    card_background_colour: str = "#1E40AF"
    card_text_colour: str = "#FFFFFF"
    contractor_card_colour: Optional[str] = "#EA580C"

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v):
        if not v.strip():
            raise ValueError("Company name cannot be blank.")
        return v.strip()

    @field_validator("card_background_colour", "card_text_colour")
    @classmethod
    def valid_hex(cls, v):
        import re
        if not re.match(r"^#[0-9A-Fa-f]{6}$", v):
            raise ValueError(f"'{v}' is not a valid hex colour (e.g. #1E40AF).")
        return v


@router.post("/company")
def setup_company(body: CompanySetupRequest, db: Session = Depends(get_db)):
    _setup_guard(db)

    existing = db.query(Company).filter(Company.is_main_company == True).first()
    if existing:
        # Update rather than create
        existing.name = body.name
        existing.card_background_colour = body.card_background_colour
        existing.card_text_colour = body.card_text_colour
        db.commit()
        return {"id": str(existing.id), "name": existing.name, "updated": True}

    company = Company(
        name=body.name,
        is_main_company=True,
        card_background_colour=body.card_background_colour,
        card_text_colour=body.card_text_colour,
    )
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"id": str(company.id), "name": company.name, "created": True}


# ── Step 2: Admin account ─────────────────────────────────────────────────────

class AdminSetupRequest(BaseModel):
    email: EmailStr
    password: str
    full_name: str

    @field_validator("password")
    @classmethod
    def strong_password(cls, v):
        ok, msg = password_meets_policy(v)
        if not ok:
            raise ValueError(msg)
        return v

    @field_validator("full_name")
    @classmethod
    def name_not_blank(cls, v):
        if not v.strip():
            raise ValueError("full_name cannot be blank.")
        return v.strip()


@router.post("/admin")
def setup_admin(body: AdminSetupRequest, db: Session = Depends(get_db)):
    """
    Create the first super_admin user.
    Returns an MFA provisioning URI — the admin must scan it before calling /setup/complete.
    """
    _setup_guard(db)

    if not db.query(Company).filter(Company.is_main_company == True).first():
        raise HTTPException(status_code=409, detail="Complete /setup/company first.")

    mfa_secret = generate_mfa_secret()

    admin = AppUser(
        display_name=body.full_name.strip(),
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        role=UserRole.super_admin,
        is_active=True,
        mfa_secret=mfa_secret,
        mfa_enabled=False,   # becomes True after /setup/complete verifies the code
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)

    provisioning_uri = get_mfa_provisioning_uri(mfa_secret, body.email)
    return {
        "admin_id": str(admin.id),
        "email": admin.email,
        "mfa_provisioning_uri": provisioning_uri,
        "mfa_secret": mfa_secret,
        "message": "Scan the QR code in your authenticator app, then call /setup/complete.",
    }


# ── Step 3: ID prefixes ───────────────────────────────────────────────────────

class PrefixItem(BaseModel):
    prefix: str
    label: str
    person_type: str   # "employee" or "contractor"

    @field_validator("prefix")
    @classmethod
    def prefix_format(cls, v):
        import re
        v = v.strip().upper()
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError("Prefix must be 1–5 uppercase letters (e.g. A, B, EMP, CTR).")
        return v

    @field_validator("person_type")
    @classmethod
    def valid_type(cls, v):
        if v not in ("employee", "contractor"):
            raise ValueError("person_type must be 'employee' or 'contractor'.")
        return v


class PrefixSetupRequest(BaseModel):
    prefixes: List[PrefixItem]


@router.get("/prefixes")
def get_prefixes(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    prefixes = db.query(IdPrefix).order_by(IdPrefix.label).all()
    return [
        {"id": str(p.id), "prefix": p.prefix, "label": p.label, "person_type": p.applies_to.value}
        for p in prefixes
    ]


@router.post("/prefixes")
def setup_prefixes(
    body: PrefixSetupRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    """
    Replace the entire prefix list with what HR has decided.
    HR-admin-or-above only — this deletes and rebuilds all ID prefixes.
    """
    if not body.prefixes:
        raise HTTPException(status_code=422, detail="At least one prefix required.")

    # Validate uniqueness
    codes = [p.prefix for p in body.prefixes]
    if len(codes) != len(set(codes)):
        raise HTTPException(status_code=422, detail="Duplicate prefix codes found.")

    # Delete existing and replace
    db.query(IdPrefix).delete()
    for item in body.prefixes:
        db.add(IdPrefix(
            prefix=item.prefix,
            label=item.label,
            applies_to=PersonType[item.person_type],
            next_sequence=1,
        ))

    db.commit()
    return {"created": len(body.prefixes), "prefixes": codes}


# ── Quick prefix (used when adding a person) ───────────────────────────────────

class QuickPrefixRequest(BaseModel):
    prefix: str
    person_type: str

    @field_validator("prefix")
    @classmethod
    def prefix_format(cls, v):
        import re
        v = v.strip().upper()
        if not re.match(r"^[A-Z]{1,5}$", v):
            raise ValueError("Letter must be 1–5 uppercase letters (A–Z).")
        return v

    @field_validator("person_type")
    @classmethod
    def valid_type(cls, v):
        if v not in ("employee", "contractor"):
            raise ValueError("person_type must be 'employee' or 'contractor'.")
        return v


@router.post("/prefixes/quick")
def quick_prefix(
    body: QuickPrefixRequest,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    """
    Find-or-create an ID prefix for the given letter, used when a user types
    a letter directly on the Add Person form rather than picking from Settings.
    """
    existing = db.query(IdPrefix).filter(IdPrefix.prefix == body.prefix).first()
    if existing:
        if existing.applies_to.value != body.person_type:
            raise HTTPException(
                status_code=422,
                detail=f"Letter '{body.prefix}' is already used for {existing.applies_to.value}s.",
            )
        return {"id": str(existing.id), "prefix": existing.prefix}

    label = "Employees" if body.person_type == "employee" else "Contractors"
    new_prefix = IdPrefix(
        prefix=body.prefix,
        label=f"{label} ({body.prefix})",
        applies_to=PersonType[body.person_type],
        next_sequence=1,
        created_by=current_user.id,
    )
    db.add(new_prefix)
    db.commit()
    db.refresh(new_prefix)
    return {"id": str(new_prefix.id), "prefix": new_prefix.prefix}


# ── Step 4: Complete setup ────────────────────────────────────────────────────

class CompleteSetupRequest(BaseModel):
    admin_id: str
    mfa_token: str   # 6-digit TOTP code


@router.post("/complete")
def complete_setup(body: CompleteSetupRequest, db: Session = Depends(get_db)):
    """
    Verify the admin's MFA token, enable MFA on the account, return a JWT.
    After this call the /setup/* routes will return 409.
    """
    try:
        aid = uuid.UUID(body.admin_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid admin_id.")

    admin = db.query(AppUser).filter(AppUser.id == aid).first()
    if not admin:
        raise HTTPException(status_code=404, detail="Admin user not found.")

    # Only valid during first-run setup: once MFA is enabled the account is set
    # up, so this passwordless (TOTP-only) completion path must not be reusable.
    if admin.mfa_enabled:
        raise HTTPException(status_code=409, detail="Setup already completed. Log in normally.")

    from app.core.security import verify_mfa_token, create_access_token, create_refresh_token
    if not verify_mfa_token(admin.mfa_secret, body.mfa_token):
        raise HTTPException(status_code=401, detail="MFA token is invalid or expired.")

    admin.mfa_enabled = True
    db.commit()

    access_token = create_access_token(str(admin.id), admin.role.value, mfa_verified=True)
    refresh_token = create_refresh_token(str(admin.id))

    return {
        "message": "Setup complete. Welcome!",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": admin.role.value,
        "email": admin.email,
    }
