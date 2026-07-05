"""Card status + note on people

Revision ID: 0006
Revises: 0005
Create Date: 2026-07-04
"""
from alembic import op
import sqlalchemy as sa

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('people', sa.Column('card_status', sa.String(30), server_default='active', nullable=False))
    op.add_column('people', sa.Column('card_status_note', sa.String(300), nullable=True))


def downgrade() -> None:
    op.drop_column('people', 'card_status_note')
    op.drop_column('people', 'card_status')
