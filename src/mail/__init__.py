"""Gmail pipeline: OAuth accounts + sender_filters -> raw_mail_data -> transactions.

Sync runs on a poller tick (poller.py) or on demand (POST /sync). Parsing into
transactions happens automatically after every sync, or on demand (POST /parse).

This is a separate, symmetric sibling of src/sms/ (the SMS pipeline). The two
pipelines share no code except the generic utilities in src/core/ and the
cross-cutting src/logs/ event log.
"""
