from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database import get_db
from app.models.company import Company
from app.scrapers.yc_scraper import run_yc_scrape
from app.agents.research_agent import run_research_batch

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("")
async def list_companies(
    hiring_only: bool = True,
    batch: str | None = None,
    limit: int = Query(50, le=500),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = select(Company)
    if hiring_only:
        q = q.where(Company.is_hiring == True)
    if batch:
        q = q.where(Company.yc_batch == batch)
    q = q.order_by(Company.opportunity_score.desc().nullslast()).limit(limit).offset(offset)
    result = await db.execute(q)
    companies = result.scalars().all()
    return {"companies": [_company_out(c) for c in companies]}


@router.get("/{company_id}")
async def get_company(company_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Company).where(Company.id == company_id))
    company = result.scalar_one_or_none()
    if not company:
        from fastapi import HTTPException
        raise HTTPException(404, "Company not found")
    return _company_out(company, full=True)


@router.post("/scrape/yc")
async def trigger_yc_scrape(
    hiring_only: bool = True,
    batch: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    count = await run_yc_scrape(db, hiring_only=hiring_only, batch=batch)
    return {"scraped": count}


@router.post("/research/batch")
async def trigger_research_batch(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    count = await run_research_batch(db, limit=limit)
    return {"researched": count}


def _company_out(c: Company, full: bool = False) -> dict:
    base = {
        "id": c.id,
        "slug": c.slug,
        "name": c.name,
        "website": c.website,
        "logo_url": c.logo_url,
        "one_liner": c.one_liner,
        "yc_batch": c.yc_batch,
        "tags": c.tags,
        "team_size": c.team_size,
        "location": c.location,
        "is_hiring": c.is_hiring,
        "opportunity_score": c.opportunity_score,
    }
    if full:
        base["description"] = c.description
        base["research"] = c.research
        base["yc_url"] = c.yc_url
    return base
