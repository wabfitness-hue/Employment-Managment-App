# Security Hardening Checklist

Status: ✅ = implemented, ⚙️ = requires ops/deployment action, 🔲 = future phase

---

## Authentication & Session

| # | Control | Status | Notes |
|---|---------|--------|-------|
| 1 | Passwords hashed with bcrypt (cost 12) | ✅ | `passlib[bcrypt]` |
| 2 | Password policy enforced (12+ chars, upper/lower/digit/special) | ✅ | `security.py: password_meets_policy()` |
| 3 | MFA mandatory — TOTP via pyotp | ✅ | All app users; enforced in `get_current_user` dependency |
| 4 | JWT access tokens (60 min), refresh tokens (7 days) | ✅ | Separate secrets for each |
| 5 | Pre-MFA token cannot access protected routes | ✅ | `mfa_verified` claim checked in dependency |
| 6 | Account lockout after 5 failed attempts (15-min window) | ✅ | In-memory rate limiter keyed on ip+email |
| 7 | Timing-safe password check (dummy hash when user not found) | ✅ | Fixed Phase 11 — prevents email enumeration via timing |
| 8 | Login error does not reveal remaining attempt count | ✅ | Fixed Phase 11 — generic "Invalid email or password" |
| 9 | Refresh token rotation (new refresh on each use) | ✅ | `auth.py: refresh_token()` |
| 10 | MFA secret stored immediately; enabled only after TOTP verified | ✅ | Two-step: `/mfa/setup` then `/mfa/enable` |

---

## Secrets & Configuration

| # | Control | Status | Notes |
|---|---------|--------|-------|
| 11 | No hardcoded secrets in source code | ✅ | All from `.env` via pydantic-settings |
| 12 | App refuses to start with default `SECRET_KEY` or `JWT_SECRET_KEY` | ✅ | Fixed Phase 11 — `field_validator` calls `sys.exit(1)` |
| 13 | Secrets minimum 32 chars enforced at startup | ✅ | Same validator |
| 14 | Outlook OAuth tokens encrypted at rest (Fernet/AES-128-CBC) | ✅ | `token_store.py` |
| 15 | `.env` file not committed to version control | ⚙️ | Confirm `.env` is in `.gitignore` |
| 16 | Separate `SECRET_KEY` and `JWT_SECRET_KEY` | ✅ | Rotating one doesn't compromise the other |

**Generate strong secrets:**
```bash
python -c "import secrets; print(secrets.token_hex(64))"
```
Run twice — once for `SECRET_KEY`, once for `JWT_SECRET_KEY`.

---

## Network & Transport

| # | Control | Status | Notes |
|---|---------|--------|-------|
| 17 | HTTPS enforced in production (HSTS header set) | ✅ | `Strict-Transport-Security: max-age=31536000` |
| 18 | CORS origins loaded from `CORS_ORIGINS` env var | ✅ | Fixed Phase 11 — no more hardcoded localhost |
| 19 | Production `CORS_ORIGINS` must not include `localhost` | ⚙️ | Set `CORS_ORIGINS=https://yourdomain.com` in prod `.env` |
| 20 | X-Forwarded-For only trusted from `TRUSTED_PROXY_IPS` | ✅ | Fixed Phase 11 — prevents rate-limit bypass via header spoofing |
| 21 | Bridge agent WebSocket uses shared secret auth (HMAC constant-time compare) | ✅ | `bridge_agent/protocol.py: verify_secret()` |
| 22 | Bridge agent secret set via env file, not source | ✅ | `bridge_agent/bridge_agent.env` |

---

## HTTP Security Headers

All set by `SecurityHeadersMiddleware` in `main.py`:

| Header | Value |
|--------|-------|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `X-XSS-Protection` | `1; mode=block` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Content-Security-Policy` | `default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; connect-src 'self' ws://localhost:8765` |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` |
| `Cache-Control` | `no-store` |

---

## Input Validation & File Uploads

| # | Control | Status | Notes |
|---|---------|--------|-------|
| 23 | Magic byte validation on photos (not extension-based) | ✅ | `photos/validation.py` — checks JPEG/PNG/WebP file signatures |
| 24 | Photo size limit (5 MB default) | ✅ | Checked before processing |
| 25 | Photos stored outside web root | ✅ | `PHOTO_STORAGE_PATH=/app/photos` — not under `static/` |
| 26 | Photo filenames are UUID-based (no user input in path) | ✅ | `storage.py: save_photo()` uses `person_id` UUID |
| 27 | Pillow re-encodes photos (strips EXIF/metadata) | ✅ | Square crop → 400×400 → JPEG re-save removes metadata |
| 28 | Import file magic byte check (xlsx/docx) | ✅ | `imports.py` validates PK header for zip-based formats |
| 29 | Import file size limit (10 MB) | ✅ | `imports.py` |
| 30 | All API request bodies validated via Pydantic schemas | ✅ | FastAPI enforces automatically |
| 31 | SQL injection prevention — SQLAlchemy ORM only, no raw queries | ✅ | All DB access through ORM |

