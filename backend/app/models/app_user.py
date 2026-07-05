import enum
from sqlalchemy import Column, String, Enum, Boolean, DateTime, Integer, ForeignKey
from sqlalchemy.orm import relationship
from .base import Base, UUIDMixin, TimestampMixin, UUIDType


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    hr_admin = "hr_admin"
    it_admin = "it_admin"
    manager = "manager"


class AppUser(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "app_users"

    email = Column(String(200), nullable=False, unique=True, index=True)
    display_name = Column(String(200), nullable=False)
    password_hash = Column(String(200), nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.manager)

    mfa_secret = Column(String(200), nullable=True)
    mfa_enabled = Column(Boolean, default=False, nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    last_login = Column(DateTime(timezone=True), nullable=True)
    failed_login_count = Column(Integer, default=0, nullable=False)

    created_by = Column(UUIDType(), ForeignKey("app_users.id"), nullable=True)
    department_scope = Column(String(200), nullable=True)

    creator = relationship("AppUser", remote_side="AppUser.id", foreign_keys=[created_by])

    def __repr__(self):
        return f"<AppUser {self.email} role={self.role}>"
