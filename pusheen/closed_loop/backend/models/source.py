from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship

from ..core.database import Base


class UserSource(Base):
    """Tracks user's configured news sources (RSS feeds, email accounts, etc.)."""
    __tablename__ = "user_sources"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    source_type = Column(String, nullable=False)  # "google_news", "rss", "email", "bookmark"
    name = Column(String, nullable=False)
    config = Column(JSON, default=dict)  # source-specific config (topics, feed URLs, etc.)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="sources")
