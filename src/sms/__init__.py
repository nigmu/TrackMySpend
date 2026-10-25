"""SMS pipeline: TMS Companion -> POST /sms/ingest_and_parse -> raw_sms_data.

Push-based (no poller, unlike the mail pipeline). Rows are stored as-is and
deduplicated by content_hash(sender, body, device_id) — received_at is stored
but not part of the hash (PDU vs inbox times can differ for the same SMS).
A new SMS is classified in that same request: transactions_sms is written when
the classification has a ledger, processing_status is set, then the request
commits. A duplicate upload leaves both tables unchanged. POST /sms/parse_all
reclassifies every raw row, deletes and rewrites that row's ledger, and
returns total, done, ignored, unmatched. GET /sms/transactions lists the
ledger. Mail `transactions` is not used for SMS.
Companion catch-up uses GET /sms/latest-received-at (per device_id) as a
watermark after reinstall.
"""
