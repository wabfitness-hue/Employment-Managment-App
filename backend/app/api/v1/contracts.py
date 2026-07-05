"""
Contract routes:
  POST /contracts/{person_id}/renew      — renew current contract
  GET  /contracts/{person_id}/history    — full contract history for a person
  GET  /contracts/expiring               — list expiring within N days
  GET  /contracts/expired                — list overdue contracts
  GET  /contracts/report                 — full expiry dashboard report
  POST /contracts/send-alerts            — manually trigger alert emails (IT/admin)
"""
from fastapi import APIRouter, Depends, Request, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.app_user import AppUser
from app.core.dependencies import get_current_user, require_hr_or_above, require_any_role
from app.core.audit import log_action
from app.services import contracts as svc
from app.api.v1.schemas.contracts import (
    RenewContractRequest, ContractDetailResponse,
    ExpiryItemResponse, ExpiryReportResponse,
)

router = APIRouter(prefix="/contracts", tags=["contracts"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else request.client.host


def _contract_response(contract) -> ContractDetailResponse:
    return ContractDetailResponse(
        id=str(contract.id),
        person_id=str(contract.person_id),
        contract_type=contract.contract_type.value,
        start_date=contract.start_date,
        end_date=contract.end_date,
        is_current=contract.is_current,
        renewal_count=contract.renewal_count,
        days_remaining=contract.days_remaining,
        expiry_warning_level=contract.expiry_warning_level,
        renewed_from=str(contract.renewed_from) if contract.renewed_from else None,
    )


# ── Renew ─────────────────────────────────────────────────────────────────────

@router.post("/{person_id}/renew", response_model=ContractDetailResponse)
def renew_contract(
    person_id: str,
    body: RenewContractRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    contract = svc.renew_contract(db, person_id, str(current_user.id), body.custom_start)
    log_action(
        db, "contract_renewed",
        user_id=str(current_user.id),
        target_type="contract",
        target_id=str(contract.id),
        detail={
            "person_id": person_id,
            "new_end_date": contract.end_date.isoformat(),
            "renewal_count": contract.renewal_count,
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(contract)
    return _contract_response(contract)


# ── History ───────────────────────────────────────────────────────────────────

@router.get("/{person_id}/history", response_model=list[ContractDetailResponse])
def get_history(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    contracts = svc.get_contract_history(db, person_id)
    return [_contract_response(c) for c in contracts]


# ── Expiry dashboard ──────────────────────────────────────────────────────────

@router.get("/expiring", response_model=list[ExpiryItemResponse])
def get_expiring(
    within_days: int = Query(default=90, ge=1, le=365),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    return svc.get_expiring_contracts(db, within_days)


@router.get("/expired", response_model=list[dict])
def get_expired(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    return svc.get_expired_contracts(db)


@router.get("/report", response_model=ExpiryReportResponse)
def get_report(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    return svc.build_expiry_report(db)


# ── Manual alert trigger ──────────────────────────────────────────────────────

@router.post("/send-alerts")
async def send_alerts(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    result = await svc.send_expiry_alerts(db)
    log_action(
        db, "alerts_sent_manually",
        user_id=str(current_user.id),
        detail=result,
        ip_address=_client_ip(request),
    )
    db.commit()
    return result
