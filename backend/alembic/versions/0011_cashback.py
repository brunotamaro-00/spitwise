"""cashback de tarjeta por gasto (cashback_kind / cashback_value)

Revision ID: 0011
Revises: 0010

Sin backfill: NULL = sin cashback (net == gross), así que amount_usd de las
filas existentes ya es correcto. batch_alter cubre SQLite (demo.db).
"""
from alembic import op
import sqlalchemy as sa


revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("movements") as batch:
        batch.add_column(sa.Column("cashback_kind", sa.String(8), nullable=True))
        batch.add_column(sa.Column("cashback_value", sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("movements") as batch:
        batch.drop_column("cashback_value")
        batch.drop_column("cashback_kind")
