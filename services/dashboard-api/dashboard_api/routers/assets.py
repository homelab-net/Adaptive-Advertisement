"""
Asset router — upload and manage creative asset files.

Assets are physical files (video, image, html) stored on-device.
Only metadata is stored in the database — the raw bytes live on disk
under ASSET_STORAGE_DIR.

Privacy note: assets are operator-supplied creative content (ads), not
audience data.  No privacy constraints apply to the asset bytes themselves,
but the storage path must stay on-device (WAN-independent requirement).
"""
import hashlib
import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import settings
from ..db import get_session
from ..events import write_event, ASSET_UPLOADED, ASSET_ARCHIVED
from ..models import Asset
from ..schemas import AssetOut, AssetSummary, AssetListOut, Pagination

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/assets", tags=["assets"])

_ALLOWED_ASSET_TYPES = {"video", "image", "html"}
_ALLOWED_EXTENSIONS: dict[str, str] = {
    ".mp4": "video", ".webm": "video",
    ".jpg": "image", ".jpeg": "image", ".png": "image", ".webp": "image",
    ".html": "html",
}


def _detect_asset_type(filename: str) -> str:
    ext = Path(filename).suffix.lower()
    return _ALLOWED_EXTENSIONS.get(ext, "unknown")


@router.get("", response_model=AssetListOut)
async def list_assets(
    asset_type: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> AssetListOut:
    q = select(Asset).where(Asset.status == "active")
    if asset_type:
        q = q.where(Asset.asset_type == asset_type)
    q = q.order_by(Asset.uploaded_at.desc())

    count_q = select(func.count()).select_from(q.subquery())
    total = (await session.execute(count_q)).scalar_one()

    page_size = min(page_size or settings.default_page_size, settings.max_page_size)
    q = q.offset((page - 1) * page_size).limit(page_size)
    rows = (await session.execute(q)).scalars().all()

    return AssetListOut(
        items=[AssetSummary.model_validate(r) for r in rows],
        pagination=Pagination(
            total=total, page=page, page_size=page_size,
            pages=max(1, (total + page_size - 1) // page_size),
        ),
    )


@router.post("", response_model=AssetOut, status_code=status.HTTP_201_CREATED)
async def upload_asset(
    file: UploadFile = File(...),
    session: AsyncSession = Depends(get_session),
) -> AssetOut:
    """
    Upload a creative asset file.

    The file is stored on-device under ASSET_STORAGE_DIR.
    An asset_id (UUID) is assigned and returned for use in manifest definitions.
    """
    filename = file.filename or "unknown"
    asset_type = _detect_asset_type(filename)
    if asset_type == "unknown":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type: {Path(filename).suffix}. "
                   f"Allowed: {', '.join(_ALLOWED_EXTENSIONS)}",
        )

    asset_id = str(uuid.uuid4())
    storage_dir = Path(settings.asset_storage_dir)
    storage_dir.mkdir(parents=True, exist_ok=True)
    dest_path = storage_dir / asset_id

    # Stream to disk, compute SHA-256 in one pass
    sha = hashlib.sha256()
    size_bytes = 0
    try:
        with dest_path.open("wb") as f:
            while chunk := await file.read(65536):
                f.write(chunk)
                sha.update(chunk)
                size_bytes += len(chunk)
    except OSError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to write asset to disk: {exc}",
        )

    asset = Asset(
        asset_id=asset_id,
        filename=filename,
        asset_type=asset_type,
        size_bytes=size_bytes,
        sha256=sha.hexdigest(),
        status="active",
    )
    session.add(asset)
    await write_event(
        session,
        event_type=ASSET_UPLOADED,
        entity_type="asset",
        entity_id=asset_id,
        payload={
            "filename": filename,
            "asset_type": asset_type,
            "size_bytes": size_bytes,
        },
    )
    await session.commit()
    await session.refresh(asset)
    log.info("asset uploaded asset_id=%s type=%s size=%d", asset_id, asset_type, size_bytes)
    return AssetOut.model_validate(asset)


@router.get("/{asset_id}", response_model=AssetOut)
async def get_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
) -> AssetOut:
    result = await session.execute(select(Asset).where(Asset.asset_id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    return AssetOut.model_validate(asset)


@router.delete("/{asset_id}", response_model=AssetOut)
async def archive_asset(
    asset_id: str,
    session: AsyncSession = Depends(get_session),
) -> AssetOut:
    """Soft-delete an asset (set status=archived). Does not remove file from disk."""
    result = await session.execute(select(Asset).where(Asset.asset_id == asset_id))
    asset = result.scalar_one_or_none()
    if asset is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Asset not found.")
    if asset.status == "archived":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Asset is already archived.",
        )

    asset.status = "archived"
    await write_event(
        session,
        event_type=ASSET_ARCHIVED,
        entity_type="asset",
        entity_id=asset_id,
        payload={"filename": asset.filename},
    )
    await session.commit()
    await session.refresh(asset)
    return AssetOut.model_validate(asset)
