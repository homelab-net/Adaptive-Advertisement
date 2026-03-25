"""
Audit event helpers (ICD-7, PRIV-006).

Every state-changing operator action MUST call write_event() so that:
- a durable, append-only record exists in the audit_events table
- admin actions are 100% auditable (PRIV-006)

The table is append-only by convention — these helpers never update
or delete audit_events rows.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from .models import AuditEvent

log = logging.getLogger(__name__)

# Canonical event types (mirrors audit-event.schema.json)
MANIFEST_CREATED = "manifest.created"
MANIFEST_APPROVED = "manifest.approved"
MANIFEST_REJECTED = "manifest.rejected"
MANIFEST_ENABLED = "manifest.enabled"
MANIFEST_DISABLED = "manifest.disabled"
MANIFEST_ARCHIVED = "manifest.archived"
MANIFEST_TAGS_UPDATED = "manifest.tags_updated"
MANIFEST_RULES_SYNCED = "manifest.rules_synced"

CAMPAIGN_CREATED = "campaign.created"
CAMPAIGN_UPDATED = "campaign.updated"
CAMPAIGN_ARCHIVED = "campaign.archived"
CAMPAIGN_MANIFEST_ADDED = "campaign.manifest_added"
CAMPAIGN_MANIFEST_REMOVED = "campaign.manifest_removed"

ASSET_UPLOADED = "asset.uploaded"
ASSET_ARCHIVED = "asset.archived"

SAFE_MODE_ENGAGED = "safe_mode.engaged"
SAFE_MODE_CLEARED = "safe_mode.cleared"


async def write_event(
    session: AsyncSession,
    *,
    event_type: str,
    entity_type: str,
    entity_id: str,
    actor: str = "operator",
    payload: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    """
    Append one audit event to the database within the current session.

    The caller is responsible for committing the session.  This function
    only adds the object to the session — it does not flush or commit.

    Payload MUST NOT contain PII, images, or embeddings (PRIV-006).
    """
    event = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=entity_id,
        actor=actor,
        payload=payload,
        created_at=datetime.now(timezone.utc),
    )
    session.add(event)
    log.info(
        "audit event type=%s entity=%s/%s actor=%s",
        event_type,
        entity_type,
        entity_id,
        actor,
    )
    return event
