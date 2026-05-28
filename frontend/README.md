# TrackMySpend — frontend

Vanilla HTML/CSS/JS control panel for the FastAPI backend.

## Run

1. Start the API (from repo root):

   ```bash
   python main.py
   ```

2. Serve this folder (from `frontend/`):

   ```bash
   python -m http.server 8080
   ```

3. Open [http://localhost:8080](http://localhost:8080)

The API must be running at `http://localhost:8000` (editable in the sidebar). CORS allows `localhost:8080`.

## Pages

- **Home** — API health and counts
- **Accounts** — Gmail connect / list / polling / active / remove
- **Pipeline** — sync mail, stage 1→2, load transactions
- **Keywords** — sender filter keywords
- **Transactions** — parsed rows from `GET /pipeline/transactions`
