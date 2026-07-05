from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import date


class RenewContractRequest(BaseModel):
    custom_start: Optional[date] = None


class ContractDetailResponse(BaseModel):
    id: str
    person_id: str
    contract_type: str
    start_date: date
    end_date: date
    is_current: bool
    renewal_count: int
    days_remaining: int
    expiry_warning_level: Optional[str]
    renewed_from: Optional[str]

    model_config = {"from_attributes": True}

    @field_validator("id", "person_id", "renewed_from", mode="before")
    @classmethod
    def _stringify_ids(cls, v):
        return str(v) if v is not None else v


class ExpiryItemResponse(BaseModel):
    person_id: str
    employee_id: str
    full_name: str
    person_type: str
    department: str
    job_title: str
    contract_id: str
    contract_type: str
    end_date: date
    days_remaining: int
    warning_level: Optional[str]
    renewal_count: int


class ExpiredItemResponse(BaseModel):
    person_id: str
    employee_id: str
    full_name: str
    person_type: str
    department: str
    contract_id: str
    end_date: date
    days_overdue: int


class ExpiryReportResponse(BaseModel):
    generated_on: str
    total_expiring: int
    total_expired: int
    groups: dict
    thresholds: list[int]
