"""Central auth configuration values.

This file loads OAuth-related settings from environment variables and
defines the Gmail permission scopes used by the auth flow.
"""

import os
from dotenv import load_dotenv

# Load environment variables from .env file to os.environ(memory)
load_dotenv()

def get_oauth_config() -> dict:
    """Build the OAuth client configuration expected by Google libraries."""
    return {
        "web": {
            "client_id": os.getenv("GOOGLE_CLIENT_ID"),
            "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
            "redirect_uris": [os.getenv("GOOGLE_REDIRECT_URI")],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }


GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "openid",
    "https://www.googleapis.com/auth/userinfo.email",
]