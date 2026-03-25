"""manifest audience_tags column

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-25

Adds audience_tags JSON column to the manifests table.
Stores an array of operator-assigned tag keys, e.g. ["adult_with_child", "time_happy_hour"].
NULL on existing rows is treated as [] (untagged) by the API layer.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "manifests",
        sa.Column("audience_tags", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("manifests", "audience_tags")