---

## API Design

| # | Control | Status | Notes |
|---|---------|--------|-------|
| 32 | API docs (`/docs`, `/redoc`, `/openapi.json`) disabled in production | ✅ | `docs_url=None` when `DEBUG=False` |
| 33 | Role-based access control on all routes | ✅ | `require_super_admin`, `require_hr_or_above`, `require_any_role` dependencies |
| 34 | Audit log written for all sensitive actions | ✅ | `core/audit.py: log_action()` — login, MFA events, user create/deactivate, password change, card print, NFC assign |
| 35 | Health endpoint returns no sensitive data | ✅ | Only `{"status":"ok","version":"..."}` |
| 36 | 404 returned for non-existent resources (no info leak) | ✅ | Standard FastAPI HTTPException handling |

---

## Deployment (Docker)

| # | Control | Status | Notes |
|---|---------|--------|-------|
| 37 | Backend container runs as non-root user | ⚙️ | Add `USER appuser` to Dockerfile (Phase 12) |
| 38 | Database password set via env var, not compose defaults | ⚙️ | Set `POSTGRES_PASSWORD` in production `.env` |
| 39 | Redis not exposed on host network | ⚙️ | Use internal Docker network only |
| 40 | Nginx terminates TLS; backend never sees raw internet traffic | ⚙️ | Planned in Phase 12 |
| 41 | Container images pinned to specific digest versions | ⚙️ | Avoids supply-chain tag-squatting |
| 42 | `DEBUG=False` in production `.env` | ⚙️ | Required — disables API docs and stack traces in responses |

---

## Operational

| # | Control | Status | Notes |
|---|---------|--------|-------|
| 43 | Token refresh failure logged (not silently swallowed) | ✅ | Fixed Phase 11 — `logger.warning(...)` before returning None |
| 44 | Failed login attempts logged with IP | ✅ | `log_action("login_failed", ...)` |
| 45 | MFA events logged (setup, enable, fail, success) | ✅ | Audit log entries for all MFA states |
| 46 | Bridge agent secret rotation procedure | ⚙️ | Update `BRIDGE_SECRET` in `bridge_agent.env` and restart both agent and backend |

---

## Known Acceptable Trade-offs

- **Outlook key derivation**: The Fernet key for Outlook token encryption is derived from `SECRET_KEY`. This is intentional — rotating `SECRET_KEY` forces all users to re-authenticate with Outlook, which is the correct security behaviour on a key compromise. No separate KMS is required for a local-deploy system.

- **In-memory rate limiting**: The rate limiter uses a process-local dict. In a single-worker Docker deployment this is fine. If multiple uvicorn workers are used in future, switch to Redis-backed rate limiting via `slowapi`.

- **WebSocket over `ws://`**: The bridge agent listens on `127.0.0.1:8765` (loopback only). Traffic never leaves the host machine, so plaintext `ws://` is acceptable. The shared-secret auth layer still prevents unauthorised NFC/printer access from other local processes.

---

## Pre-Production Checklist

Before going live, complete every ⚙️ item above, then:

```
[ ] Set SECRET_KEY (64+ hex chars, generated fresh)
[ ] Set JWT_SECRET_KEY (64+ hex chars, different from SECRET_KEY)
[ ] Set CORS_ORIGINS=https://yourdomain.com (no localhost)
[ ] Set TRUSTED_PROXY_IPS to Nginx container IP
[ ] Set DATABASE_URL to PostgreSQL connection string
[ ] Set POSTGRES_PASSWORD to a strong random value
[ ] Set DEBUG=False
[ ] Confirm .env is in .gitignore and not committed
[ ] Confirm PHOTO_STORAGE_PATH is on a persistent volume
[ ] Confirm bridge agent BRIDGE_SECRET is set and non-empty
[ ] Test that /api/docs returns 404 in production mode
[ ] Test that login with wrong password gives no timing hint
[ ] Run `docker compose up` and verify health endpoint
```
