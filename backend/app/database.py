from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
from .core.config import get_settings

settings = get_settings()

_is_postgres = settings.DATABASE_URL.startswith("postgresql")
_connect_args: dict = {}
if _is_postgres:
    _connect_args = {
        "connect_timeout": 10,
        "options": "-c statement_timeout=30000",  # 30s max per query
    }

engine = create_engine(
    settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_pre_ping=True,
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
