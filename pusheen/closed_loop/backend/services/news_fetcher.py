"""
News fetcher service — pulls articles from Google News RSS, custom RSS feeds,
and user bookmarks.  Results are cached in-memory for fast repeated reads.
"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import feedparser
import httpx
from bs4 import BeautifulSoup

from ..core.cache import news_cache
from ..core.config import settings

logger = logging.getLogger(__name__)

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
DEFAULT_TOPICS = ["technology", "finance", "AI artificial intelligence", "world news"]

# Shared async client (connection pooling)
_client: httpx.AsyncClient | None = None


async def _get_client() -> httpx.AsyncClient:
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            follow_redirects=True,
            headers={"User-Agent": "Sift/1.0 NewsAggregator"},
        )
    return _client


def _is_fresh(published: datetime | None, max_hours: int | None = None) -> bool:
    if published is None:
        return True  # if unknown, include it
    hours = max_hours or settings.NEWS_FRESHNESS_HOURS
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    if published.tzinfo is None:
        published = published.replace(tzinfo=timezone.utc)
    return published >= cutoff


# ── Google News RSS ────────────────────────────────────────────────────────

async def fetch_google_news(topics: list[str] | None = None) -> list[dict]:
    topics = topics or DEFAULT_TOPICS
    cache_key = "google_news"
    cache_params = {"topics": sorted(topics)}
    cached = news_cache.get(cache_key, cache_params)
    if cached is not None:
        return cached

    articles: list[dict] = []

    async def _fetch_topic(topic: str):
        url = GOOGLE_NEWS_RSS.format(query=quote_plus(topic))
        client = await _get_client()
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            feed = feedparser.parse(resp.text)
            for entry in feed.entries:
                published = None
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    from time import mktime
                    published = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
                if not _is_fresh(published):
                    continue
                articles.append({
                    "source_type": "google_news",
                    "original_title": entry.get("title", ""),
                    "original_url": entry.get("link", ""),
                    "published_at": published.isoformat() if published else None,
                    "author": entry.get("author"),
                    "category": topic,
                    "content_snippet": entry.get("summary", ""),
                })
        except Exception as e:
            logger.warning(f"Failed to fetch Google News for topic '{topic}': {e}")

    await asyncio.gather(*[_fetch_topic(t) for t in topics])

    # Deduplicate by URL
    seen_urls: set[str] = set()
    deduped: list[dict] = []
    for a in articles:
        if a["original_url"] not in seen_urls:
            seen_urls.add(a["original_url"])
            deduped.append(a)

    news_cache.set(cache_key, deduped, cache_params)
    return deduped


# ── Custom RSS Feeds ───────────────────────────────────────────────────────

async def fetch_rss_feed(feed_url: str) -> list[dict]:
    cache_key = "rss"
    cache_params = {"url": feed_url}
    cached = news_cache.get(cache_key, cache_params)
    if cached is not None:
        return cached

    articles: list[dict] = []
    client = await _get_client()
    try:
        resp = await client.get(feed_url)
        resp.raise_for_status()
        feed = feedparser.parse(resp.text)
        for entry in feed.entries:
            published = None
            if hasattr(entry, "published_parsed") and entry.published_parsed:
                from time import mktime
                published = datetime.fromtimestamp(mktime(entry.published_parsed), tz=timezone.utc)
            if not _is_fresh(published):
                continue
            articles.append({
                "source_type": "rss",
                "original_title": entry.get("title", ""),
                "original_url": entry.get("link", ""),
                "published_at": published.isoformat() if published else None,
                "author": entry.get("author"),
                "content_snippet": entry.get("summary", ""),
            })
    except Exception as e:
        logger.warning(f"Failed to fetch RSS feed '{feed_url}': {e}")

    news_cache.set(cache_key, articles, cache_params)
    return articles


# ── Extract article text from URL ──────────────────────────────────────────

async def extract_article_content(url: str) -> str:
    """Fetch a URL and extract the main text content."""
    cache_key = "article_content"
    cache_params = {"url": url}
    cached = news_cache.get(cache_key, cache_params)
    if cached is not None:
        return cached

    client = await _get_client()
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Remove script/style elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Try common article selectors
        article = (
            soup.find("article")
            or soup.find("div", class_="article-body")
            or soup.find("div", class_="post-content")
            or soup.find("main")
        )
        text = (article or soup.body or soup).get_text(separator="\n", strip=True)

        # Trim to ~3000 chars for summarization
        text = text[:3000]
        news_cache.set(cache_key, text, cache_params, ttl=3600)
        return text
    except Exception as e:
        logger.warning(f"Failed to extract content from '{url}': {e}")
        return ""
