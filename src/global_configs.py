import os

from dotenv import load_dotenv

# Load .env before DATABASE_URL is read so CLI tools (e.g. db_create.py) match the app.
load_dotenv()

# PostgreSQL connection string, e.g. postgresql://user:pass@localhost:5432/trackmyspend
DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:nigmu@127.0.0.1:5432/trackmyspend",
)

# Parser sender keyword filters used for second staging step.
# Updated at runtime via parsing API endpoints.
PARSER_FROM_HEADER_KEYWORDS = [
    "hdfcbank.bank.in",
]
