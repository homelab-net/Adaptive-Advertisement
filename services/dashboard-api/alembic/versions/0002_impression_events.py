"""impression_events table for A/B analytics

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-25

Adds the impression_events table used by ImpressionRecorder to persist
per-manifest impression records sourced from ICD-9 player events + ICD-3
audience-state snapshots.

PLACEHOLDER: this table will populate once the player service is publishing
ICD-9 events to adaptive-ad/player/events and the ImpressionRecorder MQTT
subscriber is running. Until then all analytics endpoints return
data_available=False.
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "impression_events",
        sa.Column("id", sa.String(36), primary_key=True),
        # Which manifest was shown
        sa.Column("manifest_id", sa.String(128), nullable=False),
        # ICD-4 activate_creative.rationale forwarded via ICD-9 event
        sa.Column("rule_rationale", sa.String(128), nullable=True),
        # Timing
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        # ICD-3 audience snapshot at impression start
        # NULL when signal was stale (age > 5 s) or pipeline offline
        sa.Column("audience_count", sa.Integer, nullable=True),
        sa.Column("audience_confidence", sa.Float, nullable=True),
        # Coarse age-bin probabilities (ICD-3 demographics.age_group)
        sa.Column("age_child", sa.Float, nullable=True),
        sa.Column("age_young_adult", sa.Float, nullable=True),
        sa.Column("age_adult", sa.Float, nullable=True),
        sa.Column("age_senior", sa.Float, nullable=True),
        # True when ICD-3 demographics.suppressed was true for this impression
        sa.Column("demographics_suppressed", sa.Boolean, nullable=True),
        # Outcome
        # NULL  = ended by disconnect/safe-mode
        # True  = dwell_elapsed=true at deactivation
        # False = switched before dwell elapsed
        sa.Column("dwell_elapsed", sa.Boolean, nullable=True),
        # "switch" | "disconnect" | "safe_mode" | "freeze" | "unknown"
        sa.Column("ended_reason", sa.String(32), nullable=True),
    )
    op.create_index(
        "ix_impression_events_manifest_id", "impression_events", ["manifest_id"]
    )
    op.create_index(
        "ix_impression_events_started_at", "impression_events", ["started_at"]
    )
    op.create_index(
        "ix_impression_events_ended_at", "impression_events", ["ended_at"]
    )


def downgrade() -> None:
    op.drop_table("impression_events")
