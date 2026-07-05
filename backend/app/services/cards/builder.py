"""
Card data builder — assembles CardData from a Person record and related models.
Keeps the generator pure (no DB access), and this module handles DB queries.
"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException

from app.models.person import Person
from app.models.company import Company
from app.models.access import PersonAccess
from app.services.photos.storage import get_photo_bytes, photo_exists
from .generator import CardData


def build_card_data(db: Session, person_id: str) -> CardData:
    """
    Loads all data needed to render an ID card for a person.
    Raises 404 if person not found or has no current contract.
    """
    try:
        pid = uuid.UUID(person_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid person ID.")

    person = db.query(Person).filter(Person.id == pid).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")

    contract = person.current_contract
    if not contract:
        raise HTTPException(
            status_code=422,
            detail=f"{person.full_name} has no active contract — cannot generate ID card.",
        )

    company = db.query(Company).filter(Company.id == person.company_id).first()
    company_name = company.name if company else "Unknown Company"

    # Card design (colours + font) from the card designer
    from app.api.v1.companies import load_card_design, DEFAULT_DESIGN
    main_company = db.query(Company).filter(Company.is_main_company.is_(True)).first()
    kind = "contractor" if person.person_type.value == "contractor" else "employee"
    design = load_card_design(main_company) if main_company else DEFAULT_DESIGN
    type_design = design[kind]

    bg_colour = type_design["bg_colour"]
    # Per-contractor-company override still wins for background
    if kind == "contractor" and company and not company.is_main_company and company.card_background_colour:
        bg_colour = company.card_background_colour

    # Access info
    access_record = db.query(PersonAccess).filter(
        PersonAccess.person_id == person.id
    ).first()

    access_name = None
    access_days = None
    access_start = None
    access_end = None

    if access_record and access_record.profile:
        access_name = access_record.profile.name
        if access_record.has_time_restriction:
            access_days = access_record.allowed_days
            if access_record.access_start:
                access_start = access_record.access_start.strftime("%H:%M")
            if access_record.access_end:
                access_end = access_record.access_end.strftime("%H:%M")

    # Photo
    photo_bytes = None
    if photo_exists(person_id):
        try:
            photo_bytes = get_photo_bytes(person_id)
        except Exception:
            pass

    return CardData(
        person_id=person_id,
        person_type=person.person_type.value,
        employee_id=person.employee_id,
        full_name=person.full_name,
        job_title=person.job_title,
        department=person.department,
        floor=person.floor,
        company_name=company_name,
        contract_end=contract.end_date,
        photo_bytes=photo_bytes,
        access_profile_name=access_name,
        access_days=access_days,
        access_start=access_start,
        access_end=access_end,
        bg_colour_hex=bg_colour,
        nfc_uid=person.nfc_uid,
        text_colour_hex=type_design["text_colour"],
        accent_colour_hex=type_design["accent_colour"],
        band_colour_hex=type_design.get("band_colour") or None,
        company_colour_hex=type_design.get("company_colour") or None,
        font=type_design["font"],
    )
