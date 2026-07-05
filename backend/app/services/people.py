"""
People service — all business logic for creating, updating, and managing
employees and contractors. Keeps routes thin.
"""
import uuid
from datetime import date
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import or_
from fastapi import HTTPException

from app.models.person import Person, PersonStatus
from app.models.id_prefix import IdPrefix, PersonType
from app.models.contract import Contract
from app.models.access import AccessProfile, PersonAccess
from app.models.company import Company
from app.api.v1.schemas.people import PersonCreate, PersonUpdate, PersonFilter


def _get_prefix_or_404(db: Session, prefix_id: str) -> IdPrefix:
    prefix = db.query(IdPrefix).filter(
        IdPrefix.id == prefix_id,
        IdPrefix.is_active == True,
    ).first()
    if not prefix:
        raise HTTPException(status_code=404, detail="ID prefix not found or inactive.")
    return prefix


def _get_company_or_404(db: Session, company_id: str) -> Company:
    company = db.query(Company).filter(Company.id == company_id).first()
    if not company:
        raise HTTPException(status_code=404, detail="Company not found.")
    return company


def _generate_employee_id(db: Session, prefix: IdPrefix) -> str:
    """
    Generate a random (non-sequential) ID for a prefix.
    Loops on collision (extremely rare with 10,000,000 possible suffixes) to guarantee uniqueness.
    """
    for _ in range(50):
        candidate = prefix.generate_employee_id()
        exists = db.query(Person).filter(Person.employee_id == candidate).first()
        if not exists:
            return candidate
    raise HTTPException(status_code=409, detail="Could not generate a unique ID for this prefix — it may be exhausted.")


def _auto_assign_access(db: Session, person: Person, assigned_by_id: Optional[str]) -> None:
    """Look up the default AccessProfile for this person's prefix and assign it."""
    profile = db.query(AccessProfile).filter(
        AccessProfile.default_for_prefix_id == person.prefix_id,
        AccessProfile.is_active == True,
    ).first()

    if not profile:
        return

    is_contractor = person.person_type == PersonType.contractor
    access = PersonAccess(
        person_id=person.id,
        profile_id=profile.id,
        has_time_restriction=is_contractor,
        # Contractors start with Mon–Fri 08:00–17:30 — HR edits as needed
        allowed_days="monday,tuesday,wednesday,thursday,friday" if is_contractor else None,
        assigned_by=uuid.UUID(assigned_by_id) if assigned_by_id else None,
    )
    if is_contractor:
        from datetime import time
        access.access_start = time(8, 0)
        access.access_end = time(17, 30)

    db.add(access)


def create_person(
    db: Session,
    data: PersonCreate,
    created_by_id: Optional[str],
) -> Person:
    prefix = _get_prefix_or_404(db, data.prefix_id)
    company = _get_company_or_404(db, data.company_id)

    # Type consistency check
    if prefix.applies_to != data.person_type:
        raise HTTPException(
            status_code=422,
            detail=f"Prefix '{prefix.prefix}' is for {prefix.applies_to.value}s, "
                   f"not {data.person_type.value}s.",
        )

    # Contractors must not use the main company
    if data.person_type == PersonType.contractor and company.is_main_company:
        raise HTTPException(
            status_code=422,
            detail="Contractors must be linked to their own company, not the main company.",
        )

    # Employees must use the main company
    if data.person_type == PersonType.employee and not company.is_main_company:
        raise HTTPException(
            status_code=422,
            detail="Employees must be linked to the main company.",
        )

    # Duplicate email check
    if db.query(Person).filter(Person.email == data.email).first():
        raise HTTPException(status_code=409, detail="Email address already registered.")

    employee_id = _generate_employee_id(db, prefix)

    person = Person(
        person_type=data.person_type,
        employee_id=employee_id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        job_title=data.job_title,
        department=data.department,
        floor=data.floor,
        notes=data.notes,
        nfc_uid=data.nfc_uid,
        company_id=uuid.UUID(data.company_id),
        prefix_id=uuid.UUID(data.prefix_id),
        created_by=uuid.UUID(created_by_id) if created_by_id else None,
        status=PersonStatus.pending,
    )
    db.add(person)
    db.flush()

    # Create contract
    if data.person_type == PersonType.employee:
        contract = Contract.new_employee_contract(person.id, data.contract_start)
    else:
        contract = Contract.new_contractor_contract(person.id, data.contract_start)
    db.add(contract)

    # Auto-assign access profile
    _auto_assign_access(db, person, created_by_id)

    db.flush()
    return person


def update_person(db: Session, person_id: str, data: PersonUpdate) -> Person:
    person = get_person_or_404(db, person_id)
    updates = data.model_dump(exclude_unset=True)

    if "email" in updates:
        conflict = db.query(Person).filter(
            Person.email == updates["email"],
            Person.id != uuid.UUID(person_id),
        ).first()
        if conflict:
            raise HTTPException(status_code=409, detail="Email address already in use.")

    for field, value in updates.items():
        setattr(person, field, value)

    db.flush()
    return person


def change_status(
    db: Session,
    person_id: str,
    new_status: PersonStatus,
    changed_by_id: str,
) -> Person:
    person = get_person_or_404(db, person_id)
    person.status = new_status
    db.flush()
    return person


