import base64
import re

from googleapiclient.discovery import build

from src.auth.credentials import build_gmail_credentials_for_email


def _decode_body_data(data_b64: str) -> str:
    return base64.urlsafe_b64decode(data_b64).decode("utf-8", errors="replace")


def _html_to_text(html: str) -> str:
    # Lightweight HTML cleanup so terminal output shows readable content.
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", html)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?s)<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ")
    text = text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    # Collapse whitespace (use \s not \\s — \\s matches literal backslash-s)
    return re.sub(r"\s+", " ", text).strip()


def extract_body(payload: dict) -> str:
    """Extract text from Gmail message payload (single-part or multipart)."""
    mime = payload.get("mimeType", "")

    if "parts" in payload:
        plain = ""
        html = ""
        for part in payload["parts"]:
            sub_mime = part.get("mimeType", "")
            if sub_mime.startswith("multipart/"):
                inner = extract_body(part)
                if inner:
                    return inner
            body = part.get("body") or {}
            data = body.get("data")
            if not data:
                continue
            text = _decode_body_data(data)
            if sub_mime == "text/plain":
                plain = text or plain
            elif sub_mime == "text/html":
                html = text or html
        if plain.strip():
            return plain.strip()
        if html.strip():
            return _html_to_text(html)
        return ""

    body = payload.get("body") or {}
    data = body.get("data")
    if data:
        decoded = _decode_body_data(data)
        if mime == "text/html":
            return _html_to_text(decoded)
        return decoded.strip()
    return ""

# nigamananda7161@gmail.com
# jaaganamrita@gmail.com
creds = build_gmail_credentials_for_email("jaaganamrita@gmail.com")

service = build("gmail", "v1", credentials=creds)

res = service.users().messages().list(userId="me", maxResults=5, q="in:inbox").execute()
msgs = res.get("messages", [])
if not msgs:
    print("No inbox messages found.")
else:
    msg = service.users().messages().get(userId="me", id=msgs[0]["id"], format="full").execute()
    headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
    body_text = extract_body(msg["payload"])
    if not body_text:
        body_text = msg.get("snippet", "")

    print("Subject:", headers.get("Subject"))
    print("From:", headers.get("From"))
    print("Date:", headers.get("Date"))
    # One f-string so print() does not insert spaces between arguments
    print(f"Body:\n{body_text}")
    # print("Body:\n", msg["payload"]["parts"][0]["body"]["data"])
