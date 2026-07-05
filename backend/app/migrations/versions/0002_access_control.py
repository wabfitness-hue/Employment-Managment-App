"""Access control — zones, profiles, time restrictions, person assignments

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-28

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:

    # access_zones
    op.create_table(
        "access_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("floor", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_access_zones_code", "access_zones", ["code"])

    # access_profiles
    op.create_table(
        "access_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("default_for_prefix_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("id_prefixes.id"), nullable=True, unique=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )

    # access_profile_zones (many-to-many: profile ↔ zone)
    op.create_table(
        "access_profile_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("access_profiles.id"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("access_zones.id"), nullable=False),
        sa.UniqueConstraint("profile_id", "zone_id", name="uq_profile_zone"),
    )

    # person_access
    op.create_table(
        "person_access",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("person_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("people.id"), nullable=False, unique=True),
        sa.Column("profile_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("access_profiles.id"), nullable=False),
        # Time restrictions for contractors
        sa.Column("has_time_restriction", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allowed_days", sa.String(200), nullable=True),
        sa.Column("access_start", sa.Time(), nullable=True),
        sa.Column("access_end", sa.Time(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("assigned_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
    )
    op.create_index("ix_person_access_person_id", "person_access", ["person_id"])

    # person_access_zones (individual zone overrides per person)
    op.create_table(
        "person_access_zones",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("uuid_generate_v4()")),
        sa.Column("person_access_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("person_access.id"), nullable=False),
        sa.Column("zone_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("access_zones.id"), nullable=False),
        sa.Column("access_type", sa.Enum("grant", "deny", name="zoneaccesstype"), nullable=False, server_default="grant"),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.Column("added_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("app_users.id"), nullable=True),
        sa.UniqueConstraint("person_access_id", "zone_id", name="uq_person_access_zone"),
    )

    # Seed default access zones
    op.execute("""
        INSERT INTO access_zones (id, code, name, description, floor, sort_order, is_active, created_at, updated_at)
        VALUES
            (uuid_generate_v4(), 'MAIN-ENTRANCE',  'Main Entrance',    'Front door / reception',          'G',  1,  true, NOW(), NOW()),
            (uuid_generate_v4(), 'FLOOR-1',        'Floor 1',          'Ground floor general access',     '1',  2,  true, NOW(), NOW()),
            (uuid_generate_v4(), 'FLOOR-2',        'Floor 2',          'Second floor office area',        '2',  3,  true, NOW(), NOW()),
            (uuid_generate_v4(), 'FLOOR-3',        'Floor 3',          'Third floor office area',         '3',  4,  true, NOW(), NOW()),
            (uuid_generate_v4(), 'HR-OFFICE',      'HR Office',        'Human Resources department',      '2',  5,  true, NOW(), NOW()),
            (uuid_generate_v4(), 'SERVER-ROOM',    'Server Room',      'IT infrastructure — restricted',  '1',  6,  true, NOW(), NOW()),
            (uuid_generate_v4(), 'BOARDROOM',      'Boardroom',        'Executive meeting room',          '3',  7,  true, NOW(), NOW()),
            (uuid_generate_v4(), 'CAR-PARK',       'Car Park',         'Staff car park barrier',          'G',  8,  true, NOW(), NOW())
    """)

    # Seed default access profiles (one per default ID prefix)
    # Directors get all zones; others get sensible defaults; contractors get entry only
    op.execute("""
        INSERT INTO access_profiles (id, name, description, is_active, created_at, updated_at)
        VALUES
            (uuid_generate_v4(), 'Director — Full Access',      'All areas, no time restriction',          true, NOW(), NOW()),
            (uuid_generate_v4(), 'Manager — Standard Access',   'All floors, boardroom, car park',         true, NOW(), NOW()),
            (uuid_generate_v4(), 'Engineer — Technical Access', 'Floors 1-3, server room, car park',       true, NOW(), NOW()),
            (uuid_generate_v4(), 'HR — HR Office Access',       'All floors, HR office, boardroom',        true, NOW(), NOW()),
            (uuid_generate_v4(), 'Admin — General Access',      'Floors 1-2, main entrance, car park',     true, NOW(), NOW()),
            (uuid_generate_v4(), 'Contractor — Entry Only',     'Main entrance and floor 1 only. Time and day restricted.', true, NOW(), NOW())
    """)

    # Link profiles to their prefix defaults
    op.execute("""
        UPDATE access_profiles ap
        SET default_for_prefix_id = ip.id
        FROM id_prefixes ip
        WHERE
            (ap.name = 'Director — Full Access'      AND ip.prefix = 'DIR') OR
            (ap.name = 'Manager — Standard Access'   AND ip.prefix = 'MGR') OR
            (ap.name = 'Engineer — Technical Access' AND ip.prefix = 'ENG') OR
            (ap.name = 'HR — HR Office Access'       AND ip.prefix = 'HR')  OR
            (ap.name = 'Admin — General Access'      AND ip.prefix = 'ADM') OR
            (ap.name = 'Contractor — Entry Only'     AND ip.prefix = 'CTR')
    """)

    # Assign zones to each profile
    op.execute("""
        INSERT INTO access_profile_zones (id, profile_id, zone_id)
        SELECT uuid_generate_v4(), ap.id, az.id
        FROM access_profiles ap
        CROSS JOIN access_zones az
        WHERE ap.name = 'Director — Full Access'
    """)

    op.execute("""
        INSERT INTO access_profile_zones (id, profile_id, zone_id)
        SELECT uuid_generate_v4(), ap.id, az.id
        FROM access_profiles ap, access_zones az
        WHERE ap.name = 'Manager — Standard Access'
        AND az.code IN ('MAIN-ENTRANCE','FLOOR-1','FLOOR-2','FLOOR-3','BOARDROOM','CAR-PARK')
    """)

    op.execute("""
        INSERT INTO access_profile_zones (id, profile_id, zone_id)
        SELECT uuid_generate_v4(), ap.id, az.id
        FROM access_profiles ap, access_zones az
        WHERE ap.name = 'Engineer — Technical Access'
        AND az.code IN ('MAIN-ENTRANCE','FLOOR-1','FLOOR-2','FLOOR-3','SERVER-ROOM','CAR-PARK')
    """)

    op.execute("""
        INSERT INTO access_profile_zones (id, profile_id, zone_id)
        SELECT uuid_generate_v4(), ap.id, az.id
        FROM access_profiles ap, access_zones az
        WHERE ap.name = 'HR — HR Office Access'
        AND az.code IN ('MAIN-ENTRANCE','FLOOR-1','FLOOR-2','FLOOR-3','HR-OFFICE','BOARDROOM','CAR-PARK')
    """)

    op.execute("""
        INSERT INTO access_profile_zones (id, profile_id, zone_id)
        SELECT uuid_generate_v4(), ap.id, az.id
        FROM access_profiles ap, access_zones az
        WHERE ap.name = 'Admin — General Access'
        AND az.code IN ('MAIN-ENTRANCE','FLOOR-1','FLOOR-2','CAR-PARK')
    """)

    op.execute("""
        INSERT INTO access_profile_zones (id, profile_id, zone_id)
        SELECT uuid_generate_v4(), ap.id, az.id
        FROM access_profiles ap, access_zones az
        WHERE ap.name = 'Contractor — Entry Only'
        AND az.code IN ('MAIN-ENTRANCE','FLOOR-1')
    """)


def downgrade() -> None:
    op.drop_table("person_access_zones")
    op.drop_table("person_access")
    op.drop_table("access_profile_zones")
    op.drop_table("access_profiles")
    op.drop_table("access_zones")
    op.execute("DROP TYPE IF EXISTS zoneaccesstype")
