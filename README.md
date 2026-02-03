# Event Scrapper — Minimal Assignment Implementation

This project contains a minimal backend (Flask) that scrapes public event listings for Sydney and a tiny Next.js frontend scaffold to display events.

Files added:
- `app.py` — Flask backend, SQLite via SQLAlchemy, scheduler, API endpoints `/api/events` and `/api/scrape`.
- `scrapers/` — two simple scrapers: `allevents` and `eventfinda`.
- `requirements.txt` — Python dependencies.
- `frontend/` — minimal Next.js scaffold (pages to fetch backend data).

How to run (backend):

1. Create a virtualenv and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2. Run the backend:

```bash
python app.py
```

The backend will run at `http://localhost:5000`. It does an initial scrape on start and then every 30 minutes.

API:
- `GET /api/events` — returns active events (can pass `?city=Sydney`).
- `POST /api/scrape` — trigger a manual scrape.

Frontend (Next.js):

The `frontend/` folder contains a minimal Next.js app. To run it:

```bash
cd frontend
npm install
npm run dev
```

The frontend will run at `http://localhost:3000` and fetch events from the backend at `http://localhost:5000/api/events`.

Docker (recommended for quick local deploy):

1. Build and start services:

```bash
docker-compose up --build
```

This will run the backend on port 5000 and the frontend on port 3000 (frontend is configured to call the backend service).

Tests:

Run unit tests and integration tests with pytest:

```bash
pytest -q
```

Notes and limitations:
- Scrapers are lightweight HTML parsers and may need selector updates if the target sites change.
- For production, add rate-limiting, error handling, robust deduplication, and respect robots.txt / site terms.
