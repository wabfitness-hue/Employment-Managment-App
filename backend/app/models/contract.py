import enum
from datetime import date, timedelta
from sqlalchemy import Column, String, Enum, ForeignKey, Date, Boolean, Integer
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin, UUIDType


class ContractType(str, enum.Enum):
    employee_5yr = "employee_5yr"
    contractor_6mo = "contractor_6mo"


class Contract(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "contracts"

    person_id = Column(UUIDType(), ForeignKey("people.id"), nullable=False)
    contract_type = Column(Enum(ContractType), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    is_current = Column(Boolean, default=True, nullable=False, index=True)
    renewal_count = Column(Integer, default=0, nullable=False)

    renewed_from = Column(UUIDType(), ForeignKey("contracts.id"), nullable=True)
    renewed_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)

    person = relationship("Person", back_populates="contracts")
    previous_contract = relationship(
        "Contract", remote_side="Contract.id", foreign_keys=[renewed_from]
    )
    renewer = relationship("AppUser", foreign_keys=[renewed_by])

    @property
    def days_remaining(self) -> int:
        return (self.end_date - date.today()).days

    @property
    def is_expired(self) -> bool:
        return self.end_date < date.today()

    @property
    def expiry_warning_level(self) -> str | None:
        days = self.days_remaining
        if days <= 0:
            return "expired"
        if days <= 14:
            return "critical"
        if days <= 30:
            return "warning"
        if days <= 90:
            return "notice"
        return None

    @classmethod
    def new_employee_contract(cls, person_id, start: date, renewed_by=None, renewed_from=None):
        return cls(
            person_id=person_id,
            contract_type=ContractType.employee_5yr,
            start_date=start,
            end_date=date(start.year + 5, start.month, start.day),
            is_current=True,
            renewed_by=renewed_by,
            renewed_from=renewed_from,
        )

    @classmethod
    def new_contractor_contract(cls, person_id, start: date, renewed_by=None, renewed_from=None, renewal_count=0):
        end = start + timedelta(days=183)
        return cls(
            person_id=person_id,
            contract_type=ContractType.contractor_6mo,
            start_date=start,
            end_date=end,
            is_current=True,
            renewed_by=renewed_by,
            renewed_from=renewed_from,
            renewal_count=renewal_count,
        )

    def __repr__(self):
        return f"<Contract {self.contract_type} {self.start_date}–{self.end_date} current={self.is_current}>"
