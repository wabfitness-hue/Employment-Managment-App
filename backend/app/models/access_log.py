import enum
from sqlalchemy import Column, String, Enum, Boolean, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base, UUIDMixin, UUIDType


class AccessDirection(str, enum.Enum):
    in_ = "in"
    out = "out"


class AccessLogEntry(Base, UUIDMixin):
    """
    One row per door tap that was evaluated. Powers the "Building Access"
    history on a person's profile (date/time in, date/time out). Only taps
    that were actually evaluated at a reader are recorded here — this is
    separate from the generic audit log, which exists for security review,
    not building-presence reporting.
    """
    __tablename__ = "access_log_entries"

    person_id = Column(UUIDType(), ForeignKey("people.id"), nullable=False, index=True)
    # store by .value ("in"/"out"), not member name (AccessDirection.in_ can't be
    # named "in" since that's a Python keyword — values_callable keeps the DB
    # column using the plain "in"/"out" strings regardless).
    direction = Column(
        Enum(AccessDirection, values_callable=lambda enum_cls: [e.value for e in enum_cls]),
        nullable=False,
    )
    granted = Column(Boolean, nullable=False)
    reason = Column(String(200), nullable=True)   # denial reason, if any
    nfc_uid = Column(String(50), nullable=True)
    device_id = Column(String(100), nullable=True)  # which reader/bridge, if known

    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    person = relationship("Person")

    def __repr__(self):
        return f"<AccessLogEntry {self.direction.value} person={self.person_id} granted={self.granted} at {self.timestamp}>"
