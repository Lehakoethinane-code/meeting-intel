# Meeting Intelligence

Event-driven pipeline: Teams recording lands in OneDrive → reconciliation worker
detects it → downloads via Graph API → transcribes with AssemblyAI (diarized) →
extracts structured meeting notes with Anthropic Claude → emails branded summary
to organiser and participants.

## Architecture

```
OneDrive (any domain user)
        │
        ▼
Reconciliation worker (runs every 15 min)
        │  walks all @taxconsulting.co.za users' Recordings/ folders
        │  deduplication ledger prevents re-processing
        ▼
Download MP4 ─► AssemblyAI transcription (diarized, speaker-labelled)
        │
        ▼
Anthropic Claude extraction (two-pass)
  Pass 1: objective · speakers · discussion points
  Pass 2: action items · deliverables · risks · next steps
        │
        ▼
Postgres (meetings · action_items · participants · processed_items)
        │
        ▼
Email sent from organiser's mailbox via Graph sendMail
  → organiser + all meeting participants
  → Tax Consulting branded HTML template
```

## Key design decisions

- **No fixed user** — reconciliation walks every domain user's OneDrive dynamically.
- **AssemblyAI** for diarized transcription (speaker labels, no ffmpeg needed — accepts MP4 directly).
- **Anthropic Claude** (two-pass) for structured extraction — avoids token-limit truncation on long meetings.
- **organizer_upn fallback** — uses drive-owner UPN when SharePoint App is listed as creator.
- **POPIA notice** fires before any AI processing (Section 18 compliance).
- **Row-level access** — a user sees a meeting only if they appear in `meeting_participants`.
- `AUTO_SEND_EMAIL=true` sends immediately on approval; `false` holds for manual review.

## Local setup

1. Python 3.12 venv: `py -3.12 -m venv .venv && .venv\Scripts\activate`
2. `pip install -r requirements.txt`
3. `cp .env.example .env` — fill in all values (see `.env.example` for required keys)
4. `docker compose up -d db` — starts Postgres on port 5434
5. `alembic upgrade head` — creates all tables
6. API: `uvicorn app.main:app --reload`
7. Reconciliation (manual): `python -m workers.reconcile`

### Webhooks (optional — reconciliation covers this)

Graph must reach your machine over HTTPS. Use `ngrok http 8000`, set `WEBHOOK_BASE_URL`,
then `POST /subscriptions/ensure` to register a subscription per domain user.

## Azure production deployment

### Prerequisites

- Azure CLI installed and logged in (`az login`)
- Docker Desktop running

### One-time resource setup

```bash
# Variables — change these
RG=meeting-intel-rg
LOCATION=southafricanorth
ACR=meetingintelacr
APP_ENV=meeting-intel-env
API_APP=meeting-intel-api
JOB_NAME=meeting-intel-reconcile
PG_SERVER=meeting-intel-pg
PG_DB=meeting_intel
PG_USER=meeting
PG_PASS=<choose-a-strong-password>

# Resource group
az group create --name $RG --location $LOCATION

# Container Registry
az acr create --name $ACR --resource-group $RG --sku Basic --admin-enabled true

# PostgreSQL Flexible Server
az postgres flexible-server create \
  --name $PG_SERVER --resource-group $RG --location $LOCATION \
  --admin-user $PG_USER --admin-password $PG_PASS \
  --sku-name Standard_B1ms --tier Burstable \
  --public-access 0.0.0.0

az postgres flexible-server db create \
  --server-name $PG_SERVER --resource-group $RG --database-name $PG_DB

# Container Apps environment
az containerapp env create --name $APP_ENV --resource-group $RG --location $LOCATION
```

### Build and push image

```bash
az acr login --name $ACR
docker build -t $ACR.azurecr.io/meeting-intel:latest .
docker push $ACR.azurecr.io/meeting-intel:latest
```

### Deploy the API

