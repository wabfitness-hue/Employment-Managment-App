import enum
from sqlalchemy import Column, String, Enum, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin, UUIDType


class PrinterTargetType(str, enum.Enum):
    os = "os"        # OS print queue, addressed by the printer's name (covers
                      # locally-installed and Windows-shared network printers)
    zebra = "zebra"   # Zebra card printer, addressed by IP over raw ZPL/TCP


class Printer(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "printers"

    label = Column(String(100), nullable=False)
    target_type = Column(Enum(PrinterTargetType), nullable=False, default=PrinterTargetType.os)
    # OS printer name (target_type=os) or IP address (target_type=zebra)
    target = Column(String(255), nullable=False)

    created_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)
    creator = relationship("AppUser", foreign_keys=[created_by])

    def __repr__(self):
        return f"<Printer {self.label} ({self.target_type.value}:{self.target})>"