def delete_person(db: Session, person_id: str) -> None:
    """
    Permanently remove a person and everything that references them, in
    foreign-key-safe order: zone overrides → access → card events →
    contracts → the person row. Also deletes their photo file.
    """
    from app.models.contract import Contract
    from app.models.card_event import CardEvent
    from app.models.access import PersonAccess, PersonAccessZone
    from app.services.photos.storage import delete_photo

    person = get_person_or_404(db, person_id)
    pid = person.id

    access_rows = db.query(PersonAccess).filter(PersonAccess.person_id == pid).all()
    for access in access_rows:
        db.query(PersonAccessZone).filter(
            PersonAccessZone.person_access_id == access.id
        ).delete(synchronize_session=False)
    db.query(PersonAccess).filter(PersonAccess.person_id == pid).delete(synchronize_session=False)

    db.query(CardEvent).filter(CardEvent.person_id == pid).delete(synchronize_session=False)

    # Break the self-referential contract link before deleting the rows
    db.query(Contract).filter(Contract.person_id == pid).update(
        {"renewed_from": None}, synchronize_session=False
    )
    db.query(Contract).filter(Contract.person_id == pid).delete(synchronize_session=False)

    db.delete(person)
    db.flush()

    # Remove the photo file last (DB is the source of truth)
    try:
        delete_photo(str(pid))
    except Exception:
        pass


def assign_nfc(db: Session, person_id: str, nfc_uid: str) -> Person:
    nfc_uid = nfc_uid.strip().upper()
    person = get_person_or_404(db, person_id)
    conflict = db.query(Person).filter(
        Person.nfc_uid == nfc_uid,
        Person.id != uuid.UUID(person_id),
    ).first()
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"NFC UID already assigned to {conflict.employee_id}.",
        )
    person.nfc_uid = nfc_uid
    db.flush()
    return person


def lookup_by_nfc(db: Session, nfc_uid: str) -> Person:
    uid = nfc_uid.upper()
    person = db.query(Person).filter(
        or_(Person.nfc_uid == uid, Person.temp_nfc_uid == uid)
    ).first()
    if not person:
        raise HTTPException(status_code=404, detail="No employee found for this NFC card.")
    return person


def issue_temp_card(db: Session, person_id: str, temp_uid: str) -> Person:
    """
    Issue a temporary card because the permanent one was forgotten.
    The permanent card is kept on record but blocked; the temp card opens doors.
    """
    temp_uid = temp_uid.strip().upper()
    person = get_person_or_404(db, person_id)

    # The temp card must not already belong to someone else (either slot)
    conflict = db.query(Person).filter(
        or_(Person.nfc_uid == temp_uid, Person.temp_nfc_uid == temp_uid),
        Person.id != uuid.UUID(person_id),
    ).first()
    if conflict:
        raise HTTPException(
            status_code=409,
            detail=f"That card is already assigned to {conflict.employee_id}.",
        )
    if person.nfc_uid == temp_uid:
        raise HTTPException(
            status_code=409,
            detail="That's this person's permanent card — scan a different (spare) card as the temporary one.",
        )

    person.temp_nfc_uid = temp_uid
    person.card_status = "temporary"
    db.flush()
    return person


def return_temp_card(db: Session, person_id: str) -> Person:
    """Take back the temporary card and restore the permanent one."""
    person = get_person_or_404(db, person_id)
    person.temp_nfc_uid = None
    person.card_status = "active"
    person.card_status_note = None
    db.flush()
    return person


# Card states that block the physical card at a reader, with the message shown.
BLOCKING_CARD_STATUSES = {
    "lost": "Card reported lost",
    "stolen": "Card reported stolen",
    "faulty": "Card marked faulty",
    "on_leave": "Employee on leave",
    "returned": "Card has been returned",
    "not_issued": "No card issued",
}


def evaluate_card_access(person: Person, tapped_uid: Optional[str] = None) -> tuple[bool, Optional[str]]:
    """
    Decide whether a tapped card should open the door.
    Returns (granted, denied_reason). Reason is None when granted.
    """
    if person.status != PersonStatus.active:
        return False, f"Access holder is {person.status.value}"

    tapped = (tapped_uid or "").upper()

    # While a temporary card is issued, only the temp card works — the forgotten
    # permanent card is blocked so it can't also open doors.
    if person.temp_nfc_uid:
        if tapped and tapped == (person.nfc_uid or "").upper():
            return False, "Permanent card forgotten — temporary card in use"
        # temp card (or unknown tap) falls through to the contract check below
    else:
        blocked = BLOCKING_CARD_STATUSES.get(person.card_status or "active")
        if blocked:
            return False, blocked

    contract = person.current_contract
    if not contract:
        return False, "No active contract"
    if getattr(contract, "is_expired", False):
        return False, "Contract expired"

    return True, None


def get_person_or_404(db: Session, person_id: str) -> Person:
    try:
        uid = uuid.UUID(person_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid person ID format.")
    person = db.query(Person).filter(Person.id == uid).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")
    return person


def list_people(db: Session, filters: PersonFilter, current_user_role: str, current_user_dept: Optional[str]):
    query = db.query(Person)

    # Managers only see their own department
    if current_user_role == "manager" and current_user_dept:
        query = query.filter(Person.department == current_user_dept)

    if filters.person_type:
        query = query.filter(Person.person_type == filters.person_type)

    if filters.department:
        query = query.filter(Person.department.ilike(f"%{filters.department}%"))

    if filters.status:
        query = query.filter(Person.status == filters.status)

    if filters.search:
        term = f"%{filters.search}%"
        query = query.filter(
            or_(
                Person.first_name.ilike(term),
                Person.last_name.ilike(term),
                Person.email.ilike(term),
                Person.employee_id.ilike(term),
                Person.job_title.ilike(term),
            )
        )

    if filters.expiring_within_days is not None:
        today = date.today()
        expiry_cutoff = date.fromordinal(today.toordinal() + filters.expiring_within_days)
        query = query.join(Contract, Contract.person_id == Person.id).filter(
            Contract.is_current == True,
            Contract.end_date <= expiry_cutoff,
            Contract.end_date >= today,
        )

    return query.order_by(Person.last_name, Person.first_name).all()
