import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    String, Text, DateTime, ForeignKey, Enum as SAEnum, UniqueConstraint, Boolean
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB

from .db import Base


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


# --- Enums ---------------------------------------------------------------

class ProcessingState(str, enum.Enum):
    queued = "queued"
    downloading = "downloading"
    transcribing = "transcribing"
    extracting = "extracting"
    awaiting_review = "awaiting_review"   # the human-review gate
    approved = "approved"
    sent = "sent"
    failed = "failed"


class Confidence(str, enum.Enum):
    high = "high"
    medium = "medium"
    low = "low"


# --- Dedupe ledger -------------------------------------------------------
# Both the webhook AND the reconciliation worker funnel through this.
# Idempotency key = Graph drive item id. If a row exists, we skip.

class ProcessedItem(Base):
    __tablename__ = "processed_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    drive_item_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    drive_id: Mapped[str | None] = mapped_column(String(255), nullable=True)   # whose OneDrive
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source: Mapped[str] = mapped_column(String(32))  # "webhook" | "reconcile"
    first_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


# --- Core domain ---------------------------------------------------------

class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    drive_item_id: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    organizer_upn: Mapped[str | None] = mapped_column(String(255), nullable=True)
    title: Mapped[str | None] = mapped_column(String(512), nullable=True)
    recorded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[ProcessingState] = mapped_column(
        SAEnum(ProcessingState), default=ProcessingState.queued, index=True
    )
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    extracted_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    action_items: Mapped[list["ActionItem"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )
    # Row-level access: who is allowed to see this meeting's outputs.
    participants: Mapped[list["MeetingParticipant"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan"
    )


class MeetingParticipant(Base):
    """Authorization is row-level: a user sees a meeting only if they appear here.
    A tax discussion between two partners must NOT surface in a third employee's
    dashboard."""
    __tablename__ = "meeting_participants"
    __table_args__ = (UniqueConstraint("meeting_id", "user_upn", name="uq_meeting_user"),)

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), index=True)
    user_upn: Mapped[str] = mapped_column(String(255), index=True)
    is_organizer: Mapped[bool] = mapped_column(Boolean, default=False)

    meeting: Mapped["Meeting"] = relationship(back_populates="participants")


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=_uuid)
    meeting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("meetings.id"), index=True)

    task: Mapped[str] = mapped_column(Text)
    owner: Mapped[str | None] = mapped_column(String(255), nullable=True)
    deadline_text: Mapped[str | None] = mapped_column(String(255), nullable=True)  # "early June" as-said
    deadline_iso: Mapped[str | None] = mapped_column(String(32), nullable=True)    # only if confident
    confidence: Mapped[Confidence] = mapped_column(SAEnum(Confidence), default=Confidence.medium)
    source_quote: Mapped[str | None] = mapped_column(Text, nullable=True)          # grounding

    # Review gate: nothing emails until an org member approves/edits.
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    edited_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    raw: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    meeting: Mapped["Meeting"] = relationship(back_populates="action_items")
