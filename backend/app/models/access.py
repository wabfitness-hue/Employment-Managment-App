"""
Access control models.

AccessZone      — a physical area in the building (door, floor, room)
AccessProfile   — a named set of zones, linked to an IdPrefix as its default
AccessProfileZone — which zones belong to a profile (many-to-many)
PersonAccess    — the access assignment for one person, with optional
                  time/day restrictions (contractors) and zone overrides
PersonAccessZone — individual zone overrides added on top of the profile
"""
import enum
from sqlalchemy import (
    Column, String, Enum, ForeignKey, Boolean, Integer,
    Time, CheckConstraint, UniqueConstraint,
)
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin, UUIDType


class DayOfWeek(str, enum.Enum):
    monday = "monday"
    tuesday = "tuesday"
    wednesday = "wednesday"
    thursday = "thursday"
    friday = "friday"
    saturday = "saturday"
    sunday = "sunday"


class ZoneAccessType(str, enum.Enum):
    grant = "grant"
    deny = "deny"


class AccessZone(Base, UUIDMixin, TimestampMixin):
    """A physical area — front door, floor, server room, etc."""
    __tablename__ = "access_zones"

    code = Column(String(50), nullable=False, unique=True)
    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    floor = Column(String(50), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    sort_order = Column(Integer, default=0, nullable=False)

    created_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)
    creator = relationship("AppUser", foreign_keys=[created_by])
    profile_zones = relationship("AccessProfileZone", back_populates="zone", lazy="dynamic")
    person_zones = relationship("PersonAccessZone", back_populates="zone", lazy="dynamic")

    def __repr__(self):
        return f"<AccessZone {self.code} — {self.name}>"


class AccessProfile(Base, UUIDMixin, TimestampMixin):
    """
    A named access profile — e.g. 'Director Full Access', 'Contractor Ground Floor'.
    Linked to an IdPrefix so new people get it auto-assigned.
    """
    __tablename__ = "access_profiles"

    name = Column(String(200), nullable=False)
    description = Column(String(500), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    # When set, new people with this prefix get this profile automatically
    default_for_prefix_id = Column(
        UUIDType(), ForeignKey("id_prefixes.id"), nullable=True, unique=True
    )

    created_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)
    creator = relationship("AppUser", foreign_keys=[created_by])
    default_prefix = relationship("IdPrefix", foreign_keys=[default_for_prefix_id])
    profile_zones = relationship(
        "AccessProfileZone", back_populates="profile", cascade="all, delete-orphan"
    )
    person_assignments = relationship("PersonAccess", back_populates="profile", lazy="dynamic")

    def __repr__(self):
        return f"<AccessProfile {self.name}>"


class AccessProfileZone(Base, UUIDMixin):
    """Which zones belong to an AccessProfile."""
    __tablename__ = "access_profile_zones"
    __table_args__ = (
        UniqueConstraint("profile_id", "zone_id", name="uq_profile_zone"),
    )

    profile_id = Column(UUIDType(), ForeignKey("access_profiles.id"), nullable=False)
    zone_id = Column(UUIDType(), ForeignKey("access_zones.id"), nullable=False)

    profile = relationship("AccessProfile", back_populates="profile_zones")
    zone = relationship("AccessZone", back_populates="profile_zones")


class PersonAccess(Base, UUIDMixin, TimestampMixin):
    """
    The access assignment for one person.
    - profile_id      : the base profile (auto-assigned from prefix, or HR-chosen)
    - has_time_restriction : True for contractors — enforces allowed_days + time window
    - allowed_days    : comma-separated DayOfWeek values e.g. "monday,tuesday,wednesday"
    - access_start    : earliest time of day access is permitted  e.g. 08:00
    - access_end      : latest time of day access is permitted    e.g. 18:00
    Individual zone overrides (PersonAccessZone) are added on top of the profile.
    """
    __tablename__ = "person_access"

    person_id = Column(UUIDType(), ForeignKey("people.id"), nullable=False, unique=True)
    profile_id = Column(UUIDType(), ForeignKey("access_profiles.id"), nullable=False)

    # Time restrictions — contractors only
    has_time_restriction = Column(Boolean, default=False, nullable=False)
    allowed_days = Column(String(200), nullable=True)   # e.g. "monday,tuesday,wednesday,thursday,friday"
    access_start = Column(Time, nullable=True)           # e.g. 08:00
    access_end = Column(Time, nullable=True)             # e.g. 18:00

    is_active = Column(Boolean, default=True, nullable=False)
    assigned_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)

    person = relationship("Person", foreign_keys=[person_id])
    profile = relationship("AccessProfile", back_populates="person_assignments")
    assigner = relationship("AppUser", foreign_keys=[assigned_by])
    zone_overrides = relationship(
        "PersonAccessZone", back_populates="person_access", cascade="all, delete-orphan"
    )

    @property
    def allowed_days_list(self) -> list[str]:
        if not self.allowed_days:
            return []
        return [d.strip() for d in self.allowed_days.split(",")]

    @allowed_days_list.setter
    def allowed_days_list(self, days: list[str]) -> None:
        self.allowed_days = ",".join(days)

    def is_allowed_on_day(self, day: DayOfWeek) -> bool:
        if not self.has_time_restriction:
            return True
        return day.value in self.allowed_days_list

    def __repr__(self):
        return f"<PersonAccess person={self.person_id} profile={self.profile_id}>"


class PersonAccessZone(Base, UUIDMixin):
    """
    Individual zone override for a person — adds or removes a specific zone
    on top of what their profile grants. HR uses this for one-off exceptions.
    """
    __tablename__ = "person_access_zones"
    __table_args__ = (
        UniqueConstraint("person_access_id", "zone_id", name="uq_person_access_zone"),
    )

    person_access_id = Column(UUIDType(), ForeignKey("person_access.id"), nullable=False)
    zone_id = Column(UUIDType(), ForeignKey("access_zones.id"), nullable=False)
    access_type = Column(
        Enum(ZoneAccessType),
        default=ZoneAccessType.grant,
        nullable=False,
    )
    reason = Column(String(500), nullable=True)
    added_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)

    person_access = relationship("PersonAccess", back_populates="zone_overrides")
    zone = relationship("AccessZone", back_populates="person_zones")
    adder = relationship("AppUser", foreign_keys=[added_by])

    def __repr__(self):
        return f"<PersonAccessZone {self.access_type} zone={self.zone_id}>"
