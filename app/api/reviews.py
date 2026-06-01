from fastapi import APIRouter, Depends, HTTPException, Header
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..db import get_db
from ..models import Meeting, ActionItem, MeetingParticipant, ProcessingState
from ..schemas import MeetingOut, ActionItemOut, ActionItemEdit
from ..graph import client as graph
from ..email_templates import build_meeting_email

settings = get_settings()
router = APIRouter()


# In real life resolve the caller from the validated Entra access token.
# Here we take the UPN from a header to keep the skeleton runnable.
async def current_user(x_user_upn: str = Header(...)) -> str:
    if not x_user_upn.endswith("@" + settings.allowed_domain):
        raise HTTPException(403, "Outside allowed domain")
    return x_user_upn


async def _authorize(db: AsyncSession, meeting_id, upn: str) -> Meeting:
    """Row-level check: caller must be a participant of this meeting."""
    m = await db.scalar(
        select(Meeting)
        .where(Meeting.id == meeting_id)
        .options(selectinload(Meeting.participants), selectinload(Meeting.action_items))
    )
    if not m:
        raise HTTPException(404)
    if not any(p.user_upn == upn for p in m.participants):
        raise HTTPException(403, "Not a participant of this meeting")
    return m


def _to_out(m: Meeting) -> MeetingOut:
    return MeetingOut(
        id=str(m.id), title=m.title, state=m.state, summary=m.summary,
        action_items=[
            ActionItemOut(
                id=str(a.id), task=a.task, owner=a.owner,
                deadline_text=a.deadline_text, deadline_iso=a.deadline_iso,
                confidence=a.confidence, source_quote=a.source_quote, approved=a.approved,
            ) for a in m.action_items
        ],
    )


@router.get("/reviews/pending", response_model=list[MeetingOut])
async def pending(db: AsyncSession = Depends(get_db), upn: str = Depends(current_user)):
    rows = (await db.scalars(
        select(Meeting)
        .join(MeetingParticipant)
        .where(
            Meeting.state == ProcessingState.awaiting_review,
            MeetingParticipant.user_upn == upn,
        )
    )).unique().all()
    return [_to_out(m) for m in rows]


@router.patch("/reviews/action-items/{item_id}")
async def edit_item(item_id: str, edit: ActionItemEdit,
                    db: AsyncSession = Depends(get_db), upn: str = Depends(current_user)):
    item = await db.get(ActionItem, item_id)
    if not item:
        raise HTTPException(404)
    await _authorize(db, item.meeting_id, upn)
    for field, val in edit.model_dump(exclude_unset=True).items():
        setattr(item, field, val)
    item.edited_by = upn
    await db.commit()
    return {"ok": True}


@router.post("/reviews/{meeting_id}/approve")
async def approve(meeting_id: str, db: AsyncSession = Depends(get_db),
                  upn: str = Depends(current_user)):
    m = await _authorize(db, meeting_id, upn)
    for a in m.action_items:
        a.approved = True
    m.state = ProcessingState.approved
    await db.commit()

    if settings.auto_send_email and m.organizer_upn:
        recipients = [p.user_upn for p in m.participants]
        subject, body = build_meeting_email(m)
        await graph.send_mail(m.organizer_upn, recipients, subject, body)
        m.state = ProcessingState.sent
        await db.commit()

    return {"ok": True, "state": m.state}
