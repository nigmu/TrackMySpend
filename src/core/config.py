import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres@127.0.0.1:5432/trackmyspend",
)
GOOGLE_CLIENT_ID = os.environ.get("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.environ.get("GOOGLE_CLIENT_SECRET", "")
GOOGLE_REDIRECT_URI = os.environ.get(
    "GOOGLE_REDIRECT_URI",
    "http://localhost:2006/auth/gmail/callback",
)
ENCRYPTION_KEY = os.environ.get("ENCRYPTION_KEY", "")
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:2007")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]
BOOTSTRAP_MESSAGE_COUNT = 50
POLLER_TICK_SEC = 60
PARSE_BATCH_LIMIT = 200
