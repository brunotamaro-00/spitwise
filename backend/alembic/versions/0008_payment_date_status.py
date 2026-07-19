"""fecha de pago y estado pending/confirmed en movements

Revision ID: 0008
Revises: 0007
"""
from alembic import op
import sqlalchemy as sa


revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sin backfill: NULL = "se pagó el día de carga" y todo lo existente ya está
    # confirmado. batch_alter cubre SQLite (demo.db).
    with op.batch_alter_table("movements") as batch:
        batch.add_column(sa.Column("payment_date", sa.Date(), nullable=True))
        batch.add_column(
            sa.Column("status", sa.String(12), nullable=False, server_default="confirmed")
        )
        batch.create_index("ix_movements_status", ["status"])


def downgrade() -> None:
    with op.batch_alter_table("movements") as batch:
        batch.drop_index("ix_movements_status")
        batch.drop_column("status")
        batch.drop_column("payment_date")
