"""add attention and attire columns

Revision ID: 0005
Revises: 0004
Create Date: 2026-04-02

Adds attention and attire tracking columns (CRM-004, CRM-005):
- audience_snapshots.attention_engaged: smoothed gaze-toward-display probability
- audience_snapshots.attire_*: 10 coarse clothing-category bin columns
- play_events.attention_at_trigger: attention engaged value at manifest activation

All new columns are nullable — NULL when the respective CV model is inactive or
when demographics are suppressed (attire columns).
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # audience_snapshots: attention
    op.add_column(
        "audience_snapshots",
        sa.Column("attention_engaged", sa.Float, nullable=True),
    )
    # audience_snapshots: attire bins (10 categories)
    for col in (
        "attire_formal",
        "attire_business_casual",
        "attire_casual",
        "attire_athletic",
        "attire_outdoor_technical",
        "attire_workwear_uniform",
        "attire_streetwear",
        "attire_luxury_premium",
        "attire_lounge_comfort",
        "attire_smart_occasion",
    ):
        op.add_column("audience_snapshots", sa.Column(col, sa.Float, nullable=True))
    # play_events: attention at trigger
    op.add_column(
        "play_events",
        sa.Column("attention_at_trigger", sa.Float, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("play_events", "attention_at_trigger")
    for col in (
        "attire_smart_occasion",
        "attire_lounge_comfort",
        "attire_luxury_premium",
        "attire_streetwear",
        "attire_workwear_uniform",
        "attire_outdoor_technical",
        "attire_athletic",
        "attire_casual",
        "attire_business_casual",
        "attire_formal",
    ):
        op.drop_column("audience_snapshots", col)
    op.drop_column("audience_snapshots", "attention_engaged")
