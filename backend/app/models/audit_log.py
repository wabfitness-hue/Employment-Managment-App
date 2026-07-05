from sqlalchemy import Column, String, ForeignKey, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base, UUIDMixin, UUIDType


class AuditLog(Base, UUIDMixin):
    __tablename__ = "audit_log"

    user_id = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)
    action = Column(String(100), nullable=False, index=True)
    target_type = Column(String(50), nullable=True)
    target_id = Column(UUIDType(), nullable=True)
    detail = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    user_agent = Column(String(500), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    actor = relationship("AppUser", foreign_keys=[user_id])

    def __repr__(self):
        return f"<AuditLog {self.action} by {self.user_id} at {self.timestamp}>"
