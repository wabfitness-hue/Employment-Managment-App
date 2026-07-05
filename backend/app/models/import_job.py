import enum
from sqlalchemy import Column, String, Enum, ForeignKey, Integer, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .base import Base, UUIDMixin, TimestampMixin, UUIDType


class ImportSource(str, enum.Enum):
    csv = "csv"
    xlsx = "xlsx"
    docx = "docx"
    outlook_email = "outlook_email"
    manual = "manual"


class ImportStatus(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    review = "review"
    completed = "completed"
    failed = "failed"
    cancelled = "cancelled"


class ImportJob(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "import_jobs"

    source_type = Column(Enum(ImportSource), nullable=False)
    filename = Column(String(500), nullable=True)
    status = Column(Enum(ImportStatus), default=ImportStatus.pending, nullable=False)

    records_found = Column(Integer, default=0, nullable=False)
    records_imported = Column(Integer, default=0, nullable=False)
    records_skipped = Column(Integer, default=0, nullable=False)

    preview_data = Column(JSON, nullable=True)
    errors = Column(JSON, nullable=True)

    started_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)

    starter = relationship("AppUser", foreign_keys=[started_by])

    def __repr__(self):
        return f"<ImportJob {self.source_type} {self.status} found={self.records_found}>"
