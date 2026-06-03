"""User self-service API — lets the frontend check the caller's registration status."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..db import get_db
from ..models import RegisteredUser
from ..schemas import RegisteredUserOut
from .deps import current_user

router = APIRouter(tags=["users"])


@router.get("/users/me", response_model=RegisteredUserOut)
async def get_me(db: AsyncSession = Depends(get_db), upn: str = Depends(current_user)):
    """Return the registration record for the currently signed-in user.

    The frontend calls this on every page load to decide whether to show the
    normal dashboard or the 'Pending Activation' screen.  Returns 404 if the
    user's UPN has not been registered by an admin yet.
    """
    user = await db.scalar(
        select(RegisteredUser)
        .where(RegisteredUser.upn == upn)
        .options(selectinload(RegisteredUser.business_unit))
    )
    if not user:
        raise HTTPException(404, "Not registered — contact an administrator to gain access")

    return RegisteredUserOut(
        upn=user.upn,
        display_name=user.display_name,
        business_unit_id=user.business_unit_id,
        business_unit_name=user.business_unit.name if user.business_unit else None,
        is_admin=user.is_admin,
        registered_at=user.registered_at.isoformat(),
    )
