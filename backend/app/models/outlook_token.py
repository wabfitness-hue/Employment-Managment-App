"""
Stores a single Outlook OAuth token set per installation.
Only one connected account is supported (the admin's personal Outlook).
"""
from sqlalchemy import Column, String, DateTime, Text
from .base import Base, UUIDMixin, TimestampMixin, UUIDType
from sqlalchemy import ForeignKey
from sqlalchemy.orm import relationship


class OutlookToken(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "outlook_tokens"

    # The admin user who authorized this connection
    owner_id = Column(UUIDType(), ForeignKey("app_users.id"), nullable=False, unique=True)

    # Encrypted at rest (AES-256 via Fernet before storing)
    access_token_enc = Column(Text, nullable=False)
    refresh_token_enc = Column(Text, nullable=True)

    # Plain metadata (not sensitive)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    outlook_email = Column(String(200), nullable=True)
    scope = Column(String(500), nullable=True)

    owner = relationship("AppUser", foreign_keys=[owner_id])

    def __repr__(self):
        return f"<OutlookToken owner={self.owner_id} email={self.outlook_email}>"
