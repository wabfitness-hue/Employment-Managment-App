import enum
import random
from sqlalchemy import Column, String, Integer, Enum, Boolean, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin, UUIDType


class PersonType(str, enum.Enum):
    employee = "employee"
    contractor = "contractor"


class IdPrefix(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "id_prefixes"

    prefix = Column(String(10), nullable=False, unique=True)
    label = Column(String(100), nullable=False)
    applies_to = Column(Enum(PersonType), nullable=False)
    next_sequence = Column(Integer, default=1, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)

    created_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)

    creator = relationship("AppUser", foreign_keys=[created_by])
    people = relationship("Person", back_populates="prefix", lazy="dynamic")

    def generate_employee_id(self) -> str:
        """Random 5-digit suffix (not sequential) so IDs aren't guessable / orderable."""
        return f"{self.prefix}{random.randint(0, 99999):05d}"

    def __repr__(self):
        return f"<IdPrefix {self.prefix} ({self.label})>"
