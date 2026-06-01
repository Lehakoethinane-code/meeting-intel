from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from ..models import ProcessedItem


async def claim_item(
    db: AsyncSession,
    drive_item_id: str,
    drive_id: str | None,
    etag: str | None,
    source: str,
) -> bool:
    """Returns True if this is the first time we've seen the item (claim succeeds),
    False if already processed. Handles duplicate webhooks AND reconcile re-finds."""
    existing = await db.scalar(
        select(ProcessedItem).where(ProcessedItem.drive_item_id == drive_item_id)
    )
    if existing:
        return False
    db.add(ProcessedItem(drive_item_id=drive_item_id, drive_id=drive_id, etag=etag, source=source))
    await db.commit()
    return True
