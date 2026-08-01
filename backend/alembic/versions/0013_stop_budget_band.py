"""el plan de vivir de una parada pasa de número a rango (stop_budgets)

Revision ID: 0013
Revises: 0012

`daily_usd` -> `daily_min_usd` + `daily_max_usd`. `Itinerary/PRESUPUESTO.md`
siempre dio bandas ("$2170-2650") y el seed las colapsaba con un promedio: un
solo número prometía una precisión que el presupuesto no tiene, y hacía que
cualquier desvío chico se leyera como desvío.

**Backfill degenerado a propósito:** `min = max = daily_usd`. Una banda de ancho
cero se comporta exactamente como el target de hoy, así que la migración no
cambia ningún veredicto. Abrir la banda con un ±% inventado sería meter un dato
que nadie cargó; las bandas reales las reescribe
`scripts/seed_stop_budgets.py --force`, que las re-deriva del doc (ver DEPLOY.md).

El centro `(min + max) / 2` **no** se persiste: es derivado en `app/budget.py`.

Acá sí hace falta `op.batch_alter_table`: son ALTERs sobre una tabla existente y
la demo local corre sobre SQLite, que no los soporta nativamente.
"""
from alembic import op
import sqlalchemy as sa


revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("stop_budgets") as batch:
        batch.add_column(sa.Column("daily_min_usd", sa.Numeric(10, 2), nullable=True))
        batch.add_column(sa.Column("daily_max_usd", sa.Numeric(10, 2), nullable=True))

    op.execute(
        "UPDATE stop_budgets SET daily_min_usd = daily_usd, daily_max_usd = daily_usd"
    )

    with op.batch_alter_table("stop_budgets") as batch:
        batch.alter_column("daily_min_usd", existing_type=sa.Numeric(10, 2), nullable=False)
        batch.alter_column("daily_max_usd", existing_type=sa.Numeric(10, 2), nullable=False)
        batch.drop_column("daily_usd")


def downgrade() -> None:
    with op.batch_alter_table("stop_budgets") as batch:
        batch.add_column(sa.Column("daily_usd", sa.Numeric(10, 2), nullable=True))

    # Volver al punto = el centro de la banda, que es justo el número contra el
    # que el modelo de rango mide los agregados.
    op.execute("UPDATE stop_budgets SET daily_usd = (daily_min_usd + daily_max_usd) / 2")

    with op.batch_alter_table("stop_budgets") as batch:
        batch.alter_column("daily_usd", existing_type=sa.Numeric(10, 2), nullable=False)
        batch.drop_column("daily_min_usd")
        batch.drop_column("daily_max_usd")
