"""analytics tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-25

Adds analytics sink tables:
  audience_snapshots — aggregated audience-state signals (PRIV-safe)
  play_events        — manifest activation log from player (impressions)
  uptime_events      — health-probe ticks for player SLO tracking
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audience_snapshots",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("presence_count", sa.Integer, nullable=False),
        sa.Column("presence_confidence", sa.Float, nullable=False),
        sa.Column("state_stable", sa.Boolean, nullable=False),
        sa.Column("pipeline_degraded", sa.Boolean, nullable=False),
        sa.Column("demographics_suppressed", sa.Boolean, nullable=False),
        sa.Column("age_group_child", sa.Float, nullable=True),
        sa.Column("age_group_young_adult", sa.Float, nullable=True),
        sa.Column("age_group_adult", sa.Float, nullable=True),
        sa.Column("age_group_senior", sa.Float, nullable=True),
    )
    op.create_index("ix_audience_snapshots_sampled_at", "audience_snapshots", ["sampled_at"])

    op.create_table(
        "play_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("manifest_id", sa.String(128), nullable=False),
        sa.Column("activated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("reason", sa.String(256), nullable=True),
        sa.Column("prev_manifest_id", sa.String(128), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.func.now()),
    )
    op.create_index("ix_play_events_manifest_id", "play_events", ["manifest_id"])
    op.create_index("ix_play_events_activated_at", "play_events", ["activated_at"])

    op.create_table(
        "uptime_events",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("sampled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("player_status", sa.String(32), nullable=False),
        sa.Column("overall_status", sa.String(32), nullable=False),
    )
    op.create_index("ix_uptime_events_sampled_at", "uptime_events", ["sampled_at"])


def downgrade() -> None:
    op.drop_table("uptime_events")
    op.drop_table("play_events")
    op.drop_table("audience_snapshots")
