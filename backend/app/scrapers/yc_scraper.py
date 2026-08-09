from __future__ import annotations
"""
YC Company Scraper

Strategy:
  1. Pull companies from YC's public Algolia search index (fast, structured, no JS needed).
  2. For each company marked is_hiring=True, follow their website to discover job listings
     via the careers_scraper.
  3. Persist to DB — upsert on slug so re-runs are safe.

Finding the Algolia keys:
  Open https://www.ycombinator.com/companies in DevTools → Network → filter "algolia".
  You'll see requests to 45bwzj1sgc-dsn.algolia.net. Copy the x-algolia-api-key header value
  and paste it into .env as YC_ALGOLIA_API_KEY. The app ID is hardcoded below (stable).
"""

import asyncio
import logging
import random
import re
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Optional
from urllib.parse import urlencode

import httpx
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.company import Company

logger = logging.getLogger(__name__)

_ALGOLIA_APP_ID = "45BWZJ1SGC"
_ALGOLIA_URL = f"https://{_ALGOLIA_APP_ID.lower()}-dsn.algolia.net/1/indexes/*/queries"
_PAGE_SIZE = 1000  # Algolia max per request


class YCScraperError(Exception):
    pass


async def _get_algolia_key(client: httpx.AsyncClient) -> str:
    """
    Fetch the public (read-only) Algolia search key from the YC companies page.
    This key is embedded in the page JS and is intentionally public.
    """
    from app.config import settings as s
    # Allow override via env to avoid hitting the page every run
    import os
    key = os.environ.get("YC_ALGOLIA_API_KEY", "")
    if key:
        return key

    logger.info("Fetching Algolia key from YC companies page...")
    resp = await client.get(
        "https://www.ycombinator.com/companies",
        headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"},
        follow_redirects=True,
        timeout=20,
    )
    resp.raise_for_status()

    # Key is base64-encoded in AlgoliaOpts JSON block
    match = re.search(r'AlgoliaOpts\s*=\s*\{[^}]*"key"\s*:\s*"([^"]+)"', resp.text)
    if not match:
        raise YCScraperError(
            "Could not auto-extract Algolia key. "
            "Set YC_ALGOLIA_API_KEY in your .env (see module docstring)."
        )
    key = match.group(1)
    logger.info("Extracted Algolia key: %s…", key[:8])
    return key


async def _fetch_page(
    client: httpx.AsyncClient,
    algolia_key: str,
    page: int,
    filters: str = "",
) -> dict[str, Any]:
    params_dict: dict[str, Any] = {
        "hitsPerPage": _PAGE_SIZE,
        "page": page,
        "attributesToRetrieve": "id,name,slug,one_liner,long_description,website,small_logo_url,batch,tags,team_size,location,isHiring",
    }
    if filters:
        params_dict["filters"] = filters

    payload = {
        "requests": [
            {
                "indexName": "YCCompany_production",
                "params": urlencode(params_dict),
            }
        ]
    }

    resp = await client.post(
        _ALGOLIA_URL,
        json=payload,
        headers={
            "x-algolia-application-id": _ALGOLIA_APP_ID,
            "x-algolia-api-key": algolia_key,
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["results"][0]


async def stream_yc_companies(
    hiring_only: bool = False,
    batch: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Async generator — yields one normalized company dict per YC startup.

    Args:
        hiring_only: if True, only fetch companies marked isHiring.
        batch: filter by batch string, e.g. "W24".
    """
    filters_parts: list[str] = []
    if hiring_only:
        filters_parts.append("isHiring:true")
    if batch:
        filters_parts.append(f"batch:{batch}")
    filters = " AND ".join(filters_parts)

    async with httpx.AsyncClient() as client:
        algolia_key = await _get_algolia_key(client)

        # Fetch page 0 to learn total pages
        first_page = await _fetch_page(client, algolia_key, page=0, filters=filters)
        nb_pages = first_page.get("nbPages", 1)
        logger.info("YC scraper: %d pages to fetch (page_size=%d)", nb_pages, _PAGE_SIZE)

        for hit in first_page.get("hits", []):
            yield _normalize(hit)

        for page_num in range(1, nb_pages):
            delay = random.uniform(settings.SCRAPE_DELAY_MIN, settings.SCRAPE_DELAY_MAX)
            await asyncio.sleep(delay)

            page_data = await _fetch_page(client, algolia_key, page=page_num, filters=filters)
            for hit in page_data.get("hits", []):
                yield _normalize(hit)


def _normalize(hit: dict[str, Any]) -> dict[str, Any]:
    """Map Algolia hit → our Company schema dict. Coerce all string fields."""
    def s(v: Any) -> Optional[str]:
        return str(v) if v is not None else None

    return {
        "slug": hit.get("slug") or _slugify(hit.get("name", "")),
        "name": hit.get("name", ""),
        "website": s(hit.get("website")),
        "logo_url": s(hit.get("small_logo_url")),
        "one_liner": s(hit.get("one_liner")),
        "description": s(hit.get("long_description")),
        "yc_batch": s(hit.get("batch")),
        "yc_url": f"https://www.ycombinator.com/companies/{hit.get('slug', '')}",
        "tags": hit.get("tags") or [],
        "team_size": s(hit.get("team_size")),
        "location": s(hit.get("location")),
        "is_hiring": bool(hit.get("isHiring", False)),
    }


def _slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------

async def upsert_companies(db: AsyncSession, companies: list[dict[str, Any]]) -> int:
    """
    Upsert a batch of normalized company dicts into the DB.
    Returns count of rows inserted/updated.
    """
    if not companies:
        return 0

    now = datetime.now(timezone.utc)
    for c in companies:
        c["updated_at"] = now

    stmt = pg_insert(Company).values(companies)
    stmt = stmt.on_conflict_do_update(
        index_elements=["slug"],
        set_={
            "name": stmt.excluded.name,
            "website": stmt.excluded.website,
            "logo_url": stmt.excluded.logo_url,
            "one_liner": stmt.excluded.one_liner,
            "description": stmt.excluded.description,
            "yc_batch": stmt.excluded.yc_batch,
            "yc_url": stmt.excluded.yc_url,
            "tags": stmt.excluded.tags,
            "team_size": stmt.excluded.team_size,
            "location": stmt.excluded.location,
            "is_hiring": stmt.excluded.is_hiring,
            "updated_at": stmt.excluded.updated_at,
        },
    )
    await db.execute(stmt)
    return len(companies)


async def run_yc_scrape(db: AsyncSession, hiring_only: bool = True, batch: str | None = None) -> int:
    """
    Full scrape → upsert pipeline. Returns total companies processed.
    Batches writes every 100 records to avoid giant transactions.
    """
    BATCH_SIZE = 100
    buffer: list[dict] = []
    total = 0

    async for company in stream_yc_companies(hiring_only=hiring_only, batch=batch):
        buffer.append(company)
        if len(buffer) >= BATCH_SIZE:
            count = await upsert_companies(db, buffer)
            total += count
            await db.commit()
            logger.info("Upserted %d companies (total so far: %d)", count, total)
            buffer.clear()

    if buffer:
        count = await upsert_companies(db, buffer)
        total += count
        await db.commit()

    logger.info("YC scrape complete. Total: %d companies", total)
    return total
