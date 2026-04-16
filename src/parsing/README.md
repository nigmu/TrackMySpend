Parsing Module (Stage-2 Filtering)
This folder is responsible for the parsing pipeline starting from ingestion stage-1 rows. Right now, parsing is implemented as a layered stage-2 sender filter that moves eligible rows into the second staging table.

It does not yet create transactions—only stages rows that match parser rules.

Tables & Ownership
Stage-1 (ingestion-owned)
ingestion_parser_staging

Owner: ingestion layer writes
Parser reads: stage-2 filtering in this module
Dedupe: unique on (email_account_id, gmail_message_id)
State column: stage2_status
NULL: not evaluated by stage-2 yet (current default)
done: considered and moved/handled by stage-2
skipped: evaluated and rejected by stage-2 filter
Parser pickup query pattern (fast + safe):

uses WHERE stage2_status IS NULL ORDER BY id ASC LIMIT ?
Stage-2 (parser-owned)
parsing_sender_regex_staging

Owner: parsing layer inserts
Dedupe: unique on (email_account_id, gmail_message_id, matched_pattern)
State column (future): parse_status (currently not used by this stage)
intended for later expansion (LLM parsing / transaction extraction)
Current Stage-2 Rules (Sender Filter)
Parsing currently applies these rules when moving rows from stage-1 → stage-2:

Only consider stage-1 rows where ingestion_parser_staging.stage2_status IS NULL.
For each candidate row:
Read from_header
If from_header contains any keyword from:
src/global_configs.py → PARSER_FROM_HEADER_KEYWORDS
If matched:
insert into parsing_sender_regex_staging with matched_pattern = <keyword>
mark stage-1 row as stage2_status = 'done'
If not matched:
mark stage-1 row as stage2_status = 'skipped'
Notes
Filtering is done on from_header (case-insensitive substring match).
No deletion occurs in stage-2. Rows are tracked via stage2_status.
Keyword Configuration (Where it comes from)
Sender keywords come from:

src/global_configs.py
PARSER_FROM_HEADER_KEYWORDS = [...]
The parsing API endpoints can append new keywords, and it persists by editing that file.

API Endpoints (Parsing)
Mounted under: /parsing

GET /parsing/sender-keywords

Returns current keyword list.
POST /parsing/sender-keywords

Body: { "keyword": "..." }
Appends the keyword if it doesn’t already exist (case-insensitive).
Persists into src/global_configs.py.
POST /parsing/staging/sender-filter/run?limit=200

Runs the stage-2 sender filter for up to limit rows where stage2_status IS NULL.
Returns counters like:
rows_scanned
rows_inserted
skipped_by_from_header_keywords
How to Think About This Pipeline (Now)
Current flow:

Ingestion poll fetches Gmail and stages rows into ingestion_parser_staging
Parsing runs stage-2 filter:
reads only unprocessed stage-1 rows (stage2_status IS NULL)
inserts matches into parsing_sender_regex_staging
updates stage2_status to done or skipped
Future stages (later) should read from parsing_sender_regex_staging and populate transactions while using parse_status.