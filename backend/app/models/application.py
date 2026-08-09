from __future__ import annotations
from sqlalchemy import String, Text, DateTime, JSON, Integer, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from typing import Optional
import enum
from app.database import Base


class ApplicationStatus(str, enum.Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    SENT = "sent"
    ACKNOWLEDGED = "acknowledged"
    INTERVIEWING = "interviewing"
    REJECTED = "rejected"
    GHOSTED = "ghosted"
    OFFER = "offer"


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    job_id: Mapped[int] = mapped_column(ForeignKey("jobs.id"), index=True)

    status: Mapped[ApplicationStatus] = mapped_column(
        Enum(ApplicationStatus), default=ApplicationStatus.DRAFT, index=True
    )

    cover_letter: Mapped[Optional[str]] = mapped_column(Text)
    cold_email_subject: Mapped[Optional[str]] = mapped_column(String(300))
    cold_email_body: Mapped[Optional[str]] = mapped_column(Text)
    resume_tweaks: Mapped[Optional[list]] = mapped_column(JSON)

    sent_via: Mapped[Optional[str]] = mapped_column(String(50))
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    confirmation_id: Mapped[Optional[str]] = mapped_column(String(200))

    last_reply_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    notes: Mapped[Optional[str]] = mapped_column(Text)

    generation_model: Mapped[Optional[str]] = mapped_column(String(100))
    generation_prompt_tokens: Mapped[Optional[int]] = mapped_column(Integer)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    job: Mapped[Job] = relationship("Job", back_populates="applications")
