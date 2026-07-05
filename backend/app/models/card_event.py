import enum
from sqlalchemy import Column, String, Enum, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base, UUIDMixin, UUIDType


class CardEventType(str, enum.Enum):
    scan = "scan"
    encode = "encode"
    print = "print"
    reprint = "reprint"
    revoke = "revoke"


class CardEvent(Base, UUIDMixin):
    __tablename__ = "card_events"

    person_id = Column(UUIDType(), ForeignKey("people.id"), nullable=False, index=True)
    event_type = Column(Enum(CardEventType), nullable=False)
    nfc_uid = Column(String(50), nullable=True)
    performed_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)
    device_id = Column(String(100), nullable=True)
    result = Column(String(50), nullable=True)
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True,
    )

    person = relationship("Person", back_populates="card_events")
    actor = relationship("AppUser", foreign_keys=[performed_by])

    def __repr__(self):
        return f"<CardEvent {self.event_type} person={self.person_id} at {self.timestamp}>"
