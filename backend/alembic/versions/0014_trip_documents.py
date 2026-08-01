"""cache de documentos de Andiamo para el Q&A de viaje del bot

Revision ID: 0014
Revises: 0013
"""
from alembic import op
import sqlalchemy as sa


revision = "0014"
down_revision = "0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "trip_documents",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("stop_slug", sa.String(80), nullable=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("doc_date", sa.Date(), nullable=True),
        sa.Column("file_name", sa.String(255), nullable=True),
        sa.Column("mime_type", sa.String(100), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_trip_documents_stop_slug", "trip_documents", ["stop_slug"])


def downgrade() -> None:
    op.drop_index("ix_trip_documents_stop_slug", table_name="trip_documents")
    op.drop_table("trip_documents")
