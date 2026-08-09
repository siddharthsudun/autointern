from __future__ import annotations
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.job import Job, JobType, JobFunction
from app.models.company import Company
from app.scrapers.careers_scraper import run_jobs_scrape
from app.scrapers.email_enricher import run_email_enrichment

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("")
async def list_jobs(
    min_score: float = 0,
    function: JobFunction | None = None,
    internship_only: bool = True,
    limit: int = Query(50, le=200),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Job)
        .where(Job.is_active == True)
        .options(selectinload(Job.company))
        .order_by(Job.match_score.desc().nullslast())
        .limit(limit)
        .offset(offset)
    )
    if min_score > 0:
        q = q.where(Job.match_score >= min_score)
    if function:
        q = q.where(Job.function == function)
    if internship_only:
        q = q.where(Job.job_type == JobType.INTERNSHIP)

    result = await db.execute(q)
    jobs = result.scalars().all()
    return {"jobs": [_job_out(j) for j in jobs]}


@router.get("/top")
async def top_opportunities(db: AsyncSession = Depends(get_db)):
    """Top 10 best opportunities — for the daily feed."""
    q = (
        select(Job)
        .where(Job.is_active == True, Job.match_score >= 60)
        .options(selectinload(Job.company))
        .order_by(Job.match_score.desc())
        .limit(10)
    )
    result = await db.execute(q)
    jobs = result.scalars().all()
    return {"top_jobs": [_job_out(j) for j in jobs]}


@router.post("/scrape")
async def trigger_jobs_scrape(
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
):
    count = await run_jobs_scrape(db, limit=limit)
    return {"scraped": count}


@router.post("/enrich-emails")
async def trigger_email_enrichment(
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    count = await run_email_enrichment(db, limit=limit)
    return {"enriched": count}


def _job_out(j: Job) -> dict:
    c = j.company
    return {
        "id": j.id,
        "title": j.title,
        "company_name": c.name if c else None,
        "company_logo": c.logo_url if c else None,
        "yc_batch": c.yc_batch if c else None,
        "location": j.location,
        "is_remote": j.is_remote,
        "apply_url": j.apply_url,
        "apply_method": j.apply_method,
        "apply_email": j.apply_email,
        "match_score": j.match_score,
        "match_reasoning": j.match_reasoning,
        "source": j.source,
    }
