"""Temporary NFC card on people

Revision ID: 0007
Revises: 0006
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('people', sa.Column('temp_nfc_uid', sa.String(50), nullable=True))
    op.create_unique_constraint('uq_people_temp_nfc_uid', 'people', ['temp_nfc_uid'])
    op.create_index('ix_people_temp_nfc_uid', 'people', ['temp_nfc_uid'])


def downgrade() -> None:
    op.drop_index('ix_people_temp_nfc_uid', table_name='people')
    op.drop_constraint('uq_people_temp_nfc_uid', 'people', type_='unique')
    op.drop_column('people', 'temp_nfc_uid')
