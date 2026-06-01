# Meeting Intelligence

Event-driven pipeline: Teams recording lands in SharePoint → Graph webhook →
Service Bus queue → worker downloads + transcribes (diarized) + extracts action
items (grounded, confidence-scored) → **human review gate** → optional email.

## Architecture at a glance

```
Graph webhook ─┐
               ├─► dedupe ledger (drive item id) ─► Service Bus ─► worker
delta reconcile┘                                                    │
                                                                    ▼
                          download ─► ffmpeg ─► transcribe ─► extract ─► Postgres
                                                                    │
                                                          state = awaiting_review
                                                                    │
                                            organizer reviews/edits/approves (API)
                                                                    │
                                                    (optional) Graph sendMail
```

Design decisions baked in (from the architecture discussion):
- **Webhook + delta reconciliation**, deduped on Graph drive-item id (`services/ledger.py`).
- **Diarized transcription** as a separate layer from reasoning (`pipeline/transcribe.py`).
- **Grounded extraction**: every action item has a `source_quote`; vague dates stay
  as `deadline_text`, `deadline_iso` only when unambiguous; `confidence` is an enum.
- **Full-transcript extraction** (not chunked) so cross-references survive.
- **Human review gate**: nothing emails until approved (`AUTO_SEND_EMAIL=false`).
- **Row-level access**: a user sees a meeting only if they're in `meeting_participants`.
- **DLQ/retry** for free via Service Bus abandon-on-error.

## Local setup (VS Code)

1. `python -m venv .venv && source .venv/bin/activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` and fill in TENANT_ID / CLIENT_ID / CLIENT_SECRET.
   Leave `TRANSCRIBER_IMPL=mock` and `EXTRACTOR_IMPL=mock` for now.
4. `docker compose up -d db`
5. Create tables (quick start): a one-off `Base.metadata.create_all` script, or
   wire Alembic (`alembic.ini` placeholder included) for migrations.
6. Run the API: `uvicorn app.main:app --reload`
7. Run the worker (separate terminal): `python -m app.queue.worker`
8. Reconciliation (cron): `python -m workers.reconcile`

### Webhooks in dev
Graph must reach your machine over HTTPS. Use `ngrok http 8000`, put the URL in
`WEBHOOK_BASE_URL`, then `POST /subscriptions/ensure` to register the subscription.
Renew it on a schedule before the ~3-day expiry (same endpoint).

## Going to production
- Swap `TRANSCRIBER_IMPL=azure_speech` and `EXTRACTOR_IMPL=azure_openai`, add keys.
- Persist the delta link and processed ledger (already in Postgres) — don't keep
  `_DELTA_STATE` in memory.
- Deploy API + worker as separate Azure Container Apps; reconciliation as a Job.
- Replace the `X-User-Upn` header auth in `api/reviews.py` with real Entra token
  validation (validate audience, issuer, signature; map `preferred_username`→UPN).

## Still TODO before v1 ships (process, not code)
- Recording-consent / AI-analysis notice to participants (POPIA).
- Blob retention + auto-deletion lifecycle policy.
- Speaker-label → real-name mapping (organizer corrects in review, or voice enrollment).
