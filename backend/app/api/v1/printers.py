"""
Printer routes:
  GET    /printers       — list configured printers (for the per-print picker)
  POST   /printers       — add a printer (name + OS printer name, or Zebra IP)
  DELETE /printers/{id}  — remove a printer

Printers are configured once (e.g. in Settings) and then chosen per print job
on a person's profile, so an office with printers on different floors/departments
can send each card to the right one. Actual printing is done by the bridge agent
running on the host machine — this table just remembers the options.
"""
import re
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_user import AppUser
from app.models.printer import Printer, PrinterTargetType
from app.core.dependencies import require_hr_or_above, require_any_role
from app.core.audit import log_action

router = APIRouter(prefix="/printers", tags=["printers"])

_IP_RE = re.compile(
    r"^(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}$"
)


class PrinterCreate(BaseModel):
    label: str
    target_type: PrinterTargetType = PrinterTargetType.os
    target: str

    @field_validator("label")
    @classmethod
    def strip_label(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Label is required.")
        return v

    @field_validator("target")
    @classmethod
    def strip_target(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Target is required.")
        return v


class PrinterResponse(BaseModel):
    id: str
    label: str
    target_type: PrinterTargetType
    target: str

    model_config = {"from_attributes": True}

    @field_validator("id", mode="before")
    @classmethod
    def _stringify_id(cls, v):
        return str(v)


def _validate_target(body: PrinterCreate) -> None:
    if body.target_type == PrinterTargetType.zebra and not _IP_RE.match(body.target):
        raise HTTPException(
            status_code=422,
            detail="Zebra printers are addressed by IP address, e.g. 192.168.1.50.",
        )


@router.get("", response_model=list[PrinterResponse])
def list_printers(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    return db.query(Printer).order_by(Printer.label).all()


@router.post("", response_model=PrinterResponse)
def create_printer(
    body: PrinterCreate,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    _validate_target(body)
    printer = Printer(
        label=body.label,
        target_type=body.target_type,
        target=body.target,
        created_by=current_user.id,
    )
    db.add(printer)
    db.commit()
    db.refresh(printer)
    log_action(db, "printer_added", user_id=str(current_user.id),
               target_type="printer", target_id=str(printer.id),
               detail={"label": printer.label, "target_type": printer.target_type.value})
    db.commit()
    return printer


@router.delete("/{printer_id}")
def delete_printer(
    printer_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    import uuid
    try:
        pid = uuid.UUID(printer_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid printer ID.")

    printer = db.query(Printer).filter(Printer.id == pid).first()
    if not printer:
        raise HTTPException(status_code=404, detail="Printer not found.")

    label = printer.label
    db.delete(printer)
    log_action(db, "printer_removed", user_id=str(current_user.id),
               target_type="printer", target_id=printer_id, detail={"label": label})
    db.commit()
    return {"deleted": True}
