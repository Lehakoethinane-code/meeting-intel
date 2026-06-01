import asyncio
from ..db import SessionLocal
from ..pipeline.steps import process_recording
from .bus import receive_loop


def _handle(drive_item_id: str, drive_id: str) -> None:
    async def _run():
        async with SessionLocal() as db:
            await process_recording(db, drive_item_id, drive_id)
    asyncio.run(_run())


if __name__ == "__main__":
    print("Worker listening on Service Bus queue...")
    receive_loop(_handle)
