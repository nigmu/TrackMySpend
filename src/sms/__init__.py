"""SMS pipeline: TMS Companion -> POST /sms/ingest_and_parse -> raw_sms_data.

The phone pushes each matching SMS. Rows are stored as-is and deduplicated by
content_hash(sender, body, device_id). received_at is stored but not part of
the hash (PDU vs inbox times can differ for the same SMS). A new SMS is
classified in that same request: transactions_sms is written when the
classification has a ledger, processing_status is set, then the request
commits. A duplicate upload leaves both tables unchanged. POST /sms/parse
reclassifies one stored raw SMS. An existing ledger row for that raw id is
overwritten in place, including hand edits. A missing row is inserted. Parse
does not delete a ledger row. GET /sms lists raw_sms_data. GET
/sms/transactions lists the ledger.
Companion catch-up uses GET /sms/latest-received-at (per device_id) as a
watermark after reinstall.
"""
