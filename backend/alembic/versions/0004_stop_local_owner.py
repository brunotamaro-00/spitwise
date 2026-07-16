"""stop is_local + owner_username

Revision ID: 0004
Revises: 0003
"""
from alembic import op
import sqlalchemy as sa


revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stops",
        sa.Column("is_local", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.add_column("stops", sa.Column("owner_username", sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column("stops", "owner_username")
    op.drop_column("stops", "is_local")
