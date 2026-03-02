from datetime import datetime, timezone

from sqlalchemy import Column, Integer, String, DateTime, Text, Float, ForeignKey, Boolean
from sqlalchemy.orm import relationship

from ..core.database import Base


class Article(Base):
    """A fetched and processed news article."""
    __tablename__ = "articles"

    id = Column(Integer, primary_key=True, index=True)
    source_type = Column(String, nullable=False)  # google_news, email, bookmark, rss
    original_title = Column(String, nullable=False)
    generated_title = Column(String, nullable=True)  # anti-clickbait title
    original_url = Column(String, unique=True, index=True, nullable=False)
    summary = Column(Text, nullable=True)  # TL;DR
    content_snippet = Column(Text, nullable=True)  # first ~2000 chars of article
    image_url = Column(String, nullable=True)
    author = Column(String, nullable=True)
    published_at = Column(DateTime, nullable=True)
    fetched_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    clickbait_score = Column(Float, nullable=True)  # 0-1, higher = more clickbait
    is_clickbait = Column(Boolean, default=False)
    category = Column(String, nullable=True)


class Bookmark(Base):
    """User-saved bookmarks imported from Chrome."""
    __tablename__ = "bookmarks"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    url = Column(String, nullable=False)
    title = Column(String, nullable=True)
    folder = Column(String, nullable=True)
    added_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="bookmarks")
