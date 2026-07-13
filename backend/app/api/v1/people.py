"""
People routes:
  POST   /people                     — create employee or contractor
  GET    /people                     — list with filters
  GET    /people/{id}                — get full record
  PATCH  /people/{id}                — update fields
  POST   /people/{id}/status         — activate / deactivate / suspend
  POST   /people/{id}/nfc            — assign NFC UID after card encoding
  GET    /people/nfc/{uid}           — look up person by NFC tap
  DELETE /people/{id}                — soft delete (sets status=inactive)
  GET    /people/departments         — distinct department list for dropdowns
"""
import csv
import io
from datetime import date
from fastapi import APIRouter, Depends, Request, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models.app_user import AppUser
from app.core.dependencies import get_current_user, require_hr_or_above, require_any_role
from app.core.audit import log_action
from app.services import people as svc
from app.api.v1.schemas.people import (
    PersonCreate, PersonUpdate, PersonResponse, PersonListItem,
    StatusChangeRequest, CardStatusRequest, NFCAssignRequest, PersonFilter,
    AccessSummary, ContractResponse,
)
from app.models.person import Person, PersonStatus
from app.models.access import PersonAccess

router = APIRouter(prefix="/people", tags=["people"])


from app.core.request_ip import client_ip as _client_ip


def _build_response(person: Person, db: Session) -> PersonResponse:
    contract = person.current_contract
    contract_resp = None
    if contract:
        contract_resp = ContractResponse(
            id=str(contract.id),
            contract_type=contract.contract_type.value,
            start_date=contract.start_date,
            end_date=contract.end_date,
            is_current=contract.is_current,
            renewal_count=contract.renewal_count,
            days_remaining=contract.days_remaining,
            expiry_warning_level=contract.expiry_warning_level,
        )

    access_record = db.query(PersonAccess).filter(PersonAccess.person_id == person.id).first()
    access_resp = None
    if access_record and access_record.profile:
        zone_count = len(access_record.profile.profile_zones)
        access_resp = AccessSummary(
            profile_name=access_record.profile.name,
            has_time_restriction=access_record.has_time_restriction,
            allowed_days=access_record.allowed_days,
            access_start=str(access_record.access_start) if access_record.access_start else None,
            access_end=str(access_record.access_end) if access_record.access_end else None,
            zone_count=zone_count,
        )

    return PersonResponse(
        id=str(person.id),
        person_type=person.person_type,
        employee_id=person.employee_id,
        first_name=person.first_name,
        last_name=person.last_name,
        full_name=person.full_name,
        email=person.email,
        phone=person.phone,
        photo_path=person.photo_path,
        has_photo=bool(person.photo_path),
        job_title=person.job_title,
        department=person.department,
        floor=person.floor,
        notes=person.notes,
        status=person.status,
        card_status=person.card_status or "active",
        card_status_note=person.card_status_note,
        company_id=str(person.company_id),
        prefix_id=str(person.prefix_id),
        nfc_uid=person.nfc_uid,
        temp_nfc_uid=person.temp_nfc_uid,
        current_contract=contract_resp,
        access=access_resp,
    )


# ── Create ────────────────────────────────────────────────────────────────────

