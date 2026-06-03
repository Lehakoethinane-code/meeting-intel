import asyncio
import json
from abc import ABC, abstractmethod
from ..config import get_settings
from ..schemas import RichExtractionResult, ExtractedActionItem
from ..models import Confidence
from .transcribe import TranscriptSegment

settings = get_settings()


SYSTEM_PROMPT = """You are a meeting intelligence assistant for Tax Consulting SA, a professional tax advisory firm.
Analyse the full transcript and return ONLY valid JSON — no prose, no markdown fences.

Extract every section as completely as possible from what was actually said.
If a section has no content, return an empty list or null — never invent information.

IMPORTANT RULES:
- Be concise. Each field value should be 1-2 sentences max. Bullet points max 2 per speaker.
- discussion_points: capture EVERY topic raised by ANY speaker, no matter how brief.
  Even a single sentence from one speaker that raises a point, states an opinion,
  or clarifies a responsibility counts as a discussion point. Do not omit any speaker's contribution.
- speaker_highlights: for EVERY speaker who appears in the transcript, summarise their
  most important contributions in at most 2 bullet points. Use the speaker label
  (e.g. "Speaker A") if no real name is known.

Return this exact schema:
{
  "objective": "<1-2 sentence purpose of the meeting>",
  "meeting_time": "<time mentioned in the meeting or null>",
  "attendees": ["<name or Speaker label>"],
  "apologies": ["<anyone mentioned as absent>"],
  "platform": "<Microsoft Teams | In-Person | Hybrid | other>",
  "speaker_highlights": [
    {
      "speaker": "<Speaker A | real name if known>",
      "role": "<inferred role e.g. Facilitator, Participant, or null>",
      "key_points": [
        "<most important thing this speaker said or contributed>",
        "<second key point if applicable>"
      ]
    }
  ],
  "discussion_points": [
    {
      "topic": "<topic heading — even one-line topics count>",
      "summary": "<what was said, by whom, including ALL speaker contributions on this topic>",
      "outcome": "<decision, conclusion, or unresolved — never leave blank if something was said>"
    }
  ],
  "action_items": [
    {
      "action": "<specific task to be completed>",
      "assigned_to": "<person responsible>",
      "department": "<team or department if mentioned, else null>",
      "reason": "<why this action is needed>",
      "expected_outcome": "<what success looks like>",
      "due_date": "<date as spoken, e.g. 'end of June' or null>",
      "confidence": "high|medium|low",
      "source_quote": "<exact words from transcript>"
    }
  ],
  "deliverables": [
    {
      "deliverable": "<document, report, or output to be produced>",
      "responsible": "<person responsible>",
      "delivery_method": "<email | SharePoint | Teams | other>",
      "due_date": "<date as spoken or null>",
      "expected_outcome": "<what the deliverable achieves>"
    }
  ],
  "risks": [
    {
      "item": "<risk or challenge identified>",
      "impact": "<potential consequence>",
      "resolution": "<proposed solution or support needed>",
      "owner": "<person responsible for resolving>"
    }
  ],
  "next_steps": ["<bullet point next step>"],
  "next_meeting": {
    "proposed_date": "<date mentioned or null>",
    "proposed_time": "<time mentioned or null>",
    "agenda_focus": "<topics for next meeting or null>"
  },
  "summary": "<2-4 sentence overall meeting summary>"
}"""


def _transcript_to_text(segs: list[TranscriptSegment]) -> str:
    """Flatten diarized segments into a single ``[Speaker X] text`` string for the LLM prompt."""
    return "\n".join(f"[{s.speaker}] {s.text}" for s in segs)


def _parse_raw(raw: str) -> RichExtractionResult:
    """Parse the LLM's raw JSON string into a RichExtractionResult.

    Strips markdown code fences (`` ```json ... ``` ``) that some models add
    even when instructed not to, then deserialises and maps to the schema.
    """
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]
    data = json.loads(raw.strip())
    return RichExtractionResult(
        objective=data.get("objective") or "",
        meeting_time=data.get("meeting_time"),
        attendees=data.get("attendees") or [],
        apologies=data.get("apologies") or [],
        platform=data.get("platform") or "Microsoft Teams",
        speaker_highlights=data.get("speaker_highlights") or [],
        discussion_points=data.get("discussion_points") or [],
        action_items=[ExtractedActionItem(**i) for i in (data.get("action_items") or [])],
        deliverables=data.get("deliverables") or [],
        risks=data.get("risks") or [],
        next_steps=data.get("next_steps") or [],
        next_meeting=data.get("next_meeting"),
        summary=data.get("summary") or "",
    )


class Extractor(ABC):
    """Abstract base class for all AI extraction backends."""

    @abstractmethod
    async def extract(self, segments: list[TranscriptSegment]) -> RichExtractionResult:
        """Extract structured meeting intelligence from transcript segments."""
        ...


