from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class UserProfile:
    name: str
    email: str
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None

    education: list = field(default_factory=list)
    experience: list = field(default_factory=list)
    projects: list = field(default_factory=list)
    skills: list = field(default_factory=list)

    target_roles: list = field(default_factory=list)
    target_industries: list = field(default_factory=list)
    preferred_locations: list = field(default_factory=list)
    open_to_remote: bool = True

    bio: str = ""
    tone_keywords: list = field(default_factory=list)
    resume_pdf_path: Optional[str] = None

    @classmethod
    def from_json(cls, data: dict) -> UserProfile:
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
