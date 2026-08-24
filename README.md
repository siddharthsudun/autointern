# AutoIntern

An AI agent that runs the entire internship hunt end to end: it finds companies, finds the right person to email, researches them, writes a tailored cold email, and sends it. You give it your profile once; it does the outreach.

## Pipeline

```
YC / careers scrape ─▶ email enrichment ─▶ Claude research + role match ─▶
        tailored application draft ─▶ Gmail cold email ─▶ scheduled follow-up
```

1. **Scrape** — pulls companies and open roles (YC directory + company careers pages) via Playwright (`app/scrapers/yc_scraper.py`, `careers_scraper.py`).
2. **Enrich** — finds a real contact email for each company (`app/scrapers/email_enricher.py`).
3. **Research + match** — Claude researches each company and scores role fit against your profile (`app/agents/research_agent.py`, `role_matcher.py`).
4. **Generate** — writes a personalized application / cold email per company (`app/agents/application_generator.py`).
5. **Send** — dispatches through Gmail, with a scheduler for follow-ups (`app/automation/email_sender.py`, `app/scheduler/cron.py`).

## Stack

- **Backend:** FastAPI + PostgreSQL, Playwright for scraping, Claude (Anthropic) for research/scoring/writing
- **Frontend:** React + Vite dashboard to review companies, drafts, and application status
- **Infra:** Docker Compose for the database

## Layout

```
backend/app/scrapers/    yc + careers scraping, email enrichment
backend/app/agents/      research, role matching, application generation (Claude)
backend/app/automation/  email sender, form filler
backend/app/scheduler/   follow-up cron
backend/app/models/      company, job, application, user_profile
frontend/                React/Vite review dashboard
```

## Run

Full setup in [SETUP.md](SETUP.md). Short version:

```bash
docker-compose up db -d
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
cp .env.example .env          # add ANTHROPIC_API_KEY
cp profile.example.json profile.json   # your name, skills, projects
uvicorn app.main:app --reload          # API on :8000
cd ../frontend && npm install && npm run dev   # dashboard on :5173
```

## Note

Secrets (`.env`) and your real `profile.json` are gitignored. Use responsibly: send outreach you'd be comfortable sending by hand, and respect each recipient's and platform's rules.
