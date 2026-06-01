from pydantic import BaseModel
from .models import Confidence, ProcessingState


# ── API output models ─────────────────────────────────────────────────────────

class ActionItemOut(BaseModel):
    id: str
    task: str
    owner: str | None
    deadline_text: str | None
    deadline_iso: str | None
    confidence: Confidence
    source_quote: str | None
    approved: bool


class ActionItemEdit(BaseModel):
    task: str | None = None
    owner: str | None = None
    deadline_iso: str | None = None
    confidence: Confidence | None = None


class MeetingOut(BaseModel):
    id: str
    title: str | None
    state: ProcessingState
    summary: str | None
    action_items: list[ActionItemOut]


# ── Rich extraction schema (what Claude must return) ──────────────────────────

class ExtractedActionItem(BaseModel):
    action: str
    assigned_to: str | None = None
    department: str | None = None
    reason: str | None = None
    expected_outcome: str | None = None
    due_date: str | None = None
    # kept for DB compatibility
    task: str | None = None
    owner: str | None = None
    deadline_text: str | None = None
    deadline_iso: str | None = None
    confidence: Confidence = Confidence.medium
    source_quote: str | None = None

    def model_post_init(self, __context):
        # keep legacy fields in sync so existing DB writes still work
        if not self.task:
            self.task = self.action
        if not self.owner:
            self.owner = self.assigned_to
        if not self.deadline_text:
            self.deadline_text = self.due_date


class DiscussionPoint(BaseModel):
    topic: str
    summary: str
    outcome: str | None = None


class Deliverable(BaseModel):
    deliverable: str
    responsible: str | None = None
    delivery_method: str | None = None
    due_date: str | None = None
    expected_outcome: str | None = None


class Risk(BaseModel):
    item: str
    impact: str | None = None
    resolution: str | None = None
    owner: str | None = None


class NextMeeting(BaseModel):
    proposed_date: str | None = None
    proposed_time: str | None = None
    agenda_focus: str | None = None


class SpeakerHighlight(BaseModel):
    speaker: str
    role: str | None = None          # inferred role if identifiable (e.g. "Facilitator")
    key_points: list[str] = []       # most important things this speaker said


class RichExtractionResult(BaseModel):
    objective: str = ""
    attendees: list[str] = []
    apologies: list[str] = []
    platform: str = "Microsoft Teams"
    meeting_time: str | None = None
    speaker_highlights: list[SpeakerHighlight] = []
    discussion_points: list[DiscussionPoint] = []
    action_items: list[ExtractedActionItem] = []
    deliverables: list[Deliverable] = []
    risks: list[Risk] = []
    next_steps: list[str] = []
    next_meeting: NextMeeting | None = None
    # kept for backwards compat
    summary: str = ""
