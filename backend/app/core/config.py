import sys
from functools import lru_cache
from pydantic import ConfigDict, field_validator
from pydantic_settings import BaseSettings

_DEV_SECRET = "dev-secret-key-change-in-production-min-64-chars-xxxxxxxxxxxxxxxxx"
_DEV_JWT    = "dev-jwt-secret-change-in-production-min-64-chars-xxxxxxxxxxxxxxxxx"


def _is_test_env() -> bool:
    return "pytest" in sys.modules or "unittest" in sys.modules


def _abort(msg: str) -> None:
    print(f"\n[STARTUP ERROR] {msg}\n", file=sys.stderr)
    sys.exit(1)


class Settings(BaseSettings):
    model_config = ConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

    # App
    APP_NAME: str = "Employee Management System"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    SECRET_KEY: str = _DEV_SECRET
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]
    # Comma-separated IPs of trusted reverse proxies (Nginx container).
    # X-Forwarded-For is only trusted when the direct TCP client is in this list.
    TRUSTED_PROXY_IPS: str = "127.0.0.1"
    # Comma-separated allowed CORS origins — override in .env for production
    CORS_ORIGINS: str = "http://localhost,http://localhost:3000"

    @property
    def trusted_proxy_list(self) -> list[str]:
        return [ip.strip() for ip in self.TRUSTED_PROXY_IPS.split(",") if ip.strip()]

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]

    # Database
    DATABASE_URL: str = "sqlite:///./test.db"
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # Redis
    REDIS_URL: str = "redis://redis:6379/0"

    # JWT
    JWT_SECRET_KEY: str = _DEV_JWT
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # Security
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_MINUTES: int = 15
    SESSION_IDLE_TIMEOUT_MINUTES: int = 60
    MFA_ISSUER: str = "EmployeeManagementSystem"

    # File storage
    PHOTO_STORAGE_PATH: str = "/app/photos"
    MAX_PHOTO_SIZE_MB: int = 5
    ALLOWED_PHOTO_TYPES: list[str] = ["image/jpeg", "image/png", "image/webp"]

    # Microsoft Graph (Outlook)
    MS_CLIENT_ID: str = ""
    MS_CLIENT_SECRET: str = ""
    MS_TENANT_ID: str = "consumers"
    MS_REDIRECT_URI: str = "http://localhost/auth/outlook/callback"
    MS_SCOPES: list[str] = ["Mail.Read", "User.Read"]

    # Card printer bridge
    BRIDGE_AGENT_URL: str = "ws://localhost:8765"
    BRIDGE_AGENT_SECRET: str = ""

    # Contract alerts
    ALERT_DAYS_BEFORE_EXPIRY: list[int] = [90, 60, 30, 14, 7]
    ALERT_EMAIL_FROM: str = ""
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    @field_validator("SECRET_KEY")
    @classmethod
    def _validate_secret_key(cls, v: str) -> str:
        if not _is_test_env():
            if v == _DEV_SECRET:
                _abort("SECRET_KEY is the insecure default. Set a strong random value in .env")
            if len(v) < 32:
                _abort("SECRET_KEY must be at least 32 characters.")
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def _validate_jwt_key(cls, v: str) -> str:
        if not _is_test_env():
            if v == _DEV_JWT:
                _abort("JWT_SECRET_KEY is the insecure default. Set a strong random value in .env")
            if len(v) < 32:
                _abort("JWT_SECRET_KEY must be at least 32 characters.")
        return v

    @field_validator("CORS_ORIGINS")
    @classmethod
    def _validate_cors_origins(cls, v: str) -> str:
        if not _is_test_env():
            origins = [o.strip() for o in v.split(",") if o.strip()]
            if "*" in origins:
                _abort("CORS_ORIGINS cannot include '*' — this would allow any site to make authenticated requests.")
        return v


@lru_cache()
def get_settings() -> Settings:
    return Settings()
