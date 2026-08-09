from __future__ import annotations
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.llm import call
from app.utils import extract_json as _extract_json
from app.config import settings
from app.models.application import Application, ApplicationStatus
from app.models.job import Job
from app.models.user_profile import UserProfile

logger = logging.getLogger(__name__)

_COLD_EMAIL_PROMPT = """\
Write a cold email from {name} applying for the {title} role at {company_name}.

Company context:
{research_summary}

Applicant:
- Bio: {bio}
- Skills: {skills}
- Projects: {projects}

Rules:
1. Subject: specific — reference something real about the company
2. Open with something specific about what they build — show you get it
3. Body: 2-3 tight paragraphs. One sentence on why you, one ask.
4. NEVER use: "I am writing to express", "passionate about", "synergy", "leverage"
5. Tone: {tone}
6. Max 200 words in body
7. CRITICAL: Only reference real projects and achievements from the applicant profile. No invented numbers, no placeholder text like "X%".

Output ONLY valid JSON, no markdown:
{{"subject": "...", "body": "..."}}"""

_COVER_LETTER_PROMPT = """\
Write a cover letter from {name} for the {title} role at {company_name}.

Company context:
{research_summary}

Applicant:
- Bio: {bio}
- Skills: {skills}
- Projects: {projects}
- Experience: {experience}

Rules:
1. Open with something specific — not your name/school
2. 3 paragraphs: (1) why this company, (2) what you bring, (3) the ask
3. Show don't tell — reference a specific project, not adjectives
4. Tone: {tone}
5. Max 300 words. No headers. No "Dear Hiring Manager".
6. CRITICAL: Do NOT invent numbers, results, or claims not in the applicant profile above. Never use placeholder text like "X%" or "N interviews". If you don't have a specific number, describe the work without one.

Output plain text only."""

_RESUME_TWEAK_PROMPT = """\
Suggest 3-5 resume bullet tweaks to make this resume more relevant for the role.
Do NOT fabricate experience — only reframe existing content.

Job: {title} at {company_name}
Description: {description}

Current bullets:
{resume_bullets}

Output ONLY valid JSON array, no markdown:
[{{"original": "...", "suggested": "...", "reason": "..."}}]"""


async def generate_cold_email(job: Job, profile: UserProfile) -> tuple[str, str]:
    prompt = _COLD_EMAIL_PROMPT.format(
        name=profile.name,
        title=job.title,
        company_name=job.company.name if job.company else "the company",
        research_summary=_summarize_research(job.company.research if job.company else None),
        bio=profile.bio[:400],
        skills=", ".join(profile.skills[:15]),
        projects=_format_projects(profile.projects[:3]),
        tone=", ".join(profile.tone_keywords) if profile.tone_keywords else "direct and genuine",
    )
    raw = await call(prompt, fast=False, max_tokens=600)
    data = json.loads(_extract_json(raw))
    return data["subject"], data["body"]


async def generate_cover_letter(job: Job, profile: UserProfile) -> str:
    prompt = _COVER_LETTER_PROMPT.format(
        name=profile.name,
        title=job.title,
        company_name=job.company.name if job.company else "the company",
        research_summary=_summarize_research(job.company.research if job.company else None),
        bio=profile.bio[:400],
        skills=", ".join(profile.skills[:15]),
        projects=_format_projects(profile.projects[:3]),
        experience=_format_experience(profile.experience[:2]),
        tone=", ".join(profile.tone_keywords) if profile.tone_keywords else "direct and genuine",
    )
    return await call(prompt, fast=False, max_tokens=600)


async def generate_resume_tweaks(job: Job, profile: UserProfile) -> list[dict]:
    bullets = [b for exp in profile.experience for b in exp.get("bullets", [])]
    bullets += [b for proj in profile.projects for b in proj.get("bullets", [])]
    if not bullets:
        return []

    prompt = _RESUME_TWEAK_PROMPT.format(
        title=job.title,
        company_name=job.company.name if job.company else "the company",
        description=(job.description_raw or "")[:1000],
        resume_bullets="\n".join(f"- {b}" for b in bullets[:15]),
    )
    raw = await call(prompt, fast=True, max_tokens=600)
    try:
        return json.loads(_extract_json(raw))
    except Exception:
        return []


async def generate_application(db: AsyncSession, job_id: int, profile: UserProfile) -> Application:
    result = await db.execute(
        select(Job).where(Job.id == job_id).options(selectinload(Job.company))
    )
    job = result.scalar_one()

    subject, email_body = await generate_cold_email(job, profile)
    cover_letter = await generate_cover_letter(job, profile)
    tweaks = await generate_resume_tweaks(job, profile)

    app = Application(
        job_id=job.id,
        status=ApplicationStatus.PENDING_REVIEW,
        cover_letter=cover_letter,
        cold_email_subject=subject,
        cold_email_body=email_body,
        resume_tweaks=tweaks,
        generation_model=(
            f"ollama/{settings.OLLAMA_MODEL}" if settings.USE_OLLAMA else "claude-sonnet-4-6"
        ),
    )
    db.add(app)
    await db.commit()
    await db.refresh(app)
    return app


def _summarize_research(research: dict | None) -> str:
    if not research:
        return "No research available."
    parts = []
    for key in ["product_summary", "target_users", "why_interesting_intern", "recent_news"]:
        val = research.get(key)
        if val:
            parts.append(f"{key.replace('_', ' ').title()}: {val}")
    return "\n".join(parts) or "No research available."


def _format_projects(projects: list) -> str:
    lines = []
    for p in projects:
        tech = ", ".join(p.get("technologies", []))
        lines.append(f"- {p.get('name','')}: {p.get('description','')}" + (f" [{tech}]" if tech else ""))
    return "\n".join(lines) or "None listed."


def _format_experience(experience: list) -> str:
    return "\n".join(
        f"- {e.get('role','')} at {e.get('company','')} ({e.get('duration','')})"
        for e in experience
    ) or "None listed."
