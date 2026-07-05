import enum
from sqlalchemy import Column, String, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin, UUIDType
from .id_prefix import PersonType


class PersonStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"
    pending = "pending"
    suspended = "suspended"


class Person(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "people"

    person_type = Column(Enum(PersonType), nullable=False)
    employee_id = Column(String(20), nullable=False, unique=True, index=True)
    nfc_uid = Column(String(50), nullable=True, unique=True, index=True)
    # A temporary card issued while the permanent one is forgotten. When set,
    # this card opens doors and the permanent card is blocked until returned.
    temp_nfc_uid = Column(String(50), nullable=True, unique=True, index=True)

    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(200), nullable=False, unique=True, index=True)
    phone = Column(String(50), nullable=True)

    photo_path = Column(String(500), nullable=True)

    job_title = Column(String(200), nullable=False)
    department = Column(String(200), nullable=False)
    floor = Column(String(50), nullable=True)
    notes = Column(Text, nullable=True)

    status = Column(Enum(PersonStatus), default=PersonStatus.pending, nullable=False)

    # Card state — why the physical card's access differs from normal (forgotten,
    # lost, temporary card issued, faulty, on leave…). Separate from employment
    # status so a lost card never deactivates the person. Stored as a plain string
    # so the list of reasons stays easily extensible.
    card_status = Column(String(30), default="active", server_default="active", nullable=False)
    card_status_note = Column(String(300), nullable=True)

    company_id = Column(UUIDType(), ForeignKey("companies.id"), nullable=False)
    prefix_id = Column(UUIDType(), ForeignKey("id_prefixes.id"), nullable=False)
    created_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)

    company = relationship("Company", back_populates="people")
    prefix = relationship("IdPrefix", back_populates="people")
    creator = relationship("AppUser", foreign_keys=[created_by])
    contracts = relationship(
        "Contract",
        back_populates="person",
        order_by="Contract.start_date.desc()",
        lazy="dynamic",
    )
    card_events = relationship("CardEvent", back_populates="person", lazy="dynamic")

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"

    @property
    def current_contract(self):
        return self.contracts.filter_by(is_current=True).first()

    def __repr__(self):
        return f"<Person {self.employee_id} {self.full_name}>"
