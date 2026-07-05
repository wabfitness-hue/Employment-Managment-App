"""Contractor card colour on companies

Revision ID: 0004
Revises: 0003
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('contractor_card_colour', sa.String(7), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'contractor_card_colour')
