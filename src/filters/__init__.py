"""Gmail sender_filters, used only by the mail sync (src/mail/service.py) to
decide which incoming emails to keep.

SMS sender filtering is local to the Android app (PrefsStore/SmsReceiver),
not server-side — the server accepts whatever the phone sends to
POST /sms/ingest_and_parse.
"""
