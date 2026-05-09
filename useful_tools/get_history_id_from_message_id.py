# This script lets you get the history id from a message id for a given account id
# It uses the Gmail API to get the history id from the message id

import socket
import time

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from httplib2.error import ServerNotFoundError

from src.db.connection import connect
from src.ingestion.gmail_client import _build_creds


# current history id for account id 3 = 3157370
# current message id for account id 4 = 326064


account_id = 4
message_id = "19da4476c4b26e58"  # set a real Gmail message id here

conn = connect()
row = conn.execute("""
    SELECT email_address, oauth_access_token, oauth_refresh_token
    FROM user_email_accounts
    WHERE id = %s
""", (account_id,)).fetchone()
conn.close()

if not row:
    raise ValueError(f"No user_email_accounts row found for account_id={account_id}")

gmail = build("gmail", "v1", credentials=_build_creds(row["oauth_access_token"], row["oauth_refresh_token"]))

if not message_id or message_id == "PUT_GMAIL_MESSAGE_ID_HERE":
    raise ValueError("Set `message_id` in temp.py before running.")

def fetch_message_with_retry(max_attempts: int = 3, sleep_sec: float = 1.5) -> dict:
    for attempt in range(1, max_attempts + 1):
        try:
            return gmail.users().messages().get(
                userId="me",
                id=message_id,
                format="metadata",
            ).execute()
        except HttpError as exc:
            status = getattr(getattr(exc, "resp", None), "status", None)
            if status == 404:
                raise ValueError(
                    f"Message ID {message_id} not found in mailbox {row['email_address']}. "
                    "Try a message id from this same account."
                ) from exc
            raise ValueError(f"Gmail API error ({status}): {exc}") from exc
        except (ServerNotFoundError, socket.gaierror) as exc:
            if attempt == max_attempts:
                raise ValueError(
                    "Network/DNS issue while contacting Gmail API "
                    "(gmail.googleapis.com). Check internet/VPN/DNS and retry."
                ) from exc
            time.sleep(sleep_sec)


full = fetch_message_with_retry()
headers = {h.get("name"): h.get("value") for h in full.get("payload", {}).get("headers", [])}

print("account_email:", row["email_address"])
print("message_id:", full.get("id"))
print("history_id:", full.get("historyId"))
print("date_header:", headers.get("Date"))
print("internal_date_ms:", full.get("internalDate"))