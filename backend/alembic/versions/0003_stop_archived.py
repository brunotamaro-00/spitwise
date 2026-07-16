"""stop is_archived

Revision ID: 0003
Revises: 0002
"""
from alembic import op
import sqlalchemy as sa


revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stops",
        sa.Column("is_archived", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("stops", "is_archived")
