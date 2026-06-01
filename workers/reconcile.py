"""Scheduled job — walks the Recordings folder of every domain user,
finds new recordings, and processes them inline (transcribe + extract + email).
Run on a schedule (e.g. every 15 minutes) or manually."""
import asyncio
import sys

# Force UTF-8 output so filenames with special characters don't crash on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from app.db import SessionLocal
from app.graph import client as graph
from app.services.ledger import claim_item
from app.pipeline.steps import process_recording


async def reconcile() -> int:
    found = 0
    users = await graph.list_domain_users()
    print(f"Reconciling {len(users)} domain user(s)...")

    for user in users:
        upn = user.get("mail") or user.get("id")
        try:
            drive_id = await graph.get_user_drive_id(upn)
            recordings = await graph.list_recordings_folder(drive_id)
        except Exception as e:
            print(f"  Skipping {upn}: {e}")
            continue

        for item in recordings:
            drive_item_id = item["id"]
            etag = item.get("eTag")

            async with SessionLocal() as db:
                claimed = await claim_item(db, drive_item_id, drive_id, etag, source="reconcile")

            if claimed:
                print(f"  Processing: {item['name']} (owner: {upn})")
                try:
                    async with SessionLocal() as db:
                        await process_recording(db, drive_item_id, drive_id, owner_upn=upn)
                    print(f"  Done: {item['name']}")
                    found += 1
                except Exception as e:
                    print(f"  Failed: {item['name']} — {e}")

    return found


if __name__ == "__main__":
    n = asyncio.run(reconcile())
    print(f"\nReconciliation complete — processed {n} new recording(s).")
