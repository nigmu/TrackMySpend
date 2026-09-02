from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from db import init_schema, insert_sms


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_schema()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class SmsIngestRequest(BaseModel):
    sender: str | None = None
    body: str
    received_at: datetime | None = None
    device_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/sms/ingest")
def ingest_sms(payload: SmsIngestRequest):
    row_id = insert_sms(
        sender=payload.sender,
        body=payload.body,
        received_at=payload.received_at,
        device_id=payload.device_id,
    )
    return {"status": "ok", "id": row_id}
