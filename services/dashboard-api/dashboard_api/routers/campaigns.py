"""
Campaign router — operator-defined groupings of approved manifests.

A campaign is a named collection of manifests with optional scheduling.
Manifests must be in 'approved' or 'enabled' state to be added to a campaign.
"""
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_session
from ..events import (
    write_event,
    CAMPAIGN_CREATED, CAMPAIGN_UPDATED, CAMPAIGN_ARCHIVED,
    CAMPAIGN_MANIFEST_ADDED, CAMPAIGN_MANIFEST_REMOVED,
)
from ..models import Campaign, CampaignManifest, Manifest
from ..schemas import (
    CampaignIn, CampaignUpdate, CampaignOut, CampaignSummary,
    CampaignListOut, Pagination,
)

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/campaigns", tags=["campaigns"])

_ACTIVATABLE_MANIFEST_STATUSES = {"approved", "enabled"}


async def _get_campaign_or_404(campaign_id: str, session: AsyncSession) -> Campaign:
    result = await session.execute(
        select(Campaign).where(Campaign.id == campaign_id)
    )
    c = result.scalar_one_or_none()
    if c is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Campaign '{campaign_id}' not found.",
        )
    return c


async def _build_campaign_out(campaign: Campaign, session: AsyncSession) -> CampaignOut:
    """Resolve manifest_ids for the detail view."""
    links = (
        await session.execute(
            select(CampaignManifest)
            .where(CampaignManifest.campaign_id == campaign.id)
            .order_by(CampaignManifest.position)
        )
    ).scalars().all()

    manifest_ids: list[str] = []
    for link in links:
        result = await session.execute(
            select(Manifest.manifest_id).where(Manifest.id == link.manifest_id)
        )
        mid = result.scalar_one_or_none()
        if mid:
            manifest_ids.append(mid)

    out = CampaignOut.model_validate(campaign)
    out.manifest_ids = manifest_ids
    return out


@router.get("", response_model=CampaignListOut)
async def list_campaigns(
    status_filter: str | None = Query(default=None, alias="status"),
    page: int = Query(default=1, ge=1),
    page_size: int | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> CampaignListOut:
    from ..config import settings
    page_size = min(page_size or settings.default_page_size, settings.max_page_size)

    q = select(Campaign)
    if status_filter:
        q = q.where(Campaign.status == status_filter)
    q = q.order_by(Campaign.created_at.desc())

    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(count_q)).scalar_one()

    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(q)).scalars().all()

    return CampaignListOut(
        items=[CampaignSummary.model_validate(r) for r in rows],
        pagination=Pagination(
            total=total, page=page, page_size=page_size,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


@router.post("", response_model=CampaignOut, status_code=status.HTTP_201_CREATED)
async def create_campaign(
    body: CampaignIn,
    session: AsyncSession = Depends(get_session),
) -> CampaignOut:
    c = Campaign(
        name=body.name,
        description=body.description,
        start_at=body.start_at,
        end_at=body.end_at,
        status="draft",
    )
    session.add(c)
    await session.flush()  # populate c.id before audit event

    await write_event(
        session,
        event_type=CAMPAIGN_CREATED,
        entity_type="campaign",
        entity_id=c.id,
        payload={"name": body.name},
    )
    await session.commit()
    await session.refresh(c)
    return await _build_campaign_out(c, session)


@router.get("/{campaign_id}", response_model=CampaignOut)
async def get_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
) -> CampaignOut:
    c = await _get_campaign_or_404(campaign_id, session)
    return await _build_campaign_out(c, session)


@router.patch("/{campaign_id}", response_model=CampaignOut)
async def update_campaign(
    campaign_id: str,
    body: CampaignUpdate,
    session: AsyncSession = Depends(get_session),
) -> CampaignOut:
    c = await _get_campaign_or_404(campaign_id, session)
    if c.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot update an archived campaign.",
        )

    changes: dict = {}
    if body.name is not None:
        c.name = body.name
        changes["name"] = body.name
    if body.description is not None:
        c.description = body.description
        changes["description"] = body.description
    if body.status is not None:
        if body.status not in ("draft", "active", "paused", "archived"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Invalid campaign status: {body.status}",
            )
        changes["previous_status"] = c.status
        changes["new_status"] = body.status
        c.status = body.status
    if body.start_at is not None:
        c.start_at = body.start_at
    if body.end_at is not None:
        c.end_at = body.end_at
    c.updated_at = datetime.now(timezone.utc)

    await write_event(
        session,
        event_type=CAMPAIGN_UPDATED,
        entity_type="campaign",
        entity_id=campaign_id,
        payload=changes,
    )
    await session.commit()
    await session.refresh(c)
    return await _build_campaign_out(c, session)


