import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .auth.auth import router as gmail_router
from .ingestion.ingest import router as ingestion_router
from .parsing.parser import router as parsing_router

load_dotenv()

# Required for OAuth flow over plain HTTP on localhost during development
os.environ.setdefault("OAUTHLIB_INSECURE_TRANSPORT", "1")

app = FastAPI(
    title="TrackMySpend",
    description="Personal finance tracker API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(gmail_router)
app.include_router(ingestion_router)
app.include_router(parsing_router)


@app.get("/")
def root():
    return {"status": "running", "message": "TrackMySpend API is up."}