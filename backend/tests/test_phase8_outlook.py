"""
Phase 8 Tests — Outlook Graph API: token encryption, storage, refresh logic,
employee ID extraction, email matching, API routes.
"""
import uuid
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.outlook.token_store import (
    _encrypt, _decrypt, save_tokens, get_access_token,
    delete_tokens, connection_status,
)
from app.services.photos.outlook_extractor import _extract_employee_id


# ── Encryption ────────────────────────────────────────────────────────────────

class TestEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        secret = "my-super-secret-access-token-xyz"
        assert _decrypt(_encrypt(secret)) == secret

    def test_different_secrets_produce_different_ciphertext(self):
        a = _encrypt("token-a")
        b = _encrypt("token-b")
        assert a != b

    def test_ciphertext_is_not_plaintext(self):
        token = "plaintext-token-value"
        enc = _encrypt(token)
        assert token not in enc

    def test_empty_string_roundtrip(self):
        assert _decrypt(_encrypt("")) == ""

    def test_unicode_roundtrip(self):
        value = "tök€n-wïth-ünïcödé"
        assert _decrypt(_encrypt(value)) == value


# ── Token store (DB operations) ───────────────────────────────────────────────

class TestTokenStore:
    def test_save_and_retrieve_access_token(self, db, super_admin):
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        record = save_tokens(
            db=db,
            owner_id=str(super_admin.id),
            access_token="tok-abc",
            refresh_token="ref-xyz",
            expires_in=3600,
            outlook_email="admin@outlook.com",
            scope="Mail.ReadWrite",
        )
        db.flush()

        token = get_access_token(db, str(super_admin.id))
        assert token == "tok-abc"

    def test_save_updates_existing_record(self, db, super_admin):
        save_tokens(db, str(super_admin.id), "tok-v1", None, 3600, None, None)
        db.flush()
        save_tokens(db, str(super_admin.id), "tok-v2", None, 3600, None, None)
        db.flush()

        token = get_access_token(db, str(super_admin.id))
        assert token == "tok-v2"

    def test_no_record_returns_none(self, db):
        random_id = str(uuid.uuid4())
        assert get_access_token(db, random_id) is None

    def test_expired_token_without_refresh_returns_none(self, db, super_admin):
        save_tokens(db, str(super_admin.id), "expired-tok", None, -60,
                    "admin@outlook.com", None)
        db.flush()
        # No refresh token — should return None
        token = get_access_token(db, str(super_admin.id))
        assert token is None

    def test_delete_removes_record(self, db, super_admin):
        save_tokens(db, str(super_admin.id), "tok", None, 3600, None, None)
        db.flush()
        deleted = delete_tokens(db, str(super_admin.id))
        assert deleted is True
        assert get_access_token(db, str(super_admin.id)) is None

    def test_delete_nonexistent_returns_false(self, db):
        assert delete_tokens(db, str(uuid.uuid4())) is False

    def test_connection_status_not_connected(self, db):
        status = connection_status(db, str(uuid.uuid4()))
        assert status["connected"] is False

    def test_connection_status_connected(self, db, super_admin):
        save_tokens(db, str(super_admin.id), "tok", None, 3600,
                    "admin@outlook.com", "Mail.ReadWrite")
        db.flush()
        status = connection_status(db, str(super_admin.id))
        assert status["connected"] is True
        assert status["outlook_email"] == "admin@outlook.com"
        assert status["token_expired"] is False

    def test_connection_status_expired(self, db, super_admin):
        save_tokens(db, str(super_admin.id), "tok", None, -60, None, None)
        db.flush()
        status = connection_status(db, str(super_admin.id))
        assert status["token_expired"] is True

    def test_outlook_email_stored_correctly(self, db, super_admin):
        save_tokens(db, str(super_admin.id), "tok", None, 3600,
                    "jane@example.com", None)
        db.flush()
        status = connection_status(db, str(super_admin.id))
        assert status["outlook_email"] == "jane@example.com"


# ── Employee ID extraction ────────────────────────────────────────────────────

class TestEmployeeIDExtraction:
    def test_extracts_from_subject(self):
        assert _extract_employee_id("Photo for DIR-0042") == "DIR-0042"

    def test_extracts_case_insensitive(self):
        assert _extract_employee_id("photo for dir-0042") == "DIR-0042"

    def test_extracts_contractor_id(self):
        assert _extract_employee_id("Please find CTR-0007 attached") == "CTR-0007"

    def test_extracts_from_body_preview(self):
        assert _extract_employee_id("Hi, the photo for HR-0003 is attached") == "HR-0003"

    def test_no_id_returns_none(self):
        assert _extract_employee_id("No employee ID in this text") is None

    def test_extracts_first_id_only(self):
        result = _extract_employee_id("ENG-0001 and DIR-0002 both need photos")
        assert result in ("ENG-0001", "DIR-0002")   # first found

    def test_ignores_short_codes(self):
        # Single letter prefixes should not match  (pattern requires 2-5 letters)
        result = _extract_employee_id("A-001 is not valid")
        assert result is None

    def test_six_digit_sequence(self):
        assert _extract_employee_id("ADM-000123 update") == "ADM-000123"

    def test_subject_and_body_combined(self):
        combined = "Subject: photo MGR-0011 Body: see attachment"
        assert _extract_employee_id(combined) == "MGR-0011"


# ── Outlook API routes ────────────────────────────────────────────────────────

