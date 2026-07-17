"""renombrar categoría "Bebidas/Salidas" -> "Salidas"

Revision ID: 0006
Revises: 0005
"""
from alembic import op
import sqlalchemy as sa


revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # La categoría se referencia por id (FK), así que renombrar el `name` no
    # toca los movimientos. El seed matchea por name: sin este rename dejaría
    # la fila vieja huérfana y crearía una 11.ª categoría.
    op.execute(
        sa.text("UPDATE categories SET name = 'Salidas' WHERE name = 'Bebidas/Salidas'")
    )


def downgrade() -> None:
    op.execute(
        sa.text("UPDATE categories SET name = 'Bebidas/Salidas' WHERE name = 'Salidas'")
    )
