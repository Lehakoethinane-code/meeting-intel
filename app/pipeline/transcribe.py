import asyncio
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass

import httpx

from ..config import get_settings

settings = get_settings()

_ASSEMBLYAI_BASE = "https://api.assemblyai.com"


@dataclass
class TranscriptSegment:
    speaker: str          # "Speaker A" / "Speaker B" — labels, not real names
    text: str
    start: float
    end: float


class Transcriber(ABC):
    @abstractmethod
    async def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        ...


class MockTranscriber(Transcriber):
    async def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        return [
            TranscriptSegment("Speaker A", "Let's get the SARS compliance report done.", 0.0, 4.0),
            TranscriptSegment("Speaker B", "Sure, I'll try wrap that up early June.", 4.0, 8.0),
            TranscriptSegment("Speaker A", "Great. Sarah, can you confirm the client numbers?", 8.0, 12.0),
        ]


class AssemblyAITranscriber(Transcriber):
    """Diarized transcription via AssemblyAI REST API (direct httpx — no SDK).
    Uploads the MP4, submits for transcription, polls until complete."""

    def _headers(self) -> dict:
        return {"authorization": settings.assemblyai_api_key}

    def _upload(self, audio_path: str) -> str:
        """Upload file to AssemblyAI and return the hosted URL."""
        with open(audio_path, "rb") as f:
            r = httpx.post(
                f"{_ASSEMBLYAI_BASE}/v2/upload",
                headers=self._headers(),
                content=f.read(),
                timeout=300,
            )
        r.raise_for_status()
        return r.json()["upload_url"]

    def _submit(self, upload_url: str) -> str:
        """Submit transcription job, return transcript ID."""
        r = httpx.post(
            f"{_ASSEMBLYAI_BASE}/v2/transcript",
            headers=self._headers(),
            json={
                "audio_url": upload_url,
                "speaker_labels": True,
                "speech_models": ["universal-2"],
            },
            timeout=30,
        )
        r.raise_for_status()
        return r.json()["id"]

    def _poll(self, transcript_id: str) -> dict:
        """Poll until the transcript is complete or errored."""
        url = f"{_ASSEMBLYAI_BASE}/v2/transcript/{transcript_id}"
        while True:
            r = httpx.get(url, headers=self._headers(), timeout=30)
            r.raise_for_status()
            data = r.json()
            if data["status"] == "completed":
                return data
            if data["status"] == "error":
                raise RuntimeError(f"AssemblyAI error: {data.get('error')}")
            time.sleep(5)

    def _transcribe_sync(self, audio_path: str) -> list[TranscriptSegment]:
        print(f"  Uploading to AssemblyAI...", flush=True)
        upload_url = self._upload(audio_path)
        print(f"  Submitting transcription job...", flush=True)
        transcript_id = self._submit(upload_url)
        print(f"  Polling (id={transcript_id})...", flush=True)
        data = self._poll(transcript_id)
        utterances = data.get("utterances") or []
        return [
            TranscriptSegment(
                speaker=f"Speaker {u['speaker']}",
                text=u["text"],
                start=u["start"] / 1000,
                end=u["end"] / 1000,
            )
            for u in utterances
        ]

    async def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._transcribe_sync, audio_path)


def get_transcriber() -> Transcriber:
    if settings.transcriber_impl == "assemblyai":
        return AssemblyAITranscriber()
    return MockTranscriber()
