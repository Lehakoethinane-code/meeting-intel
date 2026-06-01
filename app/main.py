from fastapi import FastAPI
from .api import webhooks, reviews, subscriptions

app = FastAPI(title="Meeting Intelligence")
app.include_router(webhooks.router, tags=["webhooks"])
app.include_router(reviews.router, tags=["reviews"])
app.include_router(subscriptions.router, tags=["subscriptions"])


@app.get("/health")
async def health():
    return {"status": "ok"}
