"""SMS pipeline: TMS Companion -> POST /sms/ingest -> raw_sms_data.

Push-based (no poller, unlike the mail pipeline). Rows are stored as-is and
deduplicated by content_hash(sender, body, device_id) — received_at is stored
but not part of the hash (PDU vs inbox times can differ for the same SMS).
Companion catch-up uses GET /sms/latest-received-at (per device_id) as a
watermark after reinstall. There is no parsing into `transactions` yet —
that is the priority next step for this pipeline.
"""
