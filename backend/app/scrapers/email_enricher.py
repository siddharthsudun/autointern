from __future__ import annotations
"""
Email enrichment using Firecrawl.

For each cold-outreach job with no apply_email, scrapes the company website
to find a real founder or contact email. Strategy (credit-efficient):
  1. Scrape homepage markdown → regex extract
  2. Try /about, /team, /contact one at a time until email found
  3. Fall back to LLM extract on the YC company page
  4. Skip company if still nothing — don't guess
"""

import asyncio
import logging
import re
from urllib.parse import urlparse

from firecrawl.v1 import AsyncV1FirecrawlApp
from firecrawl.v1.client import V1JsonConfig

from app.config import settings

logger = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")

_NOISE = {"noreply", "no-reply", "example", "test", "placeholder", "support@",
          "info@info", "email@email", "user@"}
_PRIORITY_PREFIXES = ("founder", "ceo", "hello", "hi", "contact", "team", "reach", "apply")

_SUBPATHS = ["/about", "/team", "/founders", "/contact", "/company", "/people"]


def _make_client() -> AsyncV1FirecrawlApp:
    return AsyncV1FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)


def _clean_emails(raw: list[str], domain: str) -> list[str]:
    """Filter noise, deduplicate, sort by priority."""
    seen: set[str] = set()
    out: list[str] = []
    for email in raw:
        e = email.lower().strip()
        if e in seen:
            continue
        if any(n in e for n in _NOISE):
            continue
        # Skip emails from completely different domains (e.g. sentry.io in error snippets)
        email_domain = e.split("@")[-1]
        if domain and not (email_domain == domain or domain.endswith("." + email_domain)):
            continue
        seen.add(e)
        out.append(e)

    # Sort: exact-domain matches first, then by prefix priority
    def rank(e: str) -> int:
        prefix = e.split("@")[0]
        for i, p in enumerate(_PRIORITY_PREFIXES):
            if p in prefix:
                return i
        return len(_PRIORITY_PREFIXES)

    return sorted(out, key=rank)


async def _scrape_markdown(client: AsyncV1FirecrawlApp, url: str) -> str:
    try:
        resp = await client.scrape_url(url, formats=["markdown"], timeout=20000, only_main_content=True)
        return resp.markdown or ""
    except Exception as e:
        logger.debug("Firecrawl scrape failed %s: %s", url, e)
        return ""


async def _llm_extract_email(client: AsyncV1FirecrawlApp, url: str, company_name: str) -> str | None:
    """Use Firecrawl LLM extraction as last resort to find a real contact email."""
    try:
        resp = await client.scrape_url(
            url,
            formats=["extract"],
            extract=V1JsonConfig(
                prompt=(
                    f"Find the best email address to reach the founders or CEO of {company_name}. "
                    "Return only a real email address visible on the page — do NOT invent one. "
                    "Prefer founder, CEO, hello@, or contact@ emails over generic support emails."
                ),
                schema_field={
                    "type": "object",
                    "properties": {"email": {"type": "string"}},
                    "required": ["email"],
                },
            ),
            timeout=30000,
        )
        if resp.extract and isinstance(resp.extract, dict):
            email = resp.extract.get("email", "")
            if email and "@" in email and "example" not in email:
                return email.lower().strip()
    except Exception as e:
        logger.debug("LLM extract failed for %s: %s", url, e)
    return None


async def find_company_email(
    client: AsyncV1FirecrawlApp,
    website: str,
    yc_url: str | None,
    company_name: str,
) -> str | None:
    """
    Find the best contact email for a company. Returns None if nothing credible found.
    Uses at most ~4 Firecrawl credits per company.
    """
    domain = urlparse(website).netloc.lstrip("www.")
    base = website.rstrip("/")

    # Step 1: homepage
    text = await _scrape_markdown(client, base)
    emails = _clean_emails(_EMAIL_RE.findall(text), domain)
    if emails:
        logger.debug("Email via homepage for %s: %s", company_name, emails[0])
        return emails[0]

    # Step 2: common subpaths — stop as soon as we find one
    for path in _SUBPATHS:
        text = await _scrape_markdown(client, base + path)
        emails = _clean_emails(_EMAIL_RE.findall(text), domain)
        if emails:
            logger.debug("Email via %s for %s: %s", path, company_name, emails[0])
            return emails[0]
        await asyncio.sleep(0.3)

    # Step 3: LLM extract on YC page (richest info source)
    if yc_url:
        email = await _llm_extract_email(client, yc_url, company_name)
        if email:
            logger.debug("Email via YC LLM for %s: %s", company_name, email)
            return email

    logger.debug("No email found for %s", company_name)
    return None


async def run_email_enrichment(db, limit: int = 100) -> int:
    """
    Populate apply_email on cold-outreach jobs that are missing it.
    One Firecrawl client shared across all requests. Caches per company.
    Returns count of jobs enriched.
    """
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    from app.models.job import Job

    if not settings.FIRECRAWL_API_KEY:
        logger.error("FIRECRAWL_API_KEY not set — skipping email enrichment")
        return 0

    result = await db.execute(
        select(Job)
        .where(Job.apply_method == "email", Job.apply_email == None, Job.is_active == True)
        .options(selectinload(Job.company))
        .limit(limit)
    )
    jobs = result.scalars().all()

    if not jobs:
        logger.info("No jobs need email enrichment")
        return 0

    client = _make_client()
    company_cache: dict[int, str | None] = {}
    count = 0

    for job in jobs:
        company = job.company
        if not company or not company.website:
            continue

        if company.id not in company_cache:
            email = await find_company_email(
                client, company.website, company.yc_url, company.name
            )
            company_cache[company.id] = email
        else:
            email = company_cache[company.id]

        if email:
            job.apply_email = email
            count += 1
            logger.info("Enriched %-30s → %s", company.name, email)

        # Polite delay between companies
        await asyncio.sleep(0.5)

    await db.commit()
    logger.info("Email enrichment complete: %d / %d jobs enriched", count, len(jobs))
    return count
