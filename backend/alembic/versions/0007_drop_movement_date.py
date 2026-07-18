"""eliminar la fecha imputada: la ciudad es el único eje del gasto

Revision ID: 0007
Revises: 0006
"""
from alembic import op
import sqlalchemy as sa


revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Sin backfill: la ciudad ya vive en stop_slug/city_name de cada fila, y
    # cualquier vista por fecha usa created_at. batch_alter cubre SQLite (demo.db).
    with op.batch_alter_table("movements") as batch:
        batch.drop_index("ix_movements_date")
        batch.drop_column("movement_date")


def downgrade() -> None:
    # El dato es irreconstruible: la columna vuelve nullable y vacía.
    with op.batch_alter_table("movements") as batch:
        batch.add_column(sa.Column("movement_date", sa.Date(), nullable=True))
        batch.create_index("ix_movements_date", ["movement_date"])
