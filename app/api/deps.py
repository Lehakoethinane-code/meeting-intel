"""Shared FastAPI dependencies used across multiple routers."""
from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import RegisteredUser

settings = get_settings()


async def current_user(x_user_upn: str = Header(...)) -> str:
    """FastAPI dependency: extract and validate the caller's UPN from the request header.

    The frontend sends ``x-user-upn`` on every API call.  Any UPN outside the
    configured ``ALLOWED_DOMAIN`` is rejected with 403.
    """
    if not x_user_upn.endswith("@" + settings.allowed_domain):
        raise HTTPException(403, "Outside allowed domain")
    return x_user_upn


async def require_registered(
    x_user_upn: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> str:
    """FastAPI dependency: verify the caller is a registered platform user.

    Raises 403 for outside-domain UPNs and for domain users not yet registered.
    Use this instead of ``current_user`` on endpoints that should be invisible
    to unregistered domain members.
    """
    upn = x_user_upn.lower()
    if not upn.endswith("@" + settings.allowed_domain):
        raise HTTPException(403, "Outside allowed domain")
    user = await db.scalar(select(RegisteredUser).where(RegisteredUser.upn == upn))
    if not user:
        raise HTTPException(403, "Not registered on the platform")
    return upn


async def require_admin(upn: str = ..., db: AsyncSession = ...) -> str:
    """FastAPI dependency: verify the caller is a registered admin.

    Raises 403 if the UPN is not found in ``registered_users`` or is not an admin.
    Must be used together with ``current_user`` — callers should declare both deps.
    """
    user = await db.scalar(select(RegisteredUser).where(RegisteredUser.upn == upn))
    if not user or not user.is_admin:
        raise HTTPException(403, "Admin access required")
    return upn
