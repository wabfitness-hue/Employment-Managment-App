"""Access log entries (building in/out history)

Revision ID: 0010
Revises: 0009
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'access_log_entries',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text('uuid_generate_v4()')),
        sa.Column('person_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('people.id'), nullable=False),
        sa.Column('direction', sa.Enum('in', 'out', name='accessdirection'), nullable=False),
        sa.Column('granted', sa.Boolean(), nullable=False),
        sa.Column('reason', sa.String(200), nullable=True),
        sa.Column('nfc_uid', sa.String(50), nullable=True),
        sa.Column('device_id', sa.String(100), nullable=True),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )
    op.create_index('ix_access_log_entries_person_id', 'access_log_entries', ['person_id'])
    op.create_index('ix_access_log_entries_timestamp', 'access_log_entries', ['timestamp'])


def downgrade() -> None:
    op.drop_index('ix_access_log_entries_timestamp', table_name='access_log_entries')
    op.drop_index('ix_access_log_entries_person_id', table_name='access_log_entries')
    op.drop_table('access_log_entries')
    op.execute('DROP TYPE IF EXISTS accessdirection')
