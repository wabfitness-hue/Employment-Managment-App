from pydantic import BaseModel, EmailStr, field_validator
from typing import Optional
from datetime import date
from app.models.id_prefix import PersonType
from app.models.person import PersonStatus

# Card states — why a physical card's access differs from normal. Extend this
# list to add new reasons; the frontend reads the same values.
CARD_STATUSES = {
    "active": "Card active",
    "forgotten": "Forgot card",
    "temporary": "Temporary card issued",
    "lost": "Lost card",
    "stolen": "Stolen card",
    "faulty": "Faulty card",
    "on_leave": "On leave",
    "returned": "Card returned",
    "not_issued": "No card issued",
}


class PersonCreate(BaseModel):
    person_type: PersonType
    prefix_id: str
    first_name: str
    last_name: str
    email: EmailStr
    phone: Optional[str] = None
    job_title: str
    department: str
    floor: Optional[str] = None
    company_id: str
    contract_start: date
    notes: Optional[str] = None
    nfc_uid: Optional[str] = None

    @field_validator("first_name", "last_name", "job_title", "department")
    @classmethod
    def strip_and_nonempty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field cannot be blank.")
        return v

    @field_validator("email")
    @classmethod
    def normalise_email(cls, v: str) -> str:
        return v.strip().lower()


class PersonUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    job_title: Optional[str] = None
    department: Optional[str] = None
    floor: Optional[str] = None
    notes: Optional[str] = None

    @field_validator("first_name", "last_name", "job_title", "department", mode="before")
    @classmethod
    def strip_if_set(cls, v):
        if isinstance(v, str):
            v = v.strip()
            if not v:
                raise ValueError("Field cannot be blank.")
        return v


class ContractResponse(BaseModel):
    id: str
    contract_type: str
    start_date: date
    end_date: date
    is_current: bool
    renewal_count: int
    days_remaining: int
    expiry_warning_level: Optional[str]

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def _stringify_id(cls, v):
        return str(v)


class AccessSummary(BaseModel):
    profile_name: str
    has_time_restriction: bool
    allowed_days: Optional[str]
    access_start: Optional[str]
    access_end: Optional[str]
    zone_count: int


class PersonResponse(BaseModel):
    id: str
    person_type: PersonType
    employee_id: str
    first_name: str
    last_name: str
    full_name: str
    email: str
    phone: Optional[str]
    photo_path: Optional[str]
    has_photo: bool = False
    job_title: str
    department: str
    floor: Optional[str]
    notes: Optional[str]
    status: PersonStatus
    card_status: str = "active"
    card_status_note: Optional[str] = None
    company_id: str
    prefix_id: str
    nfc_uid: Optional[str]
    temp_nfc_uid: Optional[str] = None
    current_contract: Optional[ContractResponse]
    access: Optional[AccessSummary]

    model_config = {"from_attributes": True}

    @field_validator("id", "company_id", "prefix_id", mode="before")
    @classmethod
    def _stringify_ids(cls, v):
        return str(v)


class PersonListItem(BaseModel):
    id: str
    person_type: PersonType
    employee_id: str
    full_name: str
    job_title: str
    department: str
    status: PersonStatus
    card_status: str = "active"
    company_id: str
    has_photo: bool = False
    expiry_warning_level: Optional[str] = None

    model_config = {"from_attributes": True}

    @field_validator("id", "company_id", mode="before")
    @classmethod
    def _stringify_ids(cls, v):
        return str(v)


class StatusChangeRequest(BaseModel):
    status: PersonStatus
    reason: Optional[str] = None


class CardStatusRequest(BaseModel):
    card_status: str
    note: Optional[str] = None

    @field_validator("card_status")
    @classmethod
    def valid_card_status(cls, v: str) -> str:
        v = v.strip().lower()
        if v not in CARD_STATUSES:
            raise ValueError(f"Card status must be one of: {', '.join(CARD_STATUSES)}.")
        return v


class NFCAssignRequest(BaseModel):
    nfc_uid: str

    @field_validator("nfc_uid")
    @classmethod
    def clean_uid(cls, v: str) -> str:
        return v.strip().upper()


class PersonFilter(BaseModel):
    person_type: Optional[PersonType] = None
    department: Optional[str] = None
    status: Optional[PersonStatus] = None
    search: Optional[str] = None
    expiring_within_days: Optional[int] = None
