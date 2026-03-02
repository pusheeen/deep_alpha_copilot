from fastapi import APIRouter, Depends, HTTPException, Header, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import decode_access_token
from ..services.news_fetcher import fetch_google_news, fetch_rss_feed, extract_article_content
from ..services.summarizer import batch_summarize, summarize_article

router = APIRouter(prefix="/api/news", tags=["news"])


def _get_user_id(authorization: str = Header(default="")) -> int:
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(payload["sub"])


class FeedRequest(BaseModel):
    topics: list[str] | None = None
    rss_feeds: list[str] | None = None
    summarize: bool = True
    limit: int = 30


@router.post("/feed")
async def get_news_feed(req: FeedRequest, user_id: int = Depends(_get_user_id)):
    """Fetch and return a combined, summarized news feed."""
    all_articles: list[dict] = []

    # Fetch Google News
    google_articles = await fetch_google_news(req.topics)
    all_articles.extend(google_articles)

    # Fetch custom RSS feeds
    if req.rss_feeds:
        for feed_url in req.rss_feeds:
            rss_articles = await fetch_rss_feed(feed_url)
            all_articles.extend(rss_articles)

    # Sort by published date (newest first)
    all_articles.sort(
        key=lambda a: a.get("published_at") or "1970-01-01",
        reverse=True,
    )

    # Limit
    all_articles = all_articles[: req.limit]

    # Summarize if requested
    if req.summarize and all_articles:
        all_articles = await batch_summarize(all_articles)

    return {
        "articles": all_articles,
        "total": len(all_articles),
    }


@router.get("/feed")
async def get_news_feed_default(
    user_id: int = Depends(_get_user_id),
    topics: str = Query(default="", description="Comma-separated topics"),
    limit: int = Query(default=20, ge=1, le=100),
    summarize: bool = Query(default=True),
):
    """GET endpoint for news feed with query params."""
    topic_list = [t.strip() for t in topics.split(",") if t.strip()] or None
    all_articles = await fetch_google_news(topic_list)

    all_articles.sort(
        key=lambda a: a.get("published_at") or "1970-01-01",
        reverse=True,
    )
    all_articles = all_articles[:limit]

    if summarize and all_articles:
        all_articles = await batch_summarize(all_articles)

    return {
        "articles": all_articles,
        "total": len(all_articles),
    }


@router.get("/article")
async def get_article_detail(
    url: str = Query(..., description="Article URL"),
    user_id: int = Depends(_get_user_id),
):
    """Fetch and summarize a single article by URL."""
    content = await extract_article_content(url)
    if not content:
        raise HTTPException(status_code=404, detail="Could not fetch article content")

    result = await summarize_article("", content, url)
    return {
        "url": url,
        "content_snippet": content[:1000],
        **result,
    }
