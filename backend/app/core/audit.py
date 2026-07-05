"""
Audit logging helper — call log_action() from any route to write to audit_log.
Captures user, IP, action, before/after state automatically.
"""
from typing import Optional, Any
from sqlalchemy.orm import Session
from ..models.audit_log import AuditLog
import uuid


def log_action(
    db: Session,
    action: str,
    user_id: Optional[str] = None,
    target_type: Optional[str] = None,
    target_id: Optional[str] = None,
    detail: Optional[dict] = None,
    ip_address: Optional[str] = None,
    user_agent: Optional[str] = None,
) -> None:
    entry = AuditLog(
        user_id=uuid.UUID(user_id) if user_id else None,
        action=action,
        target_type=target_type,
        target_id=uuid.UUID(str(target_id)) if target_id else None,
        detail=detail or {},
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
