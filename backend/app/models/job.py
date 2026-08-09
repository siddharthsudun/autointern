from __future__ import annotations
from sqlalchemy import String, Text, Boolean, DateTime, JSON, Integer, Float, ForeignKey, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime, timezone
from typing import Optional
import enum
from app.database import Base


class JobType(str, enum.Enum):
    INTERNSHIP = "internship"
    FULL_TIME = "full_time"
    PART_TIME = "part_time"
    CONTRACT = "contract"


class JobFunction(str, enum.Enum):
    ENGINEERING = "engineering"
    PRODUCT = "product"
    MARKETING = "marketing"
    DESIGN = "design"
    OPERATIONS = "operations"
    SALES = "sales"
    DATA = "data"
    OTHER = "other"


class Job(Base):
    __tablename__ = "jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    company_id: Mapped[int] = mapped_column(ForeignKey("companies.id"), index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    job_type: Mapped[JobType] = mapped_column(Enum(JobType), default=JobType.INTERNSHIP)
    function: Mapped[JobFunction] = mapped_column(Enum(JobFunction), default=JobFunction.ENGINEERING)

    source_url: Mapped[Optional[str]] = mapped_column(String(1000))
    source: Mapped[Optional[str]] = mapped_column(String(100))
    apply_url: Mapped[Optional[str]] = mapped_column(String(1000))
    apply_method: Mapped[Optional[str]] = mapped_column(String(50))
    apply_email: Mapped[Optional[str]] = mapped_column(String(200))

    description_raw: Mapped[Optional[str]] = mapped_column(Text)
    requirements: Mapped[Optional[list]] = mapped_column(JSON)
    responsibilities: Mapped[Optional[list]] = mapped_column(JSON)
    location: Mapped[Optional[str]] = mapped_column(String(200))
    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    compensation: Mapped[Optional[str]] = mapped_column(String(200))

    match_score: Mapped[Optional[float]] = mapped_column(Float)
    match_reasoning: Mapped[Optional[str]] = mapped_column(Text)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    company: Mapped[Company] = relationship("Company", back_populates="jobs")
    applications: Mapped[list[Application]] = relationship(
        "Application", back_populates="job", cascade="all, delete-orphan"
    )
