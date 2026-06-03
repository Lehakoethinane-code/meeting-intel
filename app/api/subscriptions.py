"""Graph subscriptions expire after ~3 days for OneDrive resources.
POST /subscriptions/ensure creates or renews one subscription per domain user.
Call this endpoint on startup and on a daily cron job."""
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import APIRouter, Header, HTTPException

from ..config import get_settings
from ..graph.auth import get_token
from ..graph import client as graph

settings = get_settings()
router = APIRouter()


async def _get_existing_subscriptions(client: httpx.AsyncClient) -> dict[str, dict]:
    """Return existing subscriptions keyed by their resource path."""
    r = await client.get(
        f"{settings.graph_base}/subscriptions",
        headers={"Authorization": f"Bearer {get_token()}"},
    )
    r.raise_for_status()
    return {s["resource"]: s for s in r.json().get("value", [])}


async def _upsert_subscription(
    client: httpx.AsyncClient,
    resource: str,
    existing: dict[str, dict],
) -> dict:
    expiry = (datetime.now(timezone.utc) + timedelta(days=2, hours=20)).isoformat()
    headers = {"Authorization": f"Bearer {get_token()}"}
    notification_url = f"{settings.webhook_base_url}/webhooks/graph"

    if resource in existing:
        sub_id = existing[resource]["id"]
        r = await client.patch(
            f"{settings.graph_base}/subscriptions/{sub_id}",
            headers=headers,
            json={"expirationDateTime": expiry},
        )
        r.raise_for_status()
        return {"action": "renewed", "resource": resource, "id": sub_id}

    payload = {
        "changeType": "updated",
        "notificationUrl": notification_url,
        "resource": resource,
        "expirationDateTime": expiry,
        "clientState": settings.webhook_client_state,
    }
    r = await client.post(
        f"{settings.graph_base}/subscriptions",
        headers=headers,
        json=payload,
    )
    r.raise_for_status()
    return {"action": "created", "resource": resource, "id": r.json()["id"]}


@router.post("/subscriptions/ensure")
async def ensure_subscriptions(x_subscription_secret: str = Header(...)):
    """Create or renew a Graph webhook subscription for every domain user's OneDrive."""
    if not settings.subscription_secret or x_subscription_secret != settings.subscription_secret:
        raise HTTPException(status_code=401, detail="Invalid secret")

    users = await graph.list_domain_users()
    results = []

    async with httpx.AsyncClient(timeout=30) as client:
        existing = await _get_existing_subscriptions(client)

        for user in users:
            upn = user.get("mail") or user.get("id")
            try:
                drive_id = await graph.get_user_drive_id(upn)
                resource = f"/drives/{drive_id}/root"
                result = await _upsert_subscription(client, resource, existing)
                result["user"] = upn
                results.append(result)
            except Exception as e:
                results.append({"user": upn, "error": str(e)})

    return {"subscriptions": results, "total": len(results)}
