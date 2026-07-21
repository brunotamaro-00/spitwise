"""refinar catálogo de categorías: quitar "Regalos" (-> "Compras"),
sumar "Cafetería" y "Lavandería"

Revision ID: 0010
Revises: 0009

Las categorías se referencian por id (FK). El seed idempotente del lifespan
crea/renombra por `name` y fija `sort_order`, así que Cafetería y Lavandería
nacen solas en el próximo arranque — esta migración solo tiene que resolver el
retiro de "Regalos" sin dejar huérfanos: reimputar sus movimientos a "Compras"
y borrar la fila legacy (si no, el seed la dejaría colgada como 12.ª categoría).
"""
from alembic import op
import sqlalchemy as sa


revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Reimputar movimientos de Regalos -> Compras (por id, sin tocar montos/splits).
    op.execute(sa.text(
        "UPDATE movements SET category_id = "
        "  (SELECT id FROM categories WHERE name = 'Compras') "
        "WHERE category_id = (SELECT id FROM categories WHERE name = 'Regalos') "
        "  AND EXISTS (SELECT 1 FROM categories WHERE name = 'Compras')"
    ))
    # Retirar la categoría legacy ya sin referencias.
    op.execute(sa.text("DELETE FROM categories WHERE name = 'Regalos'"))


def downgrade() -> None:
    # Recrear la fila para no romper el downgrade; los movimientos reimputados
    # quedan en Compras (la reversa exacta no es reconstruible).
    op.execute(sa.text(
        "INSERT INTO categories (name, icon, sort_order, description) "
        "SELECT 'Regalos', '🎁', 99, 'para otros: regalos, souvenirs, postales' "
        "WHERE NOT EXISTS (SELECT 1 FROM categories WHERE name = 'Regalos')"
    ))
