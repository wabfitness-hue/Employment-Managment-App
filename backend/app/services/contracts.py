"""
Contract service — renewal, expiry checking, notification dispatch.
"""
import uuid
from datetime import date, timedelta
from typing import Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_
from fastapi import HTTPException

from app.models.contract import Contract, ContractType
from app.models.person import Person, PersonStatus
from app.models.id_prefix import PersonType
from app.core.config import get_settings

settings = get_settings()


# ── Renewal ───────────────────────────────────────────────────────────────────

def renew_contract(
    db: Session,
    person_id: str,
    renewed_by_id: str,
    custom_start: Optional[date] = None,
) -> Contract:
    """
    Renew the current contract for a person.
    - Employees: new 5-year contract starting from today (or custom_start)
    - Contractors: new 6-month contract starting from the day after the old end date
      (preserves continuity — no gap between contracts)
    The previous contract is marked is_current=False before the new one is created.
    """
    try:
        pid = uuid.UUID(person_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid person ID.")

    person = db.query(Person).filter(Person.id == pid).first()
    if not person:
        raise HTTPException(status_code=404, detail="Person not found.")

    current = db.query(Contract).filter(
        Contract.person_id == pid,
        Contract.is_current == True,
    ).first()

    if not current:
        raise HTTPException(status_code=404, detail="No current contract found.")

    if person.status == PersonStatus.inactive:
        raise HTTPException(status_code=422, detail="Cannot renew contract for an inactive person.")

    # Determine new start date
    if custom_start:
        new_start = custom_start
    elif person.person_type == PersonType.contractor:
        # Start the day after old contract ends — no gap
        new_start = current.end_date + timedelta(days=1)
    else:
        new_start = date.today()

    # Close old contract
    current.is_current = False

    # Create new contract
    renewer_id = uuid.UUID(renewed_by_id)

    if person.person_type == PersonType.employee:
        new_contract = Contract.new_employee_contract(
            person.id, new_start,
            renewed_by=renewer_id,
            renewed_from=current.id,
        )
    else:
        new_contract = Contract.new_contractor_contract(
            person.id, new_start,
            renewed_by=renewer_id,
            renewed_from=current.id,
            renewal_count=current.renewal_count + 1,
        )

    db.add(new_contract)
    db.flush()
    return new_contract


# ── Expiry queries ────────────────────────────────────────────────────────────

def get_expiring_contracts(db: Session, within_days: int) -> list[dict]:
    """
    Returns all current contracts expiring within `within_days` days.
    Each result includes person details and the warning level.
    """
    today = date.today()
    cutoff = today + timedelta(days=within_days)

    rows = (
        db.query(Contract, Person)
        .join(Person, Person.id == Contract.person_id)
        .filter(
            Contract.is_current == True,
            Contract.end_date >= today,
            Contract.end_date <= cutoff,
            Person.status != PersonStatus.inactive,
        )
        .order_by(Contract.end_date)
        .all()
    )

    results = []
    for contract, person in rows:
        results.append({
            "person_id": str(person.id),
            "employee_id": person.employee_id,
            "full_name": person.full_name,
            "person_type": person.person_type.value,
            "department": person.department,
            "job_title": person.job_title,
            "contract_id": str(contract.id),
            "contract_type": contract.contract_type.value,
            "end_date": contract.end_date,
            "days_remaining": contract.days_remaining,
            "warning_level": contract.expiry_warning_level,
            "renewal_count": contract.renewal_count,
        })
    return results


def get_expired_contracts(db: Session) -> list[dict]:
    """Contracts that are past their end date but still marked is_current=True."""
    today = date.today()
    rows = (
        db.query(Contract, Person)
        .join(Person, Person.id == Contract.person_id)
        .filter(
            Contract.is_current == True,
            Contract.end_date < today,
        )
        .order_by(Contract.end_date)
        .all()
    )
    results = []
    for contract, person in rows:
        results.append({
            "person_id": str(person.id),
            "employee_id": person.employee_id,
            "full_name": person.full_name,
            "person_type": person.person_type.value,
            "department": person.department,
            "contract_id": str(contract.id),
            "end_date": contract.end_date,
            "days_overdue": abs(contract.days_remaining),
        })
    return results


def get_contract_history(db: Session, person_id: str) -> list[Contract]:
    try:
        pid = uuid.UUID(person_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid person ID.")
    return (
        db.query(Contract)
        .filter(Contract.person_id == pid)
        .order_by(Contract.start_date.desc())
        .all()
    )


# ── Expiry notification engine ────────────────────────────────────────────────

def build_expiry_report(db: Session) -> dict:
    """
    Builds the full expiry report used by the daily alert job and the
    dashboard. Groups by warning level for easy display.
    """
    max_window = max(settings.ALERT_DAYS_BEFORE_EXPIRY)
    all_expiring = get_expiring_contracts(db, max_window)
    expired = get_expired_contracts(db)

    grouped: dict[str, list] = {
        "expired": expired,
        "critical": [],   # ≤ 14 days
        "warning": [],    # ≤ 30 days
        "notice": [],     # ≤ 90 days
    }

    for item in all_expiring:
        level = item["warning_level"]
        if level in grouped:
            grouped[level].append(item)

    return {
        "generated_on": date.today().isoformat(),
        "total_expiring": len(all_expiring),
        "total_expired": len(expired),
        "groups": grouped,
        "thresholds": settings.ALERT_DAYS_BEFORE_EXPIRY,
    }


async def send_expiry_alerts(db: Session) -> dict:
    """
    Called once daily (scheduled job). Sends email alerts to HR for each
    warning threshold crossed. Returns a summary of what was sent.
    """
    report = build_expiry_report(db)
    sent = []
    errors = []

    for level, items in report["groups"].items():
        if not items:
            continue
        try:
            await _send_alert_email(level, items)
            sent.append({"level": level, "count": len(items)})
        except Exception as exc:
            errors.append({"level": level, "error": str(exc)})

    return {"sent": sent, "errors": errors, "report_date": report["generated_on"]}


async def _send_alert_email(level: str, items: list) -> None:
    """
    Sends a single alert email for a warning level group.
    Uses aiosmtplib — falls back silently if SMTP not configured in dev.
    """
    if not settings.SMTP_HOST or not settings.ALERT_EMAIL_FROM:
        return  # SMTP not configured — skip silently in local dev

    import aiosmtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    level_labels = {
        "expired": "EXPIRED — Immediate Action Required",
        "critical": "CRITICAL — Expiring Within 14 Days",
        "warning": "WARNING — Expiring Within 30 Days",
        "notice": "NOTICE — Expiring Within 90 Days",
    }

    subject = f"[EMS] Contract Alert: {level_labels.get(level, level)} ({len(items)} records)"

    rows = "\n".join(
        f"  • {i['employee_id']} — {i['full_name']} "
        f"({i['person_type']}) expires {i['end_date']} "
        f"[{i.get('days_remaining', 0)} days]"
        for i in items
    )
    body = f"Contract Expiry Alert\n{'='*40}\n\n{rows}\n\nPlease log into the Employee Management System to take action."

    msg = MIMEMultipart()
    msg["From"] = settings.ALERT_EMAIL_FROM
    msg["To"] = settings.ALERT_EMAIL_FROM
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    await aiosmtplib.send(
        msg,
        hostname=settings.SMTP_HOST,
        port=settings.SMTP_PORT,
        username=settings.SMTP_USER,
        password=settings.SMTP_PASSWORD,
        start_tls=True,
    )