class MockExtractor(Extractor):
    """Stub extractor that returns hard-coded results — used in local dev/tests."""

    async def extract(self, segments: list[TranscriptSegment]) -> RichExtractionResult:
        return RichExtractionResult(
            objective="To review the SARS compliance report and confirm client numbers.",
            attendees=["Speaker A", "Speaker B", "Sarah"],
            platform="Microsoft Teams",
            discussion_points=[
                {"topic": "SARS Compliance Report", "summary": "Speaker B to finalise the report by early June.", "outcome": "Report deadline confirmed."},
            ],
            action_items=[
                ExtractedActionItem(
                    action="Finalise SARS compliance report",
                    assigned_to="Speaker B", department=None,
                    reason="Required for client submission",
                    expected_outcome="Report submitted to SARS on time",
                    due_date="early June", confidence=Confidence.medium,
                    source_quote="Sure, I'll try wrap that up early June.",
                ),
                ExtractedActionItem(
                    action="Confirm client numbers",
                    assigned_to="Sarah", department=None,
                    reason="Numbers needed before report can be finalised",
                    expected_outcome="Accurate client count confirmed",
                    due_date=None, confidence=Confidence.low,
                    source_quote="Sarah, can you confirm the client numbers?",
                ),
            ],
            deliverables=[],
            risks=[],
            next_steps=["Sarah to send client numbers by end of week.", "Speaker B to circulate draft report for review."],
            next_meeting=None,
            summary="Team discussed the SARS compliance report and client number confirmation.",
        )


_ACTIONS_PROMPT = """You are a meeting intelligence assistant for Tax Consulting SA.
Given the transcript below, extract ONLY action items, deliverables, risks, and next steps.
Return ONLY valid JSON — no prose, no markdown fences. Be concise (1-2 sentences per field).

Return this exact schema:
{
  "action_items": [
    {"action":"","assigned_to":null,"department":null,"reason":null,"expected_outcome":null,"due_date":null,"confidence":"medium","source_quote":null}
  ],
  "deliverables": [
    {"deliverable":"","responsible":null,"delivery_method":null,"due_date":null,"expected_outcome":null}
  ],
  "risks": [
    {"item":"","impact":null,"resolution":null,"owner":null}
  ],
  "next_steps": [""],
  "next_meeting": {"proposed_date":null,"proposed_time":null,"agenda_focus":null}
}"""


class AnthropicExtractor(Extractor):
    """Two-pass extractor using Anthropic Claude.

    Pass 1 extracts meeting structure, speakers, and discussion points.
    Pass 2 extracts action items, deliverables, risks, and next steps separately
    to avoid the LLM conflating structure with tasks under a single large prompt.
    """

    def _call(self, client, system: str, user: str) -> str:
        """Synchronous Claude API call — run in an executor to avoid blocking the event loop."""
        msg = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=8192,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return msg.content[0].text

    async def extract(self, segments: list[TranscriptSegment]) -> RichExtractionResult:
        import anthropic
        client  = anthropic.Anthropic(api_key=settings.anthropic_api_key)
        text    = _transcript_to_text(segments)
        loop    = asyncio.get_running_loop()

        # Pass 1 — structure, speakers, discussion (no action items)
        p1_system = SYSTEM_PROMPT + "\n\nFor this call, set action_items=[], deliverables=[], risks=[], next_steps=[], next_meeting=null."
        raw1 = await loop.run_in_executor(None, self._call, client, p1_system, text)
        result = _parse_raw(raw1)

        # Pass 2 — action items, deliverables, risks, next steps only
        raw2 = await loop.run_in_executor(None, self._call, client, _ACTIONS_PROMPT, text)
        try:
            data2 = json.loads(raw2.strip().strip("```").lstrip("json").strip())
            result.action_items  = [ExtractedActionItem(**i) for i in (data2.get("action_items") or [])]
            result.deliverables  = data2.get("deliverables") or []
            result.risks         = data2.get("risks") or []
            result.next_steps    = data2.get("next_steps") or []
            result.next_meeting  = data2.get("next_meeting")
        except Exception:
            pass  # keep whatever pass 1 extracted for these fields

        return result


class AzureOpenAIExtractor(Extractor):
    """Single-pass extractor using Azure OpenAI (GPT-4o by default).

    Uses ``response_format=json_object`` so the model is constrained to valid JSON.
    """

    async def extract(self, segments: list[TranscriptSegment]) -> RichExtractionResult:
        from openai import AsyncAzureOpenAI
        client = AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_key,
            api_version="2024-02-01",
        )
        resp = await client.chat.completions.create(
            model=settings.azure_openai_deployment,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": _transcript_to_text(segments)},
            ],
        )
        return _parse_raw(resp.choices[0].message.content)


def get_extractor() -> Extractor:
    """Factory: return the configured extraction backend.

    Controlled by the ``EXTRACTOR_IMPL`` env var (``anthropic`` | ``azure_openai`` | ``mock``).
    """
    if settings.extractor_impl == "anthropic":
        return AnthropicExtractor()
    if settings.extractor_impl == "azure_openai":
        return AzureOpenAIExtractor()
    return MockExtractor()
