"""cache de guías y notas de Andiamo para el Q&A de viaje del bot

Revision ID: 0009
Revises: 0008
"""
from alembic import op
import sqlalchemy as sa


revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "guide_docs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("guide_slug", sa.String(80), nullable=False),
        sa.Column("doc_slug", sa.String(80), nullable=False),
        sa.Column("guide_title", sa.String(160), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("country", sa.String(80), nullable=True),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("file", sa.String(255), nullable=False),
        sa.Column("content_md", sa.Text(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.UniqueConstraint("guide_slug", "doc_slug"),
    )
    op.create_index("ix_guide_docs_guide_slug", "guide_docs", ["guide_slug"])

    op.create_table(
        "stop_guides",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("stop_slug", sa.String(80), nullable=False),
        sa.Column("guide_slug", sa.String(80), nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
    )
    op.create_index("ix_stop_guides_stop_slug", "stop_guides", ["stop_slug"])

    op.create_table(
        "trip_notes",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("stop_slug", sa.String(80), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("synced_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
    )
    op.create_index("ix_trip_notes_stop_slug", "trip_notes", ["stop_slug"])

    op.create_table(
        "sync_meta",
        sa.Column("key", sa.String(50), primary_key=True),
        sa.Column("value", sa.String(255), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("sync_meta")
    op.drop_index("ix_trip_notes_stop_slug", table_name="trip_notes")
    op.drop_table("trip_notes")
    op.drop_index("ix_stop_guides_stop_slug", table_name="stop_guides")
    op.drop_table("stop_guides")
    op.drop_index("ix_guide_docs_guide_slug", table_name="guide_docs")
    op.drop_table("guide_docs")
