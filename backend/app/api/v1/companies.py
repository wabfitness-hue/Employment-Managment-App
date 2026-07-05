"""
Company routes:
  GET  /companies              — list all companies (main + contractor companies)
  POST /companies              — create a new contractor company
  GET  /companies/card-design  — current ID card colours
  PUT  /companies/card-design  — update ID card colours
"""
import json
import re
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.company import Company
from app.models.app_user import AppUser
from app.core.dependencies import require_hr_or_above, require_any_role

router = APIRouter(prefix="/companies", tags=["companies"])

HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")
DEFAULT_EMPLOYEE_COLOUR = "#1E40AF"
DEFAULT_CONTRACTOR_COLOUR = "#EA5B0C"


class CompanyCreate(BaseModel):
    name: str

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Company name cannot be blank.")
        return v


@router.get("")
def list_companies(
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_hr_or_above),
):
    companies = db.query(Company).order_by(Company.name).all()
    return [
        {
            "id": str(c.id),
            "name": c.name,
            "is_main_company": c.is_main_company,
        }
        for c in companies
    ]


@router.post("", status_code=201)
def create_company(
    body: CompanyCreate,
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_hr_or_above),
):
    # Prevent duplicate names
    existing = db.query(Company).filter(Company.name == body.name).first()
    if existing:
        return {"id": str(existing.id), "name": existing.name, "is_main_company": existing.is_main_company}

    company = Company(name=body.name, is_main_company=False)
    db.add(company)
    db.commit()
    db.refresh(company)
    return {"id": str(company.id), "name": company.name, "is_main_company": company.is_main_company}


# ── Card design ───────────────────────────────────────────────────────────────

VALID_FONTS = {"helvetica", "times", "courier"}

DEFAULT_DESIGN = {
    "employee": {
        "bg_colour": DEFAULT_EMPLOYEE_COLOUR,
        "text_colour": "#FFFFFF",
        "accent_colour": "#F4C833",
        "band_colour": "",   # empty = auto-darken the card colour
        "company_colour": "",  # empty = same as text colour
        "font": "helvetica",
    },
    "contractor": {
        "bg_colour": DEFAULT_CONTRACTOR_COLOUR,
        "text_colour": "#FFFFFF",
        "accent_colour": "#F4C833",
        "band_colour": "",
        "company_colour": "",
        "font": "helvetica",
    },
}


class TypeDesign(BaseModel):
    bg_colour: str
    text_colour: str = "#FFFFFF"
    accent_colour: str = "#F4C833"
    band_colour: str = ""      # empty string = auto-darken the card colour
    company_colour: str = ""   # empty string = same as text colour
    font: str = "helvetica"

    @field_validator("bg_colour", "text_colour", "accent_colour")
    @classmethod
    def valid_hex(cls, v: str) -> str:
        v = v.strip().upper()
        if not HEX_RE.match(v):
            raise ValueError("Colour must be a hex code like #1E40AF.")
        return v

    @field_validator("band_colour", "company_colour")
    @classmethod
    def valid_optional_hex(cls, v: str) -> str:
        v = (v or "").strip().upper()
        if v and not HEX_RE.match(v):
            raise ValueError("Colour must be a hex code like #1E40AF.")
        return v

    @field_validator("font")
    @classmethod
    def valid_font(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in VALID_FONTS:
            raise ValueError(f"Font must be one of: {', '.join(sorted(VALID_FONTS))}.")
        return v


class CardDesignUpdate(BaseModel):
    employee: TypeDesign
    contractor: TypeDesign


def _main_company(db: Session) -> Company:
    company = db.query(Company).filter(Company.is_main_company.is_(True)).first()
    if not company:
        raise HTTPException(status_code=404, detail="Main company not found — complete setup first.")
    return company


def load_card_design(company: Company) -> dict:
    """Merge stored design over defaults so missing keys never break rendering."""
    design = {k: dict(v) for k, v in DEFAULT_DESIGN.items()}
    if company.card_design:
        try:
            stored = json.loads(company.card_design)
            for kind in ("employee", "contractor"):
                if isinstance(stored.get(kind), dict):
                    # band_colour is allowed to be empty (means "auto-darken");
                    # every other key only overrides when it has a truthy value.
                    design[kind].update({
                        k: v for k, v in stored[kind].items()
                        if v or k in ("band_colour", "company_colour")
                    })
        except (ValueError, TypeError):
            pass
    # Legacy single-colour columns act as fallback background
    if company.card_background_colour and not (company.card_design and "employee" in (company.card_design or "")):
        design["employee"]["bg_colour"] = company.card_background_colour
    if company.contractor_card_colour and not (company.card_design and "contractor" in (company.card_design or "")):
        design["contractor"]["bg_colour"] = company.contractor_card_colour
    return design


@router.get("/card-design")
def get_card_design(
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_any_role),
):
    return load_card_design(_main_company(db))


@router.put("/card-design")
def update_card_design(
    body: CardDesignUpdate,
    db: Session = Depends(get_db),
    _: AppUser = Depends(require_hr_or_above),
):
    company = _main_company(db)
    design = {"employee": body.employee.model_dump(), "contractor": body.contractor.model_dump()}
    company.card_design = json.dumps(design)
    # Keep legacy columns in sync
    company.card_background_colour = body.employee.bg_colour
    company.contractor_card_colour = body.contractor.bg_colour
    db.commit()
    return design
