"""
Core import engine — takes validated rows and writes Person + Contract records.
Wraps each row in a savepoint so one bad row never kills the whole batch.
"""
import uuid
from datetime import date
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from app.models.person import Person, PersonStatus, PersonType
from app.models.company import Company
from app.models.id_prefix import IdPrefix
from app.models.import_job import ImportJob, ImportStatus
from app.services.people import create_person
from app.api.v1.schemas.people import PersonCreate
from .validator import RowResult


def _get_or_create_company(db: Session, name: str, is_main: bool = False) -> Company:
    company = db.query(Company).filter(
        Company.name.ilike(name.strip())
    ).first()
    if not company:
        company = Company(name=name.strip(), is_main_company=is_main)
        db.add(company)
        db.flush()
    return company


def _guess_prefix(db: Session, job_title: str, person_type: str) -> Optional[str]:
    """
    Heuristic: try to find the right IdPrefix for a job title.
    Falls back to CTR for contractors and ENG for employees.
    """
    title_lower = job_title.lower()
    prefixes = db.query(IdPrefix).all()
    # Exact or partial match on label
    for p in prefixes:
        if p.label.lower() in title_lower or title_lower.startswith(p.label.lower()):
            if p.applies_to.value == person_type:
                return str(p.id)
    # Fallback by type
    fallback_label = "CTR" if person_type == "contractor" else "ENG"
    for p in prefixes:
        if p.prefix == fallback_label:
            return str(p.id)
    # Any prefix matching the person type
    for p in prefixes:
        if p.applies_to.value == person_type:
            return str(p.id)
    return None


def run_import(
    db: Session,
    job: ImportJob,
    valid_rows: list[RowResult],
    main_company_id: str,
    performed_by_id: str,
) -> ImportJob:
    """
    Process valid rows from a completed validation run.
    Updates the ImportJob in-place and returns it.
    """
    job.status = ImportStatus.processing
    db.flush()

    imported = 0
    skipped = 0
    errors = []

    main_company = db.query(Company).filter(
        Company.id == uuid.UUID(main_company_id)
    ).first()

    for result in valid_rows:
        if not result.is_valid:
            skipped += 1
            errors.append({"row": result.row_number, "errors": result.errors})
            continue

        row = result.cleaned
        sp = db.begin_nested()   # savepoint — bad row rolls back to here only
        try:
            # Resolve company
            if row.get("person_type") == "contractor":
                company_name = row.get("company_name", "Unknown Contractor Company")
                company = _get_or_create_company(db, company_name, is_main=False)
                company_id = str(company.id)
            else:
                company_id = main_company_id

            # Find prefix
            prefix_id = _guess_prefix(db, row["job_title"], row["person_type"])
            if not prefix_id:
                raise ValueError(f"No ID prefix found for job title '{row['job_title']}'")

            create_data = PersonCreate(
                first_name=row["first_name"],
                last_name=row["last_name"],
                email=row["email"],
                phone=row.get("phone"),
                person_type=row["person_type"],
                job_title=row["job_title"],
                department=row["department"],
                floor=row.get("floor"),
                company_id=company_id,
                prefix_id=prefix_id,
                contract_start=row.get("start_date", date.today()),
                nfc_uid=row.get("nfc_uid"),
            )

            create_person(db, create_data, created_by_id=performed_by_id)
            sp.commit()
            imported += 1

        except IntegrityError as exc:
            sp.rollback()
            skipped += 1
            errors.append({
                "row": result.row_number,
                "errors": [f"Duplicate record (email or NFC UID already exists): {exc.orig}"],
            })
        except Exception as exc:
            sp.rollback()
            skipped += 1
            errors.append({
                "row": result.row_number,
                "errors": [str(exc)],
            })

    from datetime import datetime, timezone
    job.records_imported = imported
    job.records_skipped = skipped
    job.errors = errors if errors else None
    job.status = ImportStatus.completed if imported > 0 else ImportStatus.failed
    job.completed_at = datetime.now(timezone.utc)
    db.flush()

    return job
