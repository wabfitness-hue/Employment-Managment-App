"""
Audit log viewer, plus (deliberately limited) deletion.

The audit trail is written by `log_action` across the app. Viewing is open to
IT/Super admins. Deletion — a single entry or a bulk "older than N days" purge
— is restricted to super_admin only, and every deletion first writes its own
audit entry (who deleted what, when, how many) before removing anything. This
means the deleted content is gone, but the fact that a deletion happened and
who did it is never itself erasable — the log can be trimmed, but not silently
rewritten.
"""
from datetime import datetime, timedelta, timezone
from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_user import AppUser
from app.models.audit_log import AuditLog
from app.core.dependencies import require_it_or_above, require_super_admin
from app.core.audit import log_action
from app.core.request_ip import client_ip

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_it_or_above),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: Optional[str] = Query(None),
    q: Optional[str] = Query(None, description="Search in action, IP, or actor email"),
):
    """Return audit entries newest-first, with the actor joined, plus a total count."""
    query = (
        db.query(AuditLog, AppUser)
        .outerjoin(AppUser, AppUser.id == AuditLog.user_id)
    )

    if action:
        query = query.filter(AuditLog.action == action)
    if q:
        like = f"%{q.strip()}%"
        query = query.filter(or_(
            AuditLog.action.ilike(like),
            AuditLog.ip_address.ilike(like),
            AppUser.email.ilike(like),
        ))

    total = query.count()
    rows = (
        query.order_by(AuditLog.timestamp.desc())
        .offset(offset).limit(limit).all()
    )

    items = [
        {
            "id": str(log.id),
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "action": log.action,
            "actor_email": actor.email if actor else None,
            "actor_name": actor.display_name if actor else None,
            "target_type": log.target_type,
            "target_id": str(log.target_id) if log.target_id else None,
            "ip_address": log.ip_address,
            "detail": log.detail or {},
        }
        for log, actor in rows
    ]
    return {"total": total, "limit": limit, "offset": offset, "items": items}


@router.get("/actions")
def list_actions(
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_it_or_above),
):
    """Distinct action names, for the filter dropdown."""
    rows = db.query(AuditLog.action).distinct().order_by(AuditLog.action).all()
    return {"actions": [r[0] for r in rows]}


# ── Deletion (super_admin only) ────────────────────────────────────────────────
# Both routes below record a fresh audit entry describing the deletion BEFORE
# removing anything, so a purge is itself permanently visible in the trail.

@router.delete("/{entry_id}")
def delete_audit_entry(
    entry_id: str,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    try:
        eid = uuid.UUID(entry_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid audit entry ID.")

    entry = db.query(AuditLog).filter(AuditLog.id == eid).first()
    if not entry:
        raise HTTPException(status_code=404, detail="Audit entry not found.")

    log_action(
        db, "audit_entry_deleted",
        user_id=str(current_user.id),
        target_type="audit_log", target_id=entry_id,
        detail={"deleted_action": entry.action, "deleted_timestamp": entry.timestamp.isoformat() if entry.timestamp else None},
        ip_address=client_ip(request),
    )
    db.delete(entry)
    db.commit()
    return {"deleted": True}


class PurgeRequest(BaseModel):
    older_than_days: int


@router.post("/purge")
def purge_audit_entries(
    body: PurgeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AppUser = Depends(require_super_admin),
):
    if body.older_than_days < 1:
        raise HTTPException(status_code=422, detail="older_than_days must be at least 1.")

    cutoff = datetime.now(timezone.utc) - timedelta(days=body.older_than_days)
    to_delete = db.query(AuditLog).filter(AuditLog.timestamp < cutoff)
    count = to_delete.count()

    log_action(
        db, "audit_log_purged",
        user_id=str(current_user.id),
        detail={"older_than_days": body.older_than_days, "count": count, "cutoff": cutoff.isoformat()},
        ip_address=client_ip(request),
    )
    to_delete.delete(synchronize_session=False)
    db.commit()
    return {"deleted": count}
