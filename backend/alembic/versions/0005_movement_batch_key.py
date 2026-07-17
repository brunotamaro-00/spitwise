"""movement batch_key (multi-gasto por mensaje)

Revision ID: 0005
Revises: 0004
"""
from alembic import op
import sqlalchemy as sa


revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("movements", sa.Column("batch_key", sa.String(length=16), nullable=True))


def downgrade() -> None:
    op.drop_column("movements", "batch_key")
