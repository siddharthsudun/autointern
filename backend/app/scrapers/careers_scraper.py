from __future__ import annotations
"""
Generic careers page scraper.
Given a company website URL, tries to:
  1. Find the careers/jobs page (via common paths + link detection)
  2. Extract job listings (title, URL, location, description)
  3. Return structured results

Uses httpx for simple pages; falls back to Playwright for JS-heavy pages.
"""

import asyncio
import logging
import random
import re
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from app.config import settings

logger = logging.getLogger(__name__)

_CAREER_PATH_HINTS = [
    "/careers", "/jobs", "/join", "/hiring", "/work-with-us",
    "/join-us", "/open-roles", "/opportunities",
]

_JOB_BOARD_DOMAINS: dict = {}  # populated after function definitions below

_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
)


async def scrape_company_jobs(website_url: str) -> list[dict]:
    """
    Entry point: given a company's homepage, return a list of job dicts.
    Each dict: {title, url, location, description_snippet, source}
    """
    if not website_url:
        return []

    careers_url = await _find_careers_page(website_url)
    if not careers_url:
        return []

    domain = urlparse(careers_url).netloc
    for board_domain, extractor in _JOB_BOARD_DOMAINS.items():
        if board_domain in domain:
            return await extractor(careers_url)

    return await _generic_extract(careers_url)


async def _find_careers_page(website_url: str) -> str | None:
    """Try known paths first, then parse homepage links."""
    base = website_url.rstrip("/")

    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        # Fast path: try common paths
        for path in _CAREER_PATH_HINTS:
            url = base + path
            try:
                resp = await client.head(url, headers={"User-Agent": _UA})
                if resp.status_code < 400:
                    return url
            except Exception:
                continue

        # Slow path: parse homepage for career links
        try:
            resp = await client.get(base, headers={"User-Agent": _UA}, timeout=10)
            soup = BeautifulSoup(resp.text, "lxml")
            for a in soup.find_all("a", href=True):
                href = a["href"].lower()
                if any(h.strip("/") in href for h in _CAREER_PATH_HINTS):
                    return urljoin(base, a["href"])
        except Exception:
            pass

    return None


