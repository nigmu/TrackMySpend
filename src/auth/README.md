# Auth Module (Google Gmail OAuth)

This folder implements Gmail OAuth for TrackMySpend with a layered design:

- `auth.py` -> entry point
- `routes.py` -> HTTP layer
- `service.py` -> business logic
- `db.py` -> SQL and persistence
- `credentials.py` -> DB row to Google `Credentials`
- `config.py` -> env-based OAuth configuration
- `src/security/crypto.py` -> shared encryption/decryption utilities

The app mounts this router under `/auth/gmail`.

## Architecture and Responsibilities

- `auth.py`
  - Exposes the auth router as the module entry point.
  - Keeps app integration simple (`app.include_router(...)`).

- `routes.py`
  - Defines endpoint paths, params, and dependency wiring.
  - Calls service methods; contains no OAuth/SQL logic.

- `service.py`
  - Handles OAuth connect/callback flow.
  - Manages PKCE `state` + `code_verifier` in memory with TTL cleanup.
  - Performs Google token exchange and user info lookup.
  - Encrypts token values before persistence.
  - Implements account state updates (polling interval, active flag, delete).

- `db.py`
  - Contains all `email_accounts` SQL reads/writes.
  - No FastAPI or Google SDK logic.

- `credentials.py`
  - Reads encrypted tokens from DB.
  - Decrypts with `security.crypto`.
  - Builds `google.oauth2.credentials.Credentials` for Gmail API usage.

- `config.py`
  - Loads OAuth config from environment.
  - Defines Gmail scopes used throughout auth and ingestion.

- `src/security/crypto.py`
  - Generic text encryption/decryption.
  - Reads `ENCRYPTION_KEY` from `.env` (creates one if missing).

## Detailed OAuth Flow

1. Client calls `GET /auth/gmail/connect`.
2. Service creates a Google OAuth `Flow` using values from `config.py`.
3. Service requests authorization URL with:
   - `access_type=offline` (refresh token support)
   - `prompt=consent`
   - granted scopes from `GMAIL_SCOPES`
4. Service stores PKCE context in memory:
   - key: OAuth `state`
   - value: `(code_verifier, created_at_monotonic)`
5. User is redirected to Google consent page.
6. Google redirects back to `GET /auth/gmail/callback?code=...&state=...`.
7. Service validates `state`, restores `code_verifier`, and exchanges `code` for tokens.
8. Service calls Google userinfo API to get the account email address.
9. Service encrypts access/refresh tokens with `encrypt_text(...)`.
10. Service upserts `email_accounts`:
    - existing email -> update tokens + mark active
    - new email -> insert new row
11. Callback returns JSON status payload.

## Database Contract

Auth currently persists OAuth details in `email_accounts`:

- `email_address` (unique identity key)
- `oauth_access_token` (encrypted)
- `oauth_refresh_token` (encrypted)
- `polling_interval_min`
- `last_polled_at`
- `is_active`
- `created_at`

No plaintext token is written to DB.

## Environment Variables

Required `.env` keys:

- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `ENCRYPTION_KEY` (auto-created by `security/crypto.py` if missing)

Notes:

- `GOOGLE_REDIRECT_URI` must exactly match the URI configured in Google Cloud.
- In local development, app sets insecure transport for OAuth over HTTP localhost.

## Final API Endpoints

Base prefix: `/auth/gmail`

- `GET /connect`
  - Starts OAuth and redirects to Google.
  - Response: `307 Temporary Redirect`.

- `GET /callback?code=<code>&state=<state>`
  - Handles OAuth callback and stores/updates encrypted tokens.
  - Success response example:
    - `{"status":"connected","email":"user@gmail.com","message":"..."}`
    - `{"status":"reconnected","email":"user@gmail.com","message":"..."}`
  - Common error responses:
    - invalid/expired state
    - token exchange failure
    - user info fetch failure

- `GET /accounts`
  - Lists connected Gmail accounts.
  - Returns array of account rows (safe fields only).

- `DELETE /accounts/{account_id}`
  - Best-effort token revocation at Google.
  - Deletes account row from DB.

- `PATCH /accounts/{account_id}/polling?interval_min=<int>`
  - Updates polling interval.
  - Validation: minimum is 5 minutes.

- `PATCH /accounts/{account_id}/active?is_active=<bool>`
  - Activates/deactivates account.
  - `true` -> active, `false` -> inactive.

## How Ingestion Uses Auth Output

Ingestion/poller layer uses `email_accounts` + `credentials.py`:

1. select active accounts (`is_active = 1`)
2. decrypt stored tokens into Google credentials
3. fetch messages from Gmail API
4. update `last_polled_at`

This keeps OAuth concerns inside auth module while letting ingestion reuse credentials safely.
