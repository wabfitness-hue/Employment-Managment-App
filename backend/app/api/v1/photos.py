"""
Photo routes:
  POST /photos/{person_id}/upload      — file upload (HR selects file)
  POST /photos/{person_id}/webcam      — base64 image from browser webcam
  GET  /photos/{person_id}             — serve the photo (authenticated)
  DELETE /photos/{person_id}           — remove photo
  POST /photos/scan-outlook            — trigger Outlook intake scan
"""
import base64
from fastapi import APIRouter, Depends, Request, UploadFile, File, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_user import AppUser
from app.models.person import Person
from app.core.dependencies import get_current_user, require_hr_or_above, require_any_role
from app.core.audit import log_action
from app.services.photos.validation import validate_photo_bytes, validate_base64_photo
from app.services.photos.storage import save_photo, delete_photo, get_photo_bytes, photo_exists
from app.core.config import get_settings
from app.services import people as people_svc

router = APIRouter(prefix="/photos", tags=["photos"])


def _client_ip(request: Request) -> str:
    direct_ip = request.client.host if request.client else "unknown"
    trusted = get_settings().trusted_proxy_list
    if direct_ip in trusted:
        fwd = request.headers.get("X-Forwarded-For")
        if fwd:
            return fwd.split(",")[0].strip()
    return direct_ip


class WebcamUploadRequest(BaseModel):
    image_data: str   # base64 data URI from browser


# ── File upload ───────────────────────────────────────────────────────────────

@router.post("/{person_id}/upload")
async def upload_photo(
    person_id: str,
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = people_svc.get_person_or_404(db, person_id)

    raw = await file.read()
    validate_photo_bytes(raw, file.filename or "")
    relative_path = save_photo(person_id, raw)

    person.photo_path = relative_path
    log_action(
        db, "photo_uploaded",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail={"method": "file_upload", "filename": file.filename},
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"photo_path": relative_path, "message": "Photo saved successfully."}


# ── Webcam capture ────────────────────────────────────────────────────────────

@router.post("/{person_id}/webcam")
async def webcam_photo(
    person_id: str,
    body: WebcamUploadRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = people_svc.get_person_or_404(db, person_id)

    raw = validate_base64_photo(body.image_data)
    validate_photo_bytes(raw)
    relative_path = save_photo(person_id, raw)

    person.photo_path = relative_path
    log_action(
        db, "photo_uploaded",
        user_id=str(current_user.id),
        target_type="person",
        target_id=person_id,
        detail={"method": "webcam"},
        ip_address=_client_ip(request),
    )
    db.commit()
    return {"photo_path": relative_path, "message": "Webcam photo saved successfully."}


# ── Serve photo ───────────────────────────────────────────────────────────────

@router.get("/{person_id}")
def serve_photo(
    person_id: str,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_any_role),
):
    """
    Serves the photo for a person. Always goes through auth —
    photos are never accessible without a valid session token.
    """
    people_svc.get_person_or_404(db, person_id)

    if not photo_exists(person_id):
        raise HTTPException(status_code=404, detail="No photo on file for this person.")

    try:
        data = get_photo_bytes(person_id)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="No photo on file for this person.")
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Content-Disposition": f'inline; filename="{person_id}.jpg"'},
    )


# ── Delete photo ──────────────────────────────────────────────────────────────

@router.delete("/{person_id}")
def remove_photo(
    person_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    person = people_svc.get_person_or_404(db, person_id)
    deleted = delete_photo(person_id)
    if deleted:
        person.photo_path = None
        log_action(
            db, "photo_deleted",
            user_id=str(current_user.id),
            target_type="person",
            target_id=person_id,
            ip_address=_client_ip(request),
        )
        db.commit()
    return {"deleted": deleted}


# ── Outlook scan ──────────────────────────────────────────────────────────────

@router.post("/scan-outlook")
async def scan_outlook(
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_hr_or_above),
):
    """
    Triggers a scan of the Outlook HR-Intake inbox for photo emails.
    Requires the Outlook integration to have been authorised first.
    """
    from app.services.photos.outlook_extractor import process_intake_emails
    from app.core.config import get_settings

    # In production the token comes from the stored MSAL session
    # In dev/test with no token configured this returns a clear message
    settings = get_settings()
    if not settings.MS_CLIENT_ID:
        return {
            "status": "not_configured",
            "message": "Outlook integration not yet configured. Connect via Settings → Outlook.",
        }

    # Token would be retrieved from the stored OAuth session here
    # Placeholder until Phase 8 (Outlook integration) is built
    return {
        "status": "pending",
        "message": "Outlook scan will be available after Phase 8 Outlook integration is complete.",
    }
