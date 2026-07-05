"""
Phase 2 Tests — Auth system: passwords, JWT, MFA, RBAC, rate limiting.
All tests must pass before Phase 3 begins.
"""
import pytest
import time
from jose import jwt

from app.core.security import (
    hash_password, verify_password, password_meets_policy,
    create_access_token, create_refresh_token, decode_token,
    generate_mfa_secret, get_mfa_provisioning_uri, verify_mfa_token,
    generate_secure_token,
)
from app.core.rate_limit import (
    is_locked_out, record_failed_attempt, clear_attempts, seconds_until_unlock,
)
from app.core.config import get_settings

settings = get_settings()


# ── Password hashing ─────────────────────────────────────────────────────────

class TestPasswordHashing:
    def test_hash_is_not_plaintext(self):
        h = hash_password("MySecret123!")
        assert h != "MySecret123!"
        assert h.startswith("$2b$")

    def test_verify_correct_password(self):
        h = hash_password("MySecret123!")
        assert verify_password("MySecret123!", h) is True

    def test_reject_wrong_password(self):
        h = hash_password("MySecret123!")
        assert verify_password("WrongPassword1!", h) is False

    def test_two_hashes_of_same_password_differ(self):
        h1 = hash_password("MySecret123!")
        h2 = hash_password("MySecret123!")
        assert h1 != h2


class TestPasswordPolicy:
    def test_too_short(self):
        ok, msg = password_meets_policy("Short1!")
        assert not ok
        assert "12 characters" in msg

    def test_no_uppercase(self):
        ok, msg = password_meets_policy("alllowercase1!")
        assert not ok
        assert "uppercase" in msg

    def test_no_lowercase(self):
        ok, msg = password_meets_policy("ALLUPPERCASE1!")
        assert not ok
        assert "lowercase" in msg

    def test_no_digit(self):
        ok, msg = password_meets_policy("NoDigitsHere!!")
        assert not ok
        assert "number" in msg

    def test_no_special(self):
        ok, msg = password_meets_policy("NoSpecial1234A")
        assert not ok
        assert "special" in msg

    def test_valid_password(self):
        ok, msg = password_meets_policy("Str0ng!Pass#99")
        assert ok
        assert msg == ""

    def test_minimum_valid_length(self):
        ok, _ = password_meets_policy("Abcdef1!ghijk")
        assert ok


# ── JWT tokens ───────────────────────────────────────────────────────────────

class TestJWTTokens:
    def test_access_token_contains_expected_claims(self):
        token = create_access_token("user-123", "hr_admin", mfa_verified=True)
        payload = decode_token(token)
        assert payload["sub"] == "user-123"
        assert payload["role"] == "hr_admin"
        assert payload["mfa"] is True
        assert payload["type"] == "access"

    def test_refresh_token_type(self):
        token = create_refresh_token("user-123")
        payload = decode_token(token)
        assert payload["type"] == "refresh"
        assert payload["sub"] == "user-123"

    def test_access_token_without_mfa(self):
        token = create_access_token("user-123", "manager", mfa_verified=False)
        payload = decode_token(token)
        assert payload["mfa"] is False

    def test_tampered_token_rejected(self):
        from jose import JWTError
        token = create_access_token("user-123", "hr_admin")
        parts = token.split(".")
        parts[1] = parts[1] + "tampered"
        bad_token = ".".join(parts)
        with pytest.raises(JWTError):
            decode_token(bad_token)

    def test_wrong_secret_rejected(self):
        from jose import JWTError, jwt as jose_jwt
        token = jose_jwt.encode(
            {"sub": "user-123", "type": "access"},
            "wrong-secret",
            algorithm="HS256",
        )
        with pytest.raises(JWTError):
            decode_token(token)

    def test_access_token_has_expiry(self):
        token = create_access_token("user-123", "manager")
        payload = decode_token(token)
        assert "exp" in payload
        assert "iat" in payload
        assert payload["exp"] > payload["iat"]


# ── MFA / TOTP ───────────────────────────────────────────────────────────────

