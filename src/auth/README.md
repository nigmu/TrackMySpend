# Google Auth Flow (TrackMySpend)

This folder contains Gmail OAuth logic split by responsibility:

- `auth.py` entry point
- `routes.py` HTTP layer
- `service.py` business logic
- `db.py` SQL/data access
- `credentials.py` DB-to-Google credentials transformation
- `config.py` environment-driven OAuth config

## Files and Responsibilities

- `auth.py`
  - Entry point for the auth package.
  - Exposes router used by the app.
- `routes.py`
  - Defines HTTP endpoints only.
  - Delegates behavior to `service.py`.
- `service.py`
  - Handles OAuth flow, PKCE state, callback exchange, and account actions.
- `db.py`
  - Contains SQL queries and DB write operations for auth flows.
- `credentials.py`
  - Converts DB token rows into `google.oauth2.credentials.Credentials`.
- `config.py`
  - Loads OAuth client settings from `.env`.
  - Defines Gmail scopes.
- `../security/crypto.py`
  - Holds generic encryption/decryption helpers.
  - Reads/creates the encryption key from `.env` (`ENCRYPTION_KEY`).
  - Used by auth code to secure OAuth tokens in DB.
- `dependencies.py`
  - DB connection dependency used by routes.

## End-to-End Auth Process

1. Client hits `GET /auth/gmail/connect`.
2. `service.py` builds Google `Flow`, generates PKCE values, and redirects to
   Google consent screen.
3. Google calls back to `GET /auth/gmail/callback` with `code` and `state`.
4. The callback validates/restores PKCE state and exchanges code for tokens.
5. Access/refresh tokens are encrypted via `security.crypto.encrypt_text(...)`.
6. Encrypted tokens are saved in `email_accounts` table.
7. Later, helper code in `credentials.py`:
   - reads encrypted tokens from DB,
   - decrypts them with `security.crypto.decrypt_text(...)`,
   - combines them with `.env` OAuth client config,
   - returns `google.oauth2.credentials.Credentials`.

## Data Sources Used

- `.env` variables (read in `config.py` and `security/crypto.py`):
  - `GOOGLE_CLIENT_ID`
  - `GOOGLE_CLIENT_SECRET`
  - `GOOGLE_REDIRECT_URI`
  - `ENCRYPTION_KEY` (auto-generated if missing)
- SQLite DB:
  - `DB/data/trackmyspend.db`
  - `email_accounts` table stores encrypted OAuth tokens.

## Minimal Requirements Before Auth Works

- Google OAuth client configured with redirect URI matching
  `GOOGLE_REDIRECT_URI`.
- App authorized on Google consent screen (test users if app is in testing).
- `email_accounts` table present in DB schema.
- Valid `.env` values loaded before running the app.
