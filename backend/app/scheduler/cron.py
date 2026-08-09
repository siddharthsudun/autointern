from __future__ import annotations
"""
Daily cron pipeline.
Run directly: python -m app.scheduler.cron
Or schedule via crontab: 0 8 * * * cd /path/to/backend && python -m app.scheduler.cron
"""

import asyncio
import json
import logging
import sys

from app.database import AsyncSessionLocal, init_db
from app.scrapers.yc_scraper import run_yc_scrape
from app.scrapers.careers_scraper import run_jobs_scrape
from app.scrapers.email_enricher import run_email_enrichment
from app.agents.research_agent import run_research_batch
from app.agents.role_matcher import score_unscored_jobs
from app.models.user_profile import UserProfile
from app.config import settings

logging.basicConfig(level=settings.LOG_LEVEL, stream=sys.stdout)
logger = logging.getLogger(__name__)


async def daily_pipeline():
    await init_db()

    with open(settings.USER_PROFILE_PATH) as f:
        profile = UserProfile.from_json(json.load(f))

    async with AsyncSessionLocal() as db:
        logger.info("Step 1/4: YC scrape")
        scraped = await run_yc_scrape(db, hiring_only=True)
        logger.info("Scraped %d companies", scraped)

        logger.info("Step 2/5: Scrape career pages")
        jobs_found = await run_jobs_scrape(db, limit=50)
        logger.info("Found %d new jobs", jobs_found)

        logger.info("Step 3/5: Enrich emails via Firecrawl")
        enriched = await run_email_enrichment(db, limit=100)
        logger.info("Enriched %d jobs with contact emails", enriched)

        logger.info("Step 4/5: Research batch")
        researched = await run_research_batch(db, limit=30)
        logger.info("Researched %d companies", researched)

        logger.info("Step 5/5: Score unmatched jobs")
        scored = await score_unscored_jobs(db, profile=profile, limit=100)
        logger.info("Scored %d jobs", scored)

    logger.info("Daily pipeline complete.")


if __name__ == "__main__":
    asyncio.run(daily_pipeline())
