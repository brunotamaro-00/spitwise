"""target de gasto diario de "vivir" por parada (stop_budgets)

Revision ID: 0012
Revises: 0011

Tabla propia y no una columna en `stops`: `Stop` es un snapshot puro de
Andiamo, y la reconciliación del sync borra la fila de una parada que
desapareció allá y no tiene movimientos. El target es dato autoral —cargado a
mano en la web— y no tiene por qué morir con esa limpieza. Por lo mismo
`stop_slug` va sin FK.

Sin backfill: una parada sin fila es una parada sin target, y `app/budget.py`
la trata como tal (baja la cobertura, no se compara ni se extrapola). Los
targets iniciales los carga `scripts/seed_stop_budgets.py`, que es idempotente.

Tabla nueva, así que NO hace falta `op.batch_alter_table` (eso es solo para
ALTERs sobre SQLite, la demo local).
"""
from alembic import op
import sqlalchemy as sa


revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stop_budgets",
        sa.Column("stop_slug", sa.String(80), primary_key=True),
        sa.Column("daily_usd", sa.Numeric(10, 2), nullable=False),
        sa.Column("note", sa.String(200), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("stop_budgets")
