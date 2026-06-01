import os
import tempfile

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..config import get_settings
from ..models import Meeting, ActionItem, MeetingParticipant, ProcessingState
from ..graph import client as graph
from .transcribe import get_transcriber
from .extract import get_extractor

settings = get_settings()

_POPIA_NOTICE_HTML = """
<p>Dear Participant,</p>

<p>This is an automated notice from <strong>Taxconsulting SA (Pty) Ltd</strong> in compliance
with the <strong>Protection of Personal Information Act, 2013 (POPIA)</strong>.</p>

<p>A Microsoft Teams recording titled <strong>{title}</strong> has been detected in your
organisation's SharePoint library and is being processed by our Meeting Intelligence system.
The following AI-assisted steps will be performed:</p>

<ul>
  <li><strong>Transcription</strong> — the audio is converted to a diarized text transcript.</li>
  <li><strong>Action-item extraction</strong> — a language model identifies tasks, owners,
      and deadlines mentioned during the meeting.</li>
</ul>

<p><strong>Who can see the results?</strong><br>
Access is limited to confirmed participants of this meeting only.
No output is shared more widely or emailed to anyone until the meeting organiser explicitly
reviews and approves it.</p>

<p><strong>Data retention</strong><br>
Transcripts and extracted action items are retained in a private database.
A blob-retention and auto-deletion policy is being finalised; you will be notified
once it is in place.</p>

<p><strong>Your rights under POPIA</strong><br>
You have the right to request access to, correction of, or deletion of your personal
information. To exercise these rights or to object to the processing of your information,
please contact the Information Officer at
<a href="mailto:privacy@taxconsulting.co.za">privacy@taxconsulting.co.za</a>.</p>

<p>If you believe this recording was made without proper consent, please notify the
Information Officer immediately and processing will be suspended pending review.</p>

<p>Kind regards,<br>
<em>Taxconsulting SA Meeting Intelligence — automated notice</em></p>
"""


async def _send_popia_notice(meeting: Meeting, extra_recipients: list[str]) -> None:
    if not settings.popia_notice_enabled or not meeting.organizer_upn:
        return
    recipients = list({meeting.organizer_upn, *extra_recipients} - {None})
    if not recipients:
        return
    title = meeting.title or "a recent Teams meeting"
    await graph.send_mail(
        meeting.organizer_upn,
        recipients,
        f"[Action required] AI processing notice — {title}",
        _POPIA_NOTICE_HTML.format(title=title),
    )


async def process_recording(
    db: AsyncSession, drive_item_id: str, drive_id: str, owner_upn: str | None = None
) -> None:
    meeting = await db.scalar(select(Meeting).where(Meeting.drive_item_id == drive_item_id))
    if meeting is None:
        meta = await graph.get_drive_item(drive_id, drive_item_id)
        user_node = (meta.get("createdBy", {}).get("user", {}) or {})
        organizer = (
            user_node.get("userPrincipalName")
            or user_node.get("email")
            or owner_upn          # fallback: whoever's drive this file lives in
        )
        meeting = Meeting(
            drive_item_id=drive_item_id,
            title=meta.get("name"),
            organizer_upn=organizer,
        )
        db.add(meeting)
        await db.commit()
        await db.refresh(meeting)

    # Notify participants before any AI processing (POPIA Section 18).
    extra = await graph.get_event_attendees(drive_id, drive_item_id)
    await _send_popia_notice(meeting, extra)

    try:
        with tempfile.TemporaryDirectory() as tmp:
            meeting.state = ProcessingState.downloading
            await db.commit()

            # AssemblyAI accepts MP4 directly — no ffmpeg audio extraction needed
            video_path = os.path.join(tmp, "rec.mp4")
            await graph.download_drive_item(drive_id, drive_item_id, video_path)

            meeting.state = ProcessingState.transcribing
            await db.commit()
            segments = await get_transcriber().transcribe(video_path)
            meeting.transcript = "\n".join(f"[{s.speaker}] {s.text}" for s in segments)

            meeting.state = ProcessingState.extracting
            await db.commit()
            result = await get_extractor().extract(segments)
            meeting.summary = result.summary
            meeting.extracted_json = result.model_dump()
            for ai in result.action_items:
                db.add(ActionItem(
                    meeting_id=meeting.id,
                    task=ai.action or ai.task,
                    owner=ai.assigned_to or ai.owner,
                    deadline_text=ai.due_date or ai.deadline_text,
                    deadline_iso=ai.deadline_iso,
                    confidence=ai.confidence,
                    source_quote=ai.source_quote,
                    raw=ai.model_dump(),
                ))

            if meeting.organizer_upn:
                db.add(MeetingParticipant(
                    meeting_id=meeting.id, user_upn=meeting.organizer_upn, is_organizer=True
                ))

            meeting.state = ProcessingState.awaiting_review
            await db.commit()

    except Exception as e:
        meeting.state = ProcessingState.failed
        meeting.error = str(e)[:2000]
        await db.commit()
        raise
