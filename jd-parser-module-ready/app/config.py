"""Application configuration powered by Pydantic Settings."""

from typing import Optional

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Global configuration settings for the JD Analyser platform."""

    # Database: SQLite by default; overrides if DATABASE_URL is set in environment/.env
    DATABASE_URL: str = "sqlite+aiosqlite:///data/feedback.db"
    SYNC_DATABASE_URL: Optional[str] = None

    # RL Policy Version
    POLICY_VERSION: str = "gemini-bootstrap"

    # Primary LLM - Google Gemini
    GEMINI_API_KEY: Optional[str] = None
    GEMINI_MODEL: str = "gemini-2.5-flash-lite"

    # Fallback LLM - SambaNova Llama
    SAMBANOVA_API_KEY: Optional[str] = None
    SAMBANOVA_MODEL: str = "Meta-Llama-3.3-70B-Instruct"

    # Optional Fallbacks
    GROQ_API_KEY: Optional[str] = None
    GROQ_MODEL: str = "llama-3.3-70b-versatile"
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_MODEL: str = "meta-llama/llama-3.3-70b-instruct:free"

    # Optional API Security
    API_KEY_AUTH_ENABLED: bool = False
    APP_API_KEY: Optional[str] = None

    # Optional CORS and Documentation
    CORS_ORIGINS: str = ""
    ENABLE_DOCS: bool = False

    # Application Timezone: IANA timezone name (e.g. 'UTC', 'Asia/Kolkata', 'America/Los_Angeles')
    # Defaults to system local timezone if None, reproducing Node.js environment behavior
    APP_TIMEZONE: Optional[str] = None

    # Server Ports
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000
    STREAMLIT_PORT: int = 8501

    model_config = SettingsConfigDict(
        env_file=(".env", ".env.local"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def normalize_database_url(cls, v: str) -> str:
        """Normalize async driver prefixes for SQLite and MySQL."""
        if v.startswith("mysql://"):
            return v.replace("mysql://", "mysql+aiomysql://", 1)
        if v.startswith("sqlite:///") and not v.startswith("sqlite+aiosqlite:///"):
            return v.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
        return v

    def get_sync_database_url(self) -> str:
        """Derive synchronous database URL for Alembic or sync connections."""
        if self.SYNC_DATABASE_URL:
            return self.SYNC_DATABASE_URL
        if self.DATABASE_URL.startswith("sqlite+aiosqlite:///"):
            return self.DATABASE_URL.replace("sqlite+aiosqlite:///", "sqlite:///")
        if self.DATABASE_URL.startswith("mysql+aiomysql://"):
            return self.DATABASE_URL.replace("mysql+aiomysql://", "mysql+pymysql://")
        if self.DATABASE_URL.startswith("mysql://"):
            return self.DATABASE_URL.replace("mysql://", "mysql+pymysql://")
        return self.DATABASE_URL

    @property
    def is_sqlite(self) -> bool:
        return "sqlite" in self.DATABASE_URL

    @property
    def is_mysql(self) -> bool:
        return "mysql" in self.DATABASE_URL


settings = Settings()