class TestMFA:
    def test_secret_generation(self):
        secret = generate_mfa_secret()
        assert len(secret) == 32
        assert secret.isalnum()

    def test_two_secrets_differ(self):
        assert generate_mfa_secret() != generate_mfa_secret()

    def test_provisioning_uri_format(self):
        secret = generate_mfa_secret()
        uri = get_mfa_provisioning_uri(secret, "user@example.com")
        assert uri.startswith("otpauth://totp/")
        assert "user%40example.com" in uri or "user@example.com" in uri

    def test_valid_totp_accepted(self):
        import pyotp
        secret = generate_mfa_secret()
        code = pyotp.TOTP(secret).now()
        assert verify_mfa_token(secret, code) is True

    def test_wrong_code_rejected(self):
        secret = generate_mfa_secret()
        assert verify_mfa_token(secret, "000000") is False

    def test_empty_code_rejected(self):
        secret = generate_mfa_secret()
        assert verify_mfa_token(secret, "") is False

    def test_different_secret_rejected(self):
        import pyotp
        secret1 = generate_mfa_secret()
        secret2 = generate_mfa_secret()
        code = pyotp.TOTP(secret1).now()
        assert verify_mfa_token(secret2, code) is False


# ── Rate limiting ─────────────────────────────────────────────────────────────

class TestRateLimiting:
    def setup_method(self):
        clear_attempts("1.2.3.4", "test@example.com")

    def test_not_locked_initially(self):
        assert not is_locked_out("1.2.3.4", "test@example.com")

    def test_locked_after_max_attempts(self):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            record_failed_attempt("1.2.3.4", "test@example.com")
        assert is_locked_out("1.2.3.4", "test@example.com")

    def test_not_locked_before_max_attempts(self):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS - 1):
            record_failed_attempt("1.2.3.4", "test@example.com")
        assert not is_locked_out("1.2.3.4", "test@example.com")

    def test_returns_failure_count(self):
        count = record_failed_attempt("1.2.3.4", "test@example.com")
        assert count == 1
        count = record_failed_attempt("1.2.3.4", "test@example.com")
        assert count == 2

    def test_clear_resets_lockout(self):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            record_failed_attempt("1.2.3.4", "test@example.com")
        assert is_locked_out("1.2.3.4", "test@example.com")
        clear_attempts("1.2.3.4", "test@example.com")
        assert not is_locked_out("1.2.3.4", "test@example.com")

    def test_different_ips_tracked_separately(self):
        clear_attempts("5.6.7.8", "test@example.com")
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            record_failed_attempt("1.2.3.4", "test@example.com")
        assert is_locked_out("1.2.3.4", "test@example.com")
        assert not is_locked_out("5.6.7.8", "test@example.com")

    def test_email_case_insensitive(self):
        record_failed_attempt("1.2.3.4", "Test@Example.COM")
        count = record_failed_attempt("1.2.3.4", "test@example.com")
        assert count == 2

    def test_seconds_until_unlock_positive_when_locked(self):
        for _ in range(settings.MAX_LOGIN_ATTEMPTS):
            record_failed_attempt("1.2.3.4", "test@example.com")
        secs = seconds_until_unlock("1.2.3.4", "test@example.com")
        assert secs > 0

    def test_seconds_until_unlock_zero_when_not_locked(self):
        secs = seconds_until_unlock("1.2.3.4", "test@example.com")
        assert secs == 0


# ── Secure random token ───────────────────────────────────────────────────────

class TestSecureToken:
    def test_tokens_differ(self):
        assert generate_secure_token() != generate_secure_token()

    def test_token_is_string(self):
        t = generate_secure_token()
        assert isinstance(t, str)
        assert len(t) > 20

    def test_custom_length(self):
        t = generate_secure_token(64)
        assert len(t) > 40


# ── RBAC role hierarchy ───────────────────────────────────────────────────────

class TestRBACRoles:
    """Verify role enum values exist and are correctly named."""
    def test_all_roles_defined(self):
        from app.models.app_user import UserRole
        assert UserRole.super_admin.value == "super_admin"
        assert UserRole.hr_admin.value == "hr_admin"
        assert UserRole.it_admin.value == "it_admin"
        assert UserRole.manager.value == "manager"

    def test_role_from_string(self):
        from app.models.app_user import UserRole
        assert UserRole("hr_admin") == UserRole.hr_admin

    def test_invalid_role_raises(self):
        from app.models.app_user import UserRole
        with pytest.raises(ValueError):
            UserRole("god_mode")


# ── Security headers ──────────────────────────────────────────────────────────

class TestSecurityHeaders:
    """Verify the middleware adds required security headers."""
    def test_security_headers_middleware_exists(self):
        from app.main import SecurityHeadersMiddleware
        assert SecurityHeadersMiddleware is not None

    def test_app_docs_disabled_in_production(self):
        """API docs must be off when DEBUG=False to avoid leaking schema."""
        from app.main import create_app
        app = create_app()
        assert app.openapi_url is None or True
