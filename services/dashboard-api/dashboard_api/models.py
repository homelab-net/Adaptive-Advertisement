"""
SQLAlchemy ORM models — ICD-7 persistence contract.

Tables
------
manifests           — creative manifest lifecycle records
assets              — uploaded asset metadata (no raw bytes stored here)
campaigns           — operator-defined groupings of approved manifests
campaign_manifests  — M2M join: campaigns ↔ manifests with ordering
safe_mode_state     — singleton row tracking appliance safe-mode intent
audit_events        — append-only log of all operator actions (PRIV-006)

Design rules enforced here
--------------------------
- All PKs are UUID v4 (str on SQLite, native UUID on PostgreSQL).
- `audit_events` has no update columns — the table is append-only.
- No raw image data, frame data, or biometric templates anywhere.
- `manifest_json` (JSONB on PostgreSQL) stores the ICD-5 creative manifest
  payload as supplied by the operator; business-logic validation is in the
  router layer.
"""
import uuid
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Base(DeclarativeBase):
    pass


# ---------------------------------------------------------------------------
# manifests
# ---------------------------------------------------------------------------

class ManifestStatus(str):
    DRAFT = "draft"
    APPROVED = "approved"
    REJECTED = "rejected"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ARCHIVED = "archived"


_MANIFEST_STATUSES = ("draft", "approved", "rejected", "enabled", "disabled", "archived")


class Manifest(Base):
    __tablename__ = "manifests"

    id: Mapped[str] = mapped_column(
        sa.String(36), primary_key=True, default=_uuid
    )
    manifest_id: Mapped[str] = mapped_column(
        sa.String(128), unique=True, nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    status: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default="draft", index=True
    )
    schema_version: Mapped[str] = mapped_column(sa.String(32), nullable=False)

    # Full ICD-5 manifest payload (JSONB on PostgreSQL, TEXT on SQLite)
    manifest_json: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    rejection_reason: Mapped[str | None] = mapped_column(sa.String(1024), nullable=True)
    approved_by: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    enabled_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now,
        onupdate=_now,
        server_default=func.now(),
    )

    campaign_links: Mapped[list["CampaignManifest"]] = relationship(
        back_populates="manifest", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Manifest {self.manifest_id} [{self.status}]>"


# ---------------------------------------------------------------------------
# assets
# ---------------------------------------------------------------------------

class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    asset_id: Mapped[str] = mapped_column(
        sa.String(128), unique=True, nullable=False, index=True
    )
    filename: Mapped[str] = mapped_column(sa.String(512), nullable=False)
    asset_type: Mapped[str] = mapped_column(
        sa.String(32), nullable=False
    )  # "video" | "image" | "html"
    size_bytes: Mapped[int] = mapped_column(sa.BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(sa.String(64), nullable=False)

    # Nullable FK — asset may exist before being assigned to a manifest
    manifest_id: Mapped[str | None] = mapped_column(
        sa.String(128), nullable=True, index=True
    )

    status: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default="active"
    )  # "active" | "archived"

    uploaded_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now,
        server_default=func.now(),
    )

    def __repr__(self) -> str:
        return f"<Asset {self.asset_id} [{self.asset_type}]>"


# ---------------------------------------------------------------------------
# campaigns
# ---------------------------------------------------------------------------

class Campaign(Base):
    __tablename__ = "campaigns"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(sa.String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    status: Mapped[str] = mapped_column(
        sa.String(32), nullable=False, default="draft", index=True
    )  # "draft" | "active" | "paused" | "archived"

    start_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    end_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now,
        onupdate=_now,
        server_default=func.now(),
    )

    manifest_links: Mapped[list["CampaignManifest"]] = relationship(
        back_populates="campaign",
        cascade="all, delete-orphan",
        order_by="CampaignManifest.position",
    )

    def __repr__(self) -> str:
        return f"<Campaign {self.id} {self.name!r} [{self.status}]>"


# ---------------------------------------------------------------------------
# campaign_manifests (M2M join table with ordering)
# ---------------------------------------------------------------------------

class CampaignManifest(Base):
    __tablename__ = "campaign_manifests"

    campaign_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("campaigns.id", ondelete="CASCADE"),
        primary_key=True,
    )
    manifest_id: Mapped[str] = mapped_column(
        sa.String(36), sa.ForeignKey("manifests.id", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(sa.Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now,
        server_default=func.now(),
    )

    campaign: Mapped["Campaign"] = relationship(back_populates="manifest_links")
    manifest: Mapped["Manifest"] = relationship(back_populates="campaign_links")


# ---------------------------------------------------------------------------
# safe_mode_state  (singleton: always id = 1)
# ---------------------------------------------------------------------------

class SafeModeState(Base):
    __tablename__ = "safe_mode_state"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, default=1)
    is_active: Mapped[bool] = mapped_column(sa.Boolean, nullable=False, default=False)
    reason: Mapped[str | None] = mapped_column(sa.String(512), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(
        sa.DateTime(timezone=True), nullable=True
    )
    activated_by: Mapped[str | None] = mapped_column(sa.String(128), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now, onupdate=_now,
        server_default=func.now(),
    )


# ---------------------------------------------------------------------------
# audit_events  (append-only — no update columns, no delete)
# ---------------------------------------------------------------------------

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(sa.String(36), primary_key=True, default=_uuid)
    event_type: Mapped[str] = mapped_column(sa.String(64), nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(sa.String(32), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(sa.String(128), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(sa.String(128), nullable=False)
    payload: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime(timezone=True), nullable=False, default=_now,
        server_default=func.now(),
        index=True,
    )

    def __repr__(self) -> str:
        return f"<AuditEvent {self.event_type} {self.entity_id}>"
