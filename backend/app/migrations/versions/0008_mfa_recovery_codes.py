"""MFA recovery codes on app_users

Revision ID: 0008
Revises: 0007
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('app_users', sa.Column('mfa_recovery_codes', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('app_users', 'mfa_recovery_codes')
