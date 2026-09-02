import json
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from db import init_schema, insert_sms

RELEASES_DIR = Path(__file__).parent / "releases"
UPDATE_JSON = RELEASES_DIR / "update.json"
RELEASES_DIR.mkdir(exist_ok=True)


@asynccontextmanager
async def lifespan(_: FastAPI):
    RELEASES_DIR.mkdir(exist_ok=True)
    init_schema()
    yield


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/releases", StaticFiles(directory=RELEASES_DIR), name="releases")


class SmsIngestRequest(BaseModel):
    sender: str | None = None
    body: str
    received_at: datetime | None = None
    device_id: str | None = None


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/app/update.json")
def app_update():
    if not UPDATE_JSON.is_file():
        return {
            "version_code": 1,
            "version_name": "1.0",
            "apk_url": "",
            "changelog": "",
        }
    return json.loads(UPDATE_JSON.read_text(encoding="utf-8"))


@app.post("/sms/ingest")
def ingest_sms(payload: SmsIngestRequest):
    row_id = insert_sms(
        sender=payload.sender,
        body=payload.body,
        received_at=payload.received_at,
        device_id=payload.device_id,
    )
    return {"status": "ok", "id": row_id}
