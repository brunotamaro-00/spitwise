"""marca de procesado en el dedupe de WhatsApp

Sin esto, un wamid claimed pero no terminado (proceso reiniciado a mitad) hacía
que el reintento de Meta se descartara por dedupe: el gasto se perdía en
silencio. Las filas viejas se backfillean como ya procesadas.

Revision ID: 0015
Revises: 0014
"""
from alembic import op
import sqlalchemy as sa


revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "whatsapp_dedupe", sa.Column("processed_at", sa.DateTime(), nullable=True)
    )
    op.execute("UPDATE whatsapp_dedupe SET processed_at = created_at")


def downgrade() -> None:
    op.drop_column("whatsapp_dedupe", "processed_at")
