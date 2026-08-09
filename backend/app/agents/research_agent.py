from __future__ import annotations
import json
import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.llm import call
from app.utils import extract_json as _extract_json
from app.models.company import Company

logger = logging.getLogger(__name__)

_RESEARCH_PROMPT = """\
You are a research assistant helping a student apply for internships at startups.

Company: {name}
YC Batch: {batch}
Website: {website}
Description: {description}
Tags: {tags}

Produce a structured JSON research report. Output ONLY valid JSON, no markdown fences.

{{
  "product_summary": "1-2 sentences on what they build",
  "target_users": "who uses their product",
  "business_model": "how they make money",
  "stage_and_funding": "known funding or Early-stage YC company",
  "founder_background": "brief if known",
  "recent_news": "notable launches or milestones",
  "why_interesting_intern": "2-3 specific reasons to intern here",
  "tone_signals": ["words", "describing", "their", "style"],
  "differentiators": ["what makes them different"],
  "questions_to_reference": ["interesting angles for an application"]
}}"""


async def research_company(company: Company) -> dict:
    prompt = _RESEARCH_PROMPT.format(
        name=company.name,
        batch=company.yc_batch or "Unknown",
        website=company.website or "N/A",
        description=(company.description or company.one_liner or "No description")[:2000],
        tags=", ".join(company.tags or []),
    )

    raw = await call(prompt, fast=False, max_tokens=1024)

    try:
        return json.loads(_extract_json(raw))
    except (json.JSONDecodeError, ValueError):
        logger.warning("Research agent returned invalid JSON for %s", company.name)
        return {"raw": raw, "parse_error": True}


async def run_research_batch(
    db: AsyncSession,
    limit: int = 50,
    force_refresh: bool = False,
) -> int:
    query = select(Company).where(Company.is_hiring == True)
    if not force_refresh:
        query = query.where(Company.research == None)
    query = query.limit(limit)

    result = await db.execute(query)
    companies = result.scalars().all()

    count = 0
    for company in companies:
        company_name = company.name
        try:
            research = await research_company(company)
            company.research = research
            company.research_updated_at = datetime.now(timezone.utc)
            await db.commit()
            count += 1
            logger.info("Researched: %s", company_name)
        except Exception as e:
            logger.error("Research failed for %s: %s", company_name, e)
            await db.rollback()

    return count
