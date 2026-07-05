"""Full card design JSON on companies

Revision ID: 0005
Revises: 0004
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('companies', sa.Column('card_design', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('companies', 'card_design')
