"""Initial schema

Revision ID: 0001
Revises:
Create Date: 2026-06-28

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable UUID extension
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')

    # companies
    op.create_table(
        "companies",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("short_name", sa.String(50), nullable=True),
        sa.Column("is_main_company", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("logo_path", sa.String(500), nullable=True),
        sa.Column("card_background_colour", sa.String(7), nullable=True),
        sa.Column("card_text_colour", sa.String(7), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # app_users
    op.create_table(
        "app_users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("display_name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(200), nullable=False),
        sa.Column("role", sa.Enum("super_admin", "hr_admin", "it_admin", "manager", name="userrole"), nullable=False),
        sa.Column("mfa_secret", sa.String(200), nullable=True),
        sa.Column("mfa_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("last_login", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_login_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("department_scope", sa.String(200), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_app_users_email", "app_users", ["email"])

    # id_prefixes
    op.create_table(
        "id_prefixes",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("prefix", sa.String(10), nullable=False, unique=True),
        sa.Column("label", sa.String(100), nullable=False),
        sa.Column("applies_to", sa.Enum("employee", "contractor", name="persontype"), nullable=False),
        sa.Column("next_sequence", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # people
    op.create_table(
        "people",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("person_type", sa.Enum("employee", "contractor", name="persontype"), nullable=False),
        sa.Column("employee_id", sa.String(20), nullable=False, unique=True),
        sa.Column("nfc_uid", sa.String(50), nullable=True, unique=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(200), nullable=False, unique=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("photo_path", sa.String(500), nullable=True),
        sa.Column("job_title", sa.String(200), nullable=False),
        sa.Column("department", sa.String(200), nullable=False),
        sa.Column("floor", sa.String(50), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.Enum("active", "inactive", "pending", "suspended", name="personstatus"), nullable=False, server_default="pending"),
        sa.Column("company_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("companies.id"), nullable=False),
        sa.Column("prefix_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("id_prefixes.id"), nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_people_employee_id", "people", ["employee_id"])
    op.create_index("ix_people_email", "people", ["email"])
    op.create_index("ix_people_nfc_uid", "people", ["nfc_uid"])

    # contracts
    op.create_table(
        "contracts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("contract_type", sa.Enum("employee_5yr", "contractor_6mo", name="contracttype"), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("renewal_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("renewed_from", postgresql.UUID(as_uuid=True), sa.ForeignKey("contracts.id"), nullable=True),
        sa.Column("renewed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_contracts_is_current", "contracts", ["is_current"])
    op.create_index("ix_contracts_end_date", "contracts", ["end_date"])

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=True),
        sa.Column("target_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("detail", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(50), nullable=True),
        sa.Column("user_agent", sa.String(500), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_audit_log_action", "audit_log", ["action"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])
    op.create_index("ix_audit_log_target", "audit_log", ["target_type", "target_id"])

    # import_jobs
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("source_type", sa.Enum("csv", "xlsx", "docx", "outlook_email", "manual", name="importsource"), nullable=False),
        sa.Column("filename", sa.String(500), nullable=True),
        sa.Column("status", sa.Enum("pending", "processing", "review", "completed", "failed", "cancelled", name="importstatus"), nullable=False, server_default="pending"),
        sa.Column("records_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_imported", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("records_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("preview_data", postgresql.JSONB(), nullable=True),
        sa.Column("errors", postgresql.JSONB(), nullable=True),
        sa.Column("started_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # card_events
    op.create_table(
        "card_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id"), nullable=False),
        sa.Column("event_type", sa.Enum("scan", "encode", "print", "reprint", "revoke", name="cardeventtype"), nullable=False),
        sa.Column("nfc_uid", sa.String(50), nullable=True),
        sa.Column("performed_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("device_id", sa.String(100), nullable=True),
        sa.Column("result", sa.String(50), nullable=True),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_card_events_person_id", "card_events", ["person_id"])
    op.create_index("ix_card_events_timestamp", "card_events", ["timestamp"])

    # Seed default ID prefixes (populated after first super_admin is created via setup wizard)
    op.execute("""
        INSERT INTO id_prefixes (id, prefix, label, applies_to, next_sequence, is_active, created_at, updated_at)
        VALUES
            (uuid_generate_v4(), 'DIR', 'Director',         'employee',   1, true, NOW(), NOW()),
            (uuid_generate_v4(), 'MGR', 'Manager',          'employee',   1, true, NOW(), NOW()),
            (uuid_generate_v4(), 'ENG', 'Engineer',         'employee',   1, true, NOW(), NOW()),
            (uuid_generate_v4(), 'HR',  'Human Resources',  'employee',   1, true, NOW(), NOW()),
            (uuid_generate_v4(), 'ADM', 'Admin',            'employee',   1, true, NOW(), NOW()),
            (uuid_generate_v4(), 'CTR', 'Contractor',       'contractor', 1, true, NOW(), NOW())
    """)


def downgrade() -> None:
    op.drop_table("card_events")
    op.drop_table("import_jobs")
    op.drop_table("audit_log")
    op.drop_table("contracts")
    op.drop_table("people")
    op.drop_table("id_prefixes")
    op.drop_table("app_users")
    op.drop_table("companies")
    op.execute("DROP TYPE IF EXISTS cardeventtype")
    op.execute("DROP TYPE IF EXISTS importstatus")
    op.execute("DROP TYPE IF EXISTS importsource")
    op.execute("DROP TYPE IF EXISTS contracttype")
    op.execute("DROP TYPE IF EXISTS personstatus")
    op.execute("DROP TYPE IF EXISTS persontype")
    op.execute("DROP TYPE IF EXISTS userrole")
