"""Central application configuration loaded from environment variables.

This module replaces the legacy `src/global_configs.py`. Other modules
should import settings from here, not write back to this file.
"""

import os

from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:nigmu@127.0.0.1:5432/trackmyspend",
)

# Default sender keyword seed used only when the `filter_keywords` table
# is empty. Runtime updates go to the DB, never back to this file.
DEFAULT_PARSER_FROM_HEADER_KEYWORDS = [
    # "hdfcbank.bank.in",
]