@router.post("", response_model=PersonResponse, status_code=201)
def create_person(
    body: PersonCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.create_person(db, body, str(current_user.id))
    log_action(
        db, "create_person",
        user_id=str(current_user.id),
        target_type="person",
        target_id=str(person.id),
        detail={
            "employee_id": person.employee_id,
            "person_type": person.person_type.value,
            "name": person.full_name,
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(person)
    return _build_response(person, db)


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("", response_model=list[PersonListItem])
def list_people(
    person_type: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    expiring_within_days: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    from app.models.id_prefix import PersonType
    filters = PersonFilter(
        person_type=PersonType(person_type) if person_type else None,
        department=department,
        status=PersonStatus(status) if status else None,
        search=search,
        expiring_within_days=expiring_within_days,
    )
    people = svc.list_people(
        db, filters,
        current_user_role=current_user.role.value,
        current_user_dept=current_user.department_scope,
    )

    result = []
    for p in people:
        contract = p.current_contract
        warning = contract.expiry_warning_level if contract else None
        result.append(PersonListItem(
            id=str(p.id),
            person_type=p.person_type,
            employee_id=p.employee_id,
            full_name=p.full_name,
            job_title=p.job_title,
            department=p.department,
            status=p.status,
            card_status=p.card_status or "active",
            company_id=str(p.company_id),
            has_photo=bool(p.photo_path),
            expiry_warning_level=warning,
        ))
    return result


# ── CSV export ────────────────────────────────────────────────────────────────

def _csv_safe(value: str) -> str:
    """
    Neutralise CSV/formula injection: if a cell starts with a character Excel
    or Sheets treats as a formula trigger (=, +, -, @, tab, CR), prefix it with
    a single quote so it's read as plain text instead of executed as a formula.
    """
    if value and value[0] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


@router.get("/export.csv")
def export_people_csv(
    request: Request,
    person_type: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    """Export the (filtered, scope-respecting) people list as CSV."""
    from app.models.id_prefix import PersonType
    filters = PersonFilter(
        person_type=PersonType(person_type) if person_type else None,
        department=department,
        status=PersonStatus(status) if status else None,
        search=search,
    )
    people = svc.list_people(
        db, filters,
        current_user_role=current_user.role.value,
        current_user_dept=current_user.department_scope,
    )

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        "Employee ID", "First Name", "Last Name", "Email", "Type", "Job Title",
        "Department", "Floor", "Company", "Status", "Card Status",
        "Contract End", "NFC Assigned",
    ])
    for p in people:
        contract = p.current_contract
        w.writerow([
            _csv_safe(p.employee_id), _csv_safe(p.first_name), _csv_safe(p.last_name),
            _csv_safe(p.email), p.person_type.value, _csv_safe(p.job_title),
            _csv_safe(p.department), _csv_safe(p.floor or ""),
            _csv_safe(p.company.name if p.company else ""),
            p.status.value, p.card_status or "active",
            contract.end_date.isoformat() if contract else "",
            "yes" if p.nfc_uid else "no",
        ])

    log_action(db, "people_exported", user_id=str(current_user.id),
               detail={"count": len(people)}, ip_address=_client_ip(request))
    db.commit()

    filename = f"people-{date.today().isoformat()}.csv"
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Get one ───────────────────────────────────────────────────────────────────

@router.get("/departments", response_model=list[str])
def list_departments(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    rows = db.query(Person.department).distinct().order_by(Person.department).all()
    return [r[0] for r in rows]


@router.get("/nfc/{nfc_uid}")
def get_by_nfc(
    nfc_uid: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    """
    Reader/kiosk lookup. Returns an access decision alongside the person, so a
    lost/stolen/faulty card (or an inactive holder) is denied at the door even
    though the card physically reads.

    Restricted to HR-admin-or-above: this returns a full person record for any
    card UID (a door-reader/security function), so it must not be reachable by
    department-scoped managers as an IDOR pivot.
    """
    person = svc.lookup_by_nfc(db, nfc_uid)
    granted, denied_reason = svc.evaluate_card_access(person, nfc_uid)
    log_action(
        db, "card_scan_lookup",
        user_id=str(current_user.id),
        target_type="person",
        target_id=str(person.id),
        detail={
            "nfc_uid": nfc_uid,
            "result": "granted" if granted else "denied",
            "reason": denied_reason,
        },
        ip_address=_client_ip(request),
    )
    db.commit()
    return {
        "access_granted": granted,
        "denied_reason": denied_reason,
        "card_status": person.card_status or "active",
        "person": _build_response(person, db),
    }


@router.get("/{person_id}", response_model=PersonResponse)
def get_person(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    person = svc.get_person_or_404(db, person_id)
    svc.authorize_person_access(current_user, person)
    return _build_response(person, db)


# ── Update ────────────────────────────────────────────────────────────────────

@router.patch("/{person_id}", response_model=PersonResponse)
def update_person(
    person_id: str,
    body: PersonUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.update_person(db, person_id, body)
    log_action(
        db, "update_person",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail=body.model_dump(exclude_unset=True),
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(person)
    return _build_response(person, db)


# ── Status change ─────────────────────────────────────────────────────────────

@router.post("/{person_id}/status", response_model=PersonResponse)
def change_status(
    person_id: str,
    body: StatusChangeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.change_status(db, person_id, body.status, str(current_user.id))
    log_action(
        db, "status_change",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail={"new_status": body.status.value, "reason": body.reason},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(person)
    return _build_response(person, db)


# ── Card status ───────────────────────────────────────────────────────────────

@router.post("/{person_id}/card-status", response_model=PersonResponse)
def change_card_status(
    person_id: str,
    body: CardStatusRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.get_person_or_404(db, person_id)
    person.card_status = body.card_status
    person.card_status_note = (body.note or "").strip() or None
    log_action(
        db, "card_status_change",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail={"card_status": body.card_status, "note": person.card_status_note},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(person)
    return _build_response(person, db)


# ── Temporary card (forgot card) ──────────────────────────────────────────────

@router.post("/{person_id}/temp-card", response_model=PersonResponse)
def issue_temp_card(
    person_id: str,
    body: NFCAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.issue_temp_card(db, person_id, body.nfc_uid)
    log_action(
        db, "temp_card_issued",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail={"temp_nfc_uid": person.temp_nfc_uid},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(person)
    return _build_response(person, db)


@router.delete("/{person_id}/temp-card", response_model=PersonResponse)
def return_temp_card(
    person_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.return_temp_card(db, person_id)
    log_action(
        db, "temp_card_returned",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(person)
    return _build_response(person, db)


# ── Permanent delete ──────────────────────────────────────────────────────────

@router.delete("/{person_id}")
def delete_person_permanently(
    person_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.get_person_or_404(db, person_id)
    snapshot = {
        "employee_id": person.employee_id,
        "name": person.full_name,
        "person_type": person.person_type.value,
    }
    svc.delete_person(db, person_id)
    log_action(
        db, "delete_person",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail=snapshot,
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"deleted": True, "employee_id": snapshot["employee_id"]}


# ── NFC assignment ────────────────────────────────────────────────────────────

@router.post("/{person_id}/nfc", response_model=PersonResponse)
def assign_nfc(
    person_id: str,
    body: NFCAssignRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = svc.assign_nfc(db, person_id, body.nfc_uid)
    log_action(
        db, "nfc_assigned",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail={"nfc_uid": body.nfc_uid},
        ip_address=_client_ip(request),
    )
    db.commit()
    db.refresh(person)
    return _build_response(person, db)