```bash
az containerapp create \
  --name $API_APP --resource-group $RG \
  --environment $APP_ENV \
  --image $ACR.azurecr.io/meeting-intel:latest \
  --registry-server $ACR.azurecr.io \
  --target-port 8000 --ingress external \
  --min-replicas 1 --max-replicas 2 \
  --env-vars \
    TENANT_ID=<> CLIENT_ID=<> CLIENT_SECRET=<> \
    ALLOWED_DOMAIN=taxconsulting.co.za \
    DATABASE_URL=postgresql+asyncpg://$PG_USER:$PG_PASS@$PG_SERVER.postgres.database.azure.com/$PG_DB \
    ANTHROPIC_API_KEY=<> ASSEMBLYAI_API_KEY=<> \
    ANTHROPIC_MODEL=claude-sonnet-4-6 \
    TRANSCRIBER_IMPL=assemblyai EXTRACTOR_IMPL=anthropic \
    AUTO_SEND_EMAIL=true POPIA_NOTICE_ENABLED=true \
    MAIL_SENDER_UPN=<> WEBHOOK_CLIENT_STATE=<>
```

### Deploy the reconciliation job (runs every 15 minutes)

```bash
az containerapp job create \
  --name $JOB_NAME --resource-group $RG \
  --environment $APP_ENV \
  --image $ACR.azurecr.io/meeting-intel:latest \
  --registry-server $ACR.azurecr.io \
  --trigger-type Schedule \
  --cron-expression "*/15 * * * *" \
  --replica-timeout 600 \
  --command "python" --args "-m" "workers.reconcile" \
  --env-vars \
    TENANT_ID=<> CLIENT_ID=<> CLIENT_SECRET=<> \
    ALLOWED_DOMAIN=taxconsulting.co.za \
    DATABASE_URL=postgresql+asyncpg://$PG_USER:$PG_PASS@$PG_SERVER.postgres.database.azure.com/$PG_DB \
    ANTHROPIC_API_KEY=<> ASSEMBLYAI_API_KEY=<> \
    TRANSCRIBER_IMPL=assemblyai EXTRACTOR_IMPL=anthropic \
    AUTO_SEND_EMAIL=true POPIA_NOTICE_ENABLED=true \
    MAIL_SENDER_UPN=<>
```

### Run migrations on first deploy

```bash
az containerapp exec --name $API_APP --resource-group $RG \
  --command "alembic upgrade head"
```

### Set WEBHOOK_BASE_URL after deploy

```bash
# Get the API URL
API_URL=$(az containerapp show --name $API_APP --resource-group $RG \
  --query properties.configuration.ingress.fqdn -o tsv)

az containerapp update --name $API_APP --resource-group $RG \
  --set-env-vars WEBHOOK_BASE_URL=https://$API_URL

# Register webhook subscriptions for all domain users
curl -X POST https://$API_URL/subscriptions/ensure
```

## Environment variables reference

| Variable | Required | Description |
| --- | --- | --- |
| `TENANT_ID` | Yes | Entra tenant ID |
| `CLIENT_ID` | Yes | App registration client ID |
| `CLIENT_SECRET` | Yes | App registration secret |
| `ALLOWED_DOMAIN` | Yes | e.g. `taxconsulting.co.za` |
| `DATABASE_URL` | Yes | asyncpg connection string |
| `ANTHROPIC_API_KEY` | Yes | Anthropic Claude key |
| `ASSEMBLYAI_API_KEY` | Yes | AssemblyAI key |
| `ANTHROPIC_MODEL` | No | Default: `claude-sonnet-4-6` |
| `TRANSCRIBER_IMPL` | No | `assemblyai` or `mock` |
| `EXTRACTOR_IMPL` | No | `anthropic`, `azure_openai`, or `mock` |
| `MAIL_SENDER_UPN` | Yes | Mailbox emails send from |
| `AUTO_SEND_EMAIL` | No | `true` to send on approval, `false` to hold |
| `POPIA_NOTICE_ENABLED` | No | `true` to send POPIA notice before processing |
| `WEBHOOK_BASE_URL` | No | Public HTTPS URL for Graph webhook delivery |
| `WEBHOOK_CLIENT_STATE` | No | Random string to verify webhook authenticity |
