"""add gender demographics columns

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-01

Adds coarse gender bin columns to audience_snapshots (CRM-003).
Columns are nullable — NULL when demographics_suppressed=True or when the
upstream pipeline does not provide gender estimates.
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audience_snapshots",
        sa.Column("gender_male", sa.Float, nullable=True),
    )
    op.add_column(
        "audience_snapshots",
        sa.Column("gender_female", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("audience_snapshots", "gender_female")
    op.drop_column("audience_snapshots", "gender_male")
