from __future__ import annotations
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.llm import call
from app.utils import extract_json as _extract_json
from app.models.job import Job
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

_MATCH_PROMPT = """\
Score this internship role for the applicant. Output ONLY valid JSON, no markdown.

Applicant:
- Skills: {skills}
- Target roles: {target_roles}
- Bio: {bio}

Job: {title} at {company}
Description: {description}

{{
  "score": <integer 0-100>,
  "reasoning": "<2 sentences>",
  "should_apply": <true or false>
}}

Score above 60 = should_apply true."""


async def score_job(job: Job, profile: UserProfile) -> tuple[float, str]:
    prompt = _MATCH_PROMPT.format(
        skills=", ".join(profile.skills[:20]),
        target_roles=", ".join(profile.target_roles),
        bio=profile.bio[:400],
        title=job.title,
        company=job.company.name if job.company else "Unknown",
        description=(job.description_raw or "")[:800],
    )

    raw = await call(prompt, fast=True, max_tokens=200)
    try:
        data = json.loads(_extract_json(raw))
        return float(data.get("score", 0)), data.get("reasoning", "")
    except Exception:
        return 0.0, "Scoring failed"


async def score_unscored_jobs(db: AsyncSession, profile: UserProfile, limit: int = 200) -> int:
    from sqlalchemy.orm import selectinload

    result = await db.execute(
        select(Job)
        .where(Job.match_score == None, Job.is_active == True)
        .options(selectinload(Job.company))
        .limit(limit)
    )
    jobs = result.scalars().all()

    count = 0
    for job in jobs:
        try:
            score, reasoning = await score_job(job, profile)
            job.match_score = score
            job.match_reasoning = reasoning
            count += 1
        except Exception as e:
            logger.error("Scoring failed for job %d: %s", job.id, e)

    await db.commit()
    logger.info("Scored %d jobs", count)
    return count
