"""
ID Card routes:
  GET  /cards/{person_id}         — generate and download single card PDF
  POST /cards/bulk                — generate multi-card A4 sheet PDF
  GET  /cards/{person_id}/preview — card data as JSON (for frontend preview)
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.app_user import AppUser
from app.core.dependencies import get_current_user, require_hr_or_above, require_any_role
from app.core.audit import log_action
from app.services.cards.builder import build_card_data
from app.services.cards.generator import generate_card_pdf
from app.services.cards.bulk import generate_bulk_pdf
from app.models.card_event import CardEvent, CardEventType

router = APIRouter(prefix="/cards", tags=["cards"])


def _client_ip(request: Request) -> str:
    fwd = request.headers.get("X-Forwarded-For")
    return fwd.split(",")[0].strip() if fwd else request.client.host


class BulkCardRequest(BaseModel):
    person_ids: List[str]


# ── Single card ───────────────────────────────────────────────────────────────

@router.get("/{person_id}")
def get_card(
    person_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    card_data = build_card_data(db, person_id)
    pdf_bytes = generate_card_pdf(card_data)

    # Log the print event
    import uuid as _uuid
    db.add(CardEvent(
        person_id=_uuid.UUID(person_id),
        event_type=CardEventType.print,
        performed_by=current_user.id,
        result="generated",
    ))
    log_action(
        db, "card_printed",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail={"employee_id": card_data.employee_id},
        ip_address=_client_ip(request),
    )
    db.commit()

    filename = f"ID_Card_{card_data.employee_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ── Card preview (JSON, no PDF) ───────────────────────────────────────────────

@router.get("/{person_id}/preview")
def preview_card(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    """Returns card data as JSON so the frontend can render a live preview."""
    card = build_card_data(db, person_id)
    return {
        "person_id": card.person_id,
        "person_type": card.person_type,
        "employee_id": card.employee_id,
        "full_name": card.full_name,
        "job_title": card.job_title,
        "department": card.department,
        "floor": card.floor,
        "company_name": card.company_name,
        "contract_end": card.contract_end.isoformat(),
        "has_photo": card.photo_bytes is not None,
        "access_profile_name": card.access_profile_name,
        "access_days": card.access_days,
        "access_start": card.access_start,
        "access_end": card.access_end,
        "is_contractor": card.is_contractor,
        "nfc_uid": card.nfc_uid,
        "bg_colour": card.bg_colour_hex,
        "text_colour": card.text_colour_hex,
        "accent_colour": card.accent_colour_hex,
        "band_colour": card.band_colour_hex,
        "company_colour": card.company_colour_hex,
        "font": card.font,
    }


# ── Bulk cards ────────────────────────────────────────────────────────────────

@router.post("/bulk")
def get_bulk_cards(
    body: BulkCardRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    if not body.person_ids:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="No person IDs provided.")
    if len(body.person_ids) > 100:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Maximum 100 cards per bulk request.")

    cards = []
    failed = []
    for pid in body.person_ids:
        try:
            cards.append(build_card_data(db, pid))
        except Exception as exc:
            failed.append({"person_id": pid, "error": str(exc)})

    if not cards:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail=f"No valid cards to generate. Errors: {failed}")

    pdf_bytes = generate_bulk_pdf(cards)

    import uuid as _uuid
    for card in cards:
        db.add(CardEvent(
            person_id=_uuid.UUID(card.person_id),
            event_type=CardEventType.print,
            performed_by=current_user.id,
            result="bulk_generated",
        ))

    log_action(
        db, "bulk_cards_printed",
        user_id=str(current_user.id),
        detail={
            "count": len(cards),
            "failed": len(failed),
            "employee_ids": [c.employee_id for c in cards],
        },
        ip_address=_client_ip(request),
    )
    db.commit()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="ID_Cards_Bulk.pdf"'},
    )
