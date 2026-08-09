from __future__ import annotations
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/autointern"

    # Claude API
    ANTHROPIC_API_KEY: str

    # Gmail (SMTP + App Password — no OAuth needed)
    FROM_EMAIL: Optional[str] = None
    GMAIL_APP_PASSWORD: Optional[str] = None

    # Ollama (local, free)
    USE_OLLAMA: bool = False
    OLLAMA_MODEL: str = "llama3.1:8b"
    OLLAMA_FAST_MODEL: str = "llama3.1:8b"

    # YC Algolia
    YC_ALGOLIA_API_KEY: Optional[str] = None

    # Firecrawl (email enrichment)
    FIRECRAWL_API_KEY: Optional[str] = None

    # App
    APP_ENV: str = "development"
    LOG_LEVEL: str = "INFO"

    # Scraping — be polite
    SCRAPE_DELAY_MIN: float = 2.0
    SCRAPE_DELAY_MAX: float = 5.0
    MAX_CONCURRENT_SCRAPERS: int = 3

    # User profile path (JSON file)
    USER_PROFILE_PATH: str = "profile.json"

    class Config:
        env_file = ".env"


settings = Settings()
