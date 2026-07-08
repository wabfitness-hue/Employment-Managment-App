"""
Audit log viewer (read-only).

The audit trail is written by `log_action` across the app. These endpoints let
IT/Super admins review it. There is intentionally no create/update/delete — an
audit log you can edit is not an audit log.
"""
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.app_user import AppUser
from app.models.audit_log import AuditLog
from app.core.dependencies import require_it_or_above

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
