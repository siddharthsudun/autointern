# AutoIntern — Setup

## Prerequisites
- Python 3.12+
- Node 20+
- PostgreSQL (or Docker)

---

## 1. Database

```bash
# With Docker (easiest)
docker-compose up db -d

# Or create manually
createdb autointern
```

---

## 2. Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env
# → Fill in ANTHROPIC_API_KEY at minimum

cp profile.example.json profile.json
# → Fill in your real profile (name, skills, projects, etc.)

uvicorn app.main:app --reload
# API at http://localhost:8000
# Docs at http://localhost:8000/docs
```

---

## 3. Frontend

```bash
cd frontend
npm install
npm run dev
# Dashboard at http://localhost:5173
```

---

## 4. First Run

From the dashboard, click **Scrape YC** — this pulls all YC companies into the DB.
Then **Research Batch** to run Claude on each company.

Or run the full pipeline from the CLI:

```bash
cd backend
python -m app.scheduler.cron
```

---

## 5. YC Algolia Key (optional speedup)

The scraper auto-extracts the key from the YC page. To skip that on every run:

1. Open https://www.ycombinator.com/companies in Chrome DevTools
2. Network tab → filter by "algolia"
3. Copy the `x-algolia-api-key` request header value
4. Add to `.env`: `YC_ALGOLIA_API_KEY=<value>`

---

## 6. Gmail App Password (for cold email sending)

No OAuth or Google Cloud project needed.

1. Go to [myaccount.google.com/security](https://myaccount.google.com/security)
2. Enable **2-Step Verification** if not already on
3. Search for **App passwords** → create one (name: "autointern")
4. Copy the 16-character password → add to `.env`:

```
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx
```

That's it.

---

## 7. Daily Cron

```bash
# Add to crontab (runs at 8am daily)
crontab -e
# Add: 0 8 * * * cd /Users/you/autointern/backend && /path/to/.venv/bin/python -m app.scheduler.cron
```

---

## Architecture

```
autointern/
├── backend/
│   └── app/
│       ├── scrapers/        # YC Algolia + careers page scrapers
│       ├── agents/          # Claude-powered: research, matching, generation
│       ├── automation/      # Playwright form filler + Gmail sender
│       ├── api/routes/      # FastAPI endpoints
│       ├── models/          # SQLAlchemy + UserProfile dataclass
│       └── scheduler/       # Daily cron pipeline
└── frontend/
    └── src/
        ├── pages/           # Dashboard
        └── components/      # ApplicationTable, OpportunityFeed, StatusBadge
```

## Application Flow

```
YC Scrape → Career Page Scrape → Research Agent (Claude)
    ↓
Role Matcher (Claude Haiku — cheap)
    ↓
Application Generator (Claude Sonnet — quality)
    ↓
Human Review (PENDING_REVIEW → APPROVED in dashboard)
    ↓
Form Filler (Playwright) OR Gmail Sender
```

## Safety Notes

- Form filler only submits when `APP_ENV=production` AND application status is `APPROVED`
- In dev mode it takes a screenshot instead of submitting
- All scrapers use randomized delays between requests
- LinkedIn is intentionally excluded — respect their ToS