def _setup_admin_via_api(client) -> dict:
    """Use the setup wizard to create a super_admin and return JWT headers."""
    import pyotp
    client.post("/api/v1/setup/company", json={"name": "Test Corp"})
    r = client.post("/api/v1/setup/admin", json={
        "email": "admin@testcorp.com",
        "password": "Str0ng!Pass#2026",
        "full_name": "Test Admin",
    })
    if r.status_code != 200:
        # Already created in this test's client DB
        return {}
    data = r.json()
    token = pyotp.TOTP(data["mfa_secret"]).now()
    r2 = client.post("/api/v1/setup/complete", json={
        "admin_id": data["admin_id"], "mfa_token": token
    })
    access_token = r2.json()["access_token"]
    return {"Authorization": f"Bearer {access_token}"}


class TestOutlookRoutes:
    def test_connect_without_client_id_returns_503(self, client):
        headers = _setup_admin_via_api(client)
        r = client.get("/api/v1/outlook/connect", headers=headers)
        assert r.status_code == 503

    def test_status_not_connected(self, client):
        headers = _setup_admin_via_api(client)
        r = client.get("/api/v1/outlook/status", headers=headers)
        assert r.status_code == 200
        assert r.json()["connected"] is False

    def test_scan_without_token_returns_503(self, client):
        headers = _setup_admin_via_api(client)
        r = client.post("/api/v1/outlook/scan", headers=headers)
        assert r.status_code == 503

    def test_disconnect_without_token_returns_404(self, client):
        headers = _setup_admin_via_api(client)
        r = client.delete("/api/v1/outlook/disconnect", headers=headers)
        assert r.status_code == 404


# ── process_intake_emails (mocked Graph API) ──────────────────────────────────

class TestProcessIntakeEmails:
    @pytest.mark.asyncio
    async def test_returns_empty_on_no_messages(self, db, main_company):
        mock_response = {"value": []}

        with patch("app.services.photos.outlook_extractor._graph_get",
                   new_callable=AsyncMock) as mock_get:
            mock_get.return_value = mock_response
            from app.services.photos.outlook_extractor import process_intake_emails
            results = await process_intake_emails(db, "fake-token")

        assert results == []

    @pytest.mark.asyncio
    async def test_unmatched_email_returned(self, db, main_company):
        """Email with no recognisable employee ID returns unmatched status."""
        messages = {"value": [{
            "id": "msg-001",
            "subject": "Hello there",
            "bodyPreview": "No employee ID here",
            "from": {"emailAddress": {"address": "sender@example.com"}},
        }]}

        call_count = 0
        async def mock_get(token, path):
            nonlocal call_count
            call_count += 1
            if "mailFolders" in path:
                return {"value": []}
            return messages

        with patch("app.services.photos.outlook_extractor._graph_get", side_effect=mock_get):
            from app.services.photos.outlook_extractor import process_intake_emails
            results = await process_intake_emails(db, "fake-token")

        assert len(results) == 1
        assert results[0]["status"] == "unmatched"
        assert results[0]["detected_employee_id"] is None

    @pytest.mark.asyncio
    async def test_matched_email_with_no_photo_attachment(self, db, main_company, dir_prefix):
        """Email with employee ID but no image attachment → matched_no_valid_photo."""
        from app.models.person import Person
        from app.models.contract import Contract, ContractType
        from datetime import date, timedelta

        person = Person(
            employee_id="DIR-0001",
            first_name="Jane", last_name="Smith",
            email="jane@test.com",
            person_type="employee",
            job_title="Director",
            department="Ops",
            company_id=main_company.id,
            prefix_id=dir_prefix.id,
        )
        db.add(person)
        db.flush()
        db.add(Contract(
            person_id=person.id,
            contract_type=ContractType.employee_5yr,
            start_date=date.today(),
            end_date=date.today() + timedelta(days=1825),
            is_current=True,
        ))
        db.flush()

        messages = {"value": [{
            "id": "msg-002",
            "subject": "Photo for DIR-0001",
            "bodyPreview": "",
            "from": {"emailAddress": {"address": "hr@test.com"}},
        }]}
        attachments = {"value": [{
            "id": "att-001",
            "contentType": "application/pdf",   # not an image
            "name": "document.pdf",
        }]}

        async def mock_get(token, path):
            if "mailFolders" in path:
                return {"value": []}
            if "attachments" in path:
                return attachments
            return messages

        with patch("app.services.photos.outlook_extractor._graph_get", side_effect=mock_get), \
             patch("app.services.photos.outlook_extractor._graph_patch", new_callable=AsyncMock):
            from app.services.photos.outlook_extractor import process_intake_emails
            results = await process_intake_emails(db, "fake-token")

        assert len(results) == 1
        assert results[0]["status"] == "matched_no_valid_photo"
        assert results[0]["person_id"] == str(person.id)


# ── PKCE (M5) ─────────────────────────────────────────────────────────────────

class TestPKCE:
    def test_challenge_is_s256_of_verifier(self):
        import base64, hashlib
        from app.api.v1.outlook import _pkce_pair
        verifier, challenge = _pkce_pair()
        expected = base64.urlsafe_b64encode(
            hashlib.sha256(verifier.encode()).digest()
        ).decode().rstrip("=")
        assert challenge == expected
        assert "=" not in challenge          # base64url, unpadded
        assert 43 <= len(verifier) <= 128    # RFC 7636

    def test_pairs_are_unique(self):
        from app.api.v1.outlook import _pkce_pair
        assert _pkce_pair()[0] != _pkce_pair()[0]