@router.post("/{campaign_id}/manifests/{manifest_id}", response_model=CampaignOut)
async def add_manifest_to_campaign(
    campaign_id: str,
    manifest_id: str,
    session: AsyncSession = Depends(get_session),
) -> CampaignOut:
    """
    Add an approved or enabled manifest to a campaign.
    Unapproved manifests cannot be added — approval is non-bypassable.
    """
    c = await _get_campaign_or_404(campaign_id, session)
    if c.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot modify an archived campaign.",
        )

    result = await session.execute(
        select(Manifest).where(Manifest.manifest_id == manifest_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest '{manifest_id}' not found.",
        )
    if m.status not in _ACTIVATABLE_MANIFEST_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Manifest '{manifest_id}' has status '{m.status}'. "
                f"Only approved or enabled manifests can be added to a campaign."
            ),
        )

    # Idempotent — check if already in campaign
    existing_link = await session.execute(
        select(CampaignManifest).where(
            CampaignManifest.campaign_id == campaign_id,
            CampaignManifest.manifest_id == m.id,
        )
    )
    if existing_link.scalar_one_or_none() is not None:
        return await _build_campaign_out(c, session)

    # Append at end
    max_pos_result = await session.execute(
        select(func.max(CampaignManifest.position)).where(
            CampaignManifest.campaign_id == campaign_id
        )
    )
    max_pos = max_pos_result.scalar_one_or_none() or -1

    link = CampaignManifest(
        campaign_id=campaign_id,
        manifest_id=m.id,
        position=max_pos + 1,
    )
    session.add(link)

    await write_event(
        session,
        event_type=CAMPAIGN_MANIFEST_ADDED,
        entity_type="campaign",
        entity_id=campaign_id,
        payload={"manifest_id": manifest_id},
    )
    await session.commit()
    await session.refresh(c)
    return await _build_campaign_out(c, session)


@router.delete("/{campaign_id}/manifests/{manifest_id}", response_model=CampaignOut)
async def remove_manifest_from_campaign(
    campaign_id: str,
    manifest_id: str,
    session: AsyncSession = Depends(get_session),
) -> CampaignOut:
    c = await _get_campaign_or_404(campaign_id, session)

    result = await session.execute(
        select(Manifest).where(Manifest.manifest_id == manifest_id)
    )
    m = result.scalar_one_or_none()
    if m is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Manifest not found.")

    link_result = await session.execute(
        select(CampaignManifest).where(
            CampaignManifest.campaign_id == campaign_id,
            CampaignManifest.manifest_id == m.id,
        )
    )
    link = link_result.scalar_one_or_none()
    if link is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Manifest '{manifest_id}' is not in this campaign.",
        )

    await session.delete(link)
    await write_event(
        session,
        event_type=CAMPAIGN_MANIFEST_REMOVED,
        entity_type="campaign",
        entity_id=campaign_id,
        payload={"manifest_id": manifest_id},
    )
    await session.commit()
    await session.refresh(c)
    return await _build_campaign_out(c, session)


@router.delete("/{campaign_id}", response_model=CampaignOut)
async def archive_campaign(
    campaign_id: str,
    session: AsyncSession = Depends(get_session),
) -> CampaignOut:
    """Soft-delete (archive) a campaign."""
    c = await _get_campaign_or_404(campaign_id, session)
    if c.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Campaign is already archived.",
        )

    prev = c.status
    c.status = "archived"
    c.updated_at = datetime.now(timezone.utc)

    await write_event(
        session,
        event_type=CAMPAIGN_ARCHIVED,
        entity_type="campaign",
        entity_id=campaign_id,
        payload={"previous_status": prev},
    )
    await session.commit()
    await session.refresh(c)
    return await _build_campaign_out(c, session)
