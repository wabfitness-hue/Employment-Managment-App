from sqlalchemy import Column, String, Boolean, Text
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin


class Company(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "companies"

    name = Column(String(200), nullable=False)
    short_name = Column(String(50), nullable=True)
    is_main_company = Column(Boolean, default=False, nullable=False)
    address = Column(Text, nullable=True)
    phone = Column(String(50), nullable=True)
    email = Column(String(200), nullable=True)
    logo_path = Column(String(500), nullable=True)

    card_background_colour = Column(String(7), nullable=True)
    card_text_colour = Column(String(7), nullable=True)
    # Global contractor card colour — only meaningful on the main company row
    contractor_card_colour = Column(String(7), nullable=True)
    # Full card design JSON ({"employee": {...}, "contractor": {...}}) — main company row only
    card_design = Column(Text, nullable=True)

    people = relationship("Person", back_populates="company", lazy="dynamic")

    def __repr__(self):
        return f"<Company {self.name} main={self.is_main_company}>"
