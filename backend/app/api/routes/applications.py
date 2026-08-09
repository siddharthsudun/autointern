from __future__ import annotations
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from pydantic import BaseModel

from app.database import get_db
from app.models.application import Application, ApplicationStatus
from app.models.job import Job
from app.models.user_profile import UserProfile
from app.agents.application_generator import generate_application
from app.automation.email_sender import send_cold_email
from app.automation.form_filler import submit_application
from app.config import settings

router = APIRouter(prefix="/applications", tags=["applications"])


class StatusUpdate(BaseModel):
    status: ApplicationStatus
    notes: str | None = None


@router.get("")
async def list_applications(
    status: ApplicationStatus | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(Application)
        .options(selectinload(Application.job).selectinload(Job.company))
        .order_by(Application.created_at.desc())
    )
    if status:
        q = q.where(Application.status == status)
    result = await db.execute(q)
    apps = result.scalars().all()
    return {"applications": [_app_out(a) for a in apps]}


@router.post("/generate/{job_id}")
async def generate(job_id: int, db: AsyncSession = Depends(get_db)):
    profile = _load_profile()
    app = await generate_application(db, job_id=job_id, profile=profile)
    return _app_out(app)


@router.patch("/{app_id}/status")
async def update_status(app_id: int, body: StatusUpdate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Application).where(Application.id == app_id))
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(404, "Application not found")
    app.status = body.status
    if body.notes:
        app.notes = body.notes
    await db.commit()
    return {"id": app_id, "status": app.status}


@router.post("/{app_id}/send")
async def send_application(app_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .where(Application.id == app_id)
        .options(selectinload(Application.job).selectinload(Job.company))
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(404, "Application not found")
    if app.status != ApplicationStatus.APPROVED:
        raise HTTPException(400, f"Application is {app.status}, not approved")

    profile = _load_profile()
    job = app.job

    if job.apply_method == "email" and app.cold_email_body:
        if not job.apply_email:
            raise HTTPException(400, "No contact email found for this job — run Enrich Emails first")
        try:
            msg_id = await send_cold_email(
                to=job.apply_email,
                subject=app.cold_email_subject or f"Internship Application – {job.title}",
                body=app.cold_email_body,
            )
        except RuntimeError as e:
            raise HTTPException(400, str(e))
        app.sent_via = "email"
        app.confirmation_id = msg_id
    else:
        ok = await submit_application(app, profile)
        if not ok:
            raise HTTPException(422, "Form submission failed or requires manual review")
        app.sent_via = "form"

    from datetime import datetime, timezone
    app.status = ApplicationStatus.SENT
    app.sent_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": app_id, "status": app.status, "sent_via": app.sent_via}


@router.get("/{app_id}")
async def get_application(app_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Application)
        .where(Application.id == app_id)
        .options(selectinload(Application.job).selectinload(Job.company))
    )
    app = result.scalar_one_or_none()
    if not app:
        raise HTTPException(404, "Application not found")
    return _app_out(app, full=True)


def _load_profile() -> UserProfile:
    with open(settings.USER_PROFILE_PATH) as f:
        return UserProfile.from_json(json.load(f))


def _app_out(a: Application, full: bool = False) -> dict:
    job = a.job
    company = job.company if job else None
    base = {
        "id": a.id,
        "status": a.status,
        "job_title": job.title if job else None,
        "company_name": company.name if company else None,
        "company_logo": company.logo_url if company else None,
        "sent_via": a.sent_via,
        "sent_at": a.sent_at.isoformat() if a.sent_at else None,
        "created_at": a.created_at.isoformat(),
    }
    if full:
        base.update({
            "cover_letter": a.cover_letter,
            "cold_email_subject": a.cold_email_subject,
            "cold_email_body": a.cold_email_body,
            "resume_tweaks": a.resume_tweaks,
            "notes": a.notes,
        })
    return base
