import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-key-change-me")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./closed_loop.db")

    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_BASE_URL: str = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    SUMMARIZATION_MODEL: str = os.getenv("SUMMARIZATION_MODEL", "gpt-4o-mini")

    GOOGLE_CLIENT_ID: str = os.getenv("GOOGLE_CLIENT_ID", "")
    GOOGLE_CLIENT_SECRET: str = os.getenv("GOOGLE_CLIENT_SECRET", "")

    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", "900"))
    NEWS_FRESHNESS_HOURS: int = int(os.getenv("NEWS_FRESHNESS_HOURS", "72"))


settings = Settings()