async def _generic_extract(url: str) -> list[dict]:
    """Best-effort extraction from an arbitrary careers page."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            await asyncio.sleep(random.uniform(settings.SCRAPE_DELAY_MIN, settings.SCRAPE_DELAY_MAX))
            resp = await client.get(url, headers={"User-Agent": _UA})
            soup = BeautifulSoup(resp.text, "lxml")

        jobs = []
        # Heuristic: find elements that look like job titles
        for el in soup.find_all(["h2", "h3", "h4", "li", "a"]):
            text = el.get_text(strip=True)
            if _looks_like_job_title(text):
                href = el.get("href") or (el.find("a") or {}).get("href", "")
                jobs.append({
                    "title": text,
                    "url": urljoin(url, href) if href else url,
                    "location": None,
                    "description_snippet": None,
                    "source": "careers_page",
                })
        return jobs[:50]  # cap to avoid noise
    except Exception as e:
        logger.warning("careers_scraper failed for %s: %s", url, e)
        return []


def _looks_like_job_title(text: str) -> bool:
    if len(text) < 5 or len(text) > 120:
        return False
    keywords = [
        "engineer", "developer", "intern", "product", "marketing",
        "designer", "analyst", "manager", "scientist", "operations",
        "growth", "sales", "recruiter", "counsel", "finance",
    ]
    return any(k in text.lower() for k in keywords)


# ---------------------------------------------------------------------------
# Job board-specific extractors
# ---------------------------------------------------------------------------

async def _extract_lever(url: str) -> list[dict]:
    """Lever uses a public JSON API: <company>.lever.co/v0/postings"""
    company_slug = urlparse(url).netloc.split(".")[0]
    api_url = f"https://api.lever.co/v0/postings/{company_slug}?mode=json"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, headers={"User-Agent": _UA})
            postings = resp.json()
        return [
            {
                "title": p.get("text", ""),
                "url": p.get("hostedUrl", ""),
                "location": (p.get("categories") or {}).get("location"),
                "description_snippet": BeautifulSoup(
                    p.get("descriptionPlain", ""), "lxml"
                ).get_text()[:300],
                "source": "lever",
            }
            for p in postings
        ]
    except Exception as e:
        logger.warning("Lever extractor failed for %s: %s", url, e)
        return []


async def _extract_greenhouse(url: str) -> list[dict]:
    """Greenhouse embeds job data as JSON in the page."""
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=20) as client:
            resp = await client.get(url, headers={"User-Agent": _UA})
        soup = BeautifulSoup(resp.text, "lxml")
        jobs = []
        for section in soup.select(".opening"):
            a = section.find("a")
            if a:
                jobs.append({
                    "title": a.get_text(strip=True),
                    "url": urljoin(url, a["href"]),
                    "location": section.select_one(".location") and section.select_one(".location").get_text(strip=True),
                    "description_snippet": None,
                    "source": "greenhouse",
                })
        return jobs
    except Exception as e:
        logger.warning("Greenhouse extractor failed for %s: %s", url, e)
        return []


async def _extract_ashby(url: str) -> list[dict]:
    """Ashby has a public GraphQL API."""
    # Extract company ID from URL pattern: jobs.ashbyhq.com/<company>
    company = urlparse(url).path.strip("/").split("/")[0]
    api_url = "https://api.ashbyhq.com/posting-api/job-board/" + company
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(api_url, headers={"User-Agent": _UA})
            data = resp.json()
        return [
            {
                "title": j.get("title", ""),
                "url": j.get("jobUrl", ""),
                "location": j.get("location"),
                "description_snippet": None,
                "source": "ashby",
            }
            for j in data.get("jobs", [])
        ]
    except Exception as e:
        logger.warning("Ashby extractor failed for %s: %s", url, e)
        return []


async def _extract_workable(url: str) -> list[dict]:
    """Workable exposes a public subdomain API."""
    company = urlparse(url).netloc.split(".")[0]
    api_url = f"https://apply.workable.com/api/v1/widget/accounts/{company}/jobs"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(api_url, json={}, headers={"User-Agent": _UA})
            data = resp.json()
        return [
            {
                "title": j.get("title", ""),
                "url": f"https://apply.workable.com/{company}/j/{j.get('shortcode', '')}",
                "location": j.get("location", {}).get("city"),
                "description_snippet": None,
                "source": "workable",
            }
            for j in data.get("results", [])
        ]
    except Exception as e:
        logger.warning("Workable extractor failed for %s: %s", url, e)
        return []


# Populate after all extractor functions are defined
_JOB_BOARD_DOMAINS = {
    "lever.co": _extract_lever,
    "greenhouse.io": _extract_greenhouse,
    "ashbyhq.com": _extract_ashby,
    "workable.com": _extract_workable,
}


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

async def run_jobs_scrape(db, limit: int = 50) -> int:
    """
    Scrape career pages for hiring companies and upsert jobs into DB.
    Returns count of new jobs inserted.
    """
    from sqlalchemy import select
    from app.models.company import Company
    from app.models.job import Job, JobType, JobFunction
    from datetime import datetime, timezone

    result = await db.execute(
        select(Company).where(Company.is_hiring == True).limit(limit)
    )
    companies = result.scalars().all()

    sem = asyncio.Semaphore(settings.MAX_CONCURRENT_SCRAPERS)
    total = 0

    for company in companies:
        if not company.website:
            continue
        async with sem:
            try:
                raw_jobs = await scrape_company_jobs(company.website)
            except Exception as e:
                logger.warning("Job scrape failed for %s: %s", company.name, e)
                continue

        for rj in raw_jobs:
            source_url = rj.get("url") or ""
            if not source_url or not rj.get("title"):
                continue

            # Skip if already in DB
            existing = await db.execute(
                select(Job).where(
                    Job.company_id == company.id,
                    Job.source_url == source_url,
                )
            )
            if existing.scalar_one_or_none():
                continue

            title = rj["title"].strip()
            job_type = (
                JobType.INTERNSHIP
                if "intern" in title.lower()
                else JobType.FULL_TIME
            )

            job = Job(
                company_id=company.id,
                title=title,
                job_type=job_type,
                function=_infer_function(title),
                source_url=source_url,
                apply_url=source_url,
                source=rj.get("source", "careers_page"),
                location=rj.get("location"),
                description_raw=rj.get("description_snippet"),
                posted_at=datetime.now(timezone.utc),
            )
            db.add(job)
            total += 1

        await db.commit()
        logger.info("Scraped jobs for %s (%d new so far)", company.name, total)

    logger.info("Jobs scrape complete. %d new jobs inserted.", total)
    return total


def _infer_function(title: str) -> "JobFunction":
    from app.models.job import JobFunction
    t = title.lower()
    if any(k in t for k in ["engineer", "developer", "software", "backend", "frontend", "fullstack", "infra", "data"]):
        return JobFunction.ENGINEERING
    if any(k in t for k in ["product", "pm", "program"]):
        return JobFunction.PRODUCT
    if any(k in t for k in ["design", "ux", "ui"]):
        return JobFunction.DESIGN
    if any(k in t for k in ["market", "growth", "content", "brand", "seo"]):
        return JobFunction.MARKETING
    if any(k in t for k in ["sales", "account", "revenue"]):
        return JobFunction.SALES
    if any(k in t for k in ["data", "analyst", "analytics", "ml", "ai", "science"]):
        return JobFunction.DATA
    if any(k in t for k in ["ops", "operation", "finance", "legal", "hr", "recruit"]):
        return JobFunction.OPERATIONS
    return JobFunction.OTHER
