"""
AI-powered summarization & anti-clickbait title generation.

Uses OpenAI-compatible API (works with OpenAI, OpenRouter, local models).
All results are cached so repeat views are instant.
"""
import json
import logging

from openai import AsyncOpenAI

from ..core.cache import summary_cache
from ..core.config import settings

logger = logging.getLogger(__name__)

_openai_client: AsyncOpenAI | None = None


def _get_openai() -> AsyncOpenAI:
    global _openai_client
    if _openai_client is None:
        _openai_client = AsyncOpenAI(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
        )
    return _openai_client


SYSTEM_PROMPT = """You are a news analyst. Given an article's original title and content, produce:

1. **generated_title** — A concise, accurate, non-clickbait title that faithfully represents the article's actual content. Remove sensationalism, vague teasers, and emotional manipulation. Keep it informative.
2. **summary** — A TL;DR of 2-3 sentences capturing the key facts. No fluff.
3. **clickbait_score** — A float from 0.0 (not clickbait) to 1.0 (extreme clickbait) rating how clickbaity the ORIGINAL title is.
4. **is_clickbait** — Boolean, true if clickbait_score >= 0.6.

Respond ONLY with valid JSON matching this schema:
{
  "generated_title": "string",
  "summary": "string",
  "clickbait_score": 0.0,
  "is_clickbait": false
}"""


async def summarize_article(original_title: str, content: str, url: str) -> dict:
    """Generate summary, anti-clickbait title, and clickbait score."""
    cache_params = {"url": url}
    cached = summary_cache.get("summary", cache_params)
    if cached is not None:
        return cached

    if not settings.OPENAI_API_KEY:
        # Fallback when no API key configured
        result = {
            "generated_title": original_title,
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "clickbait_score": 0.0,
            "is_clickbait": False,
        }
        summary_cache.set("summary", result, cache_params)
        return result

    client = _get_openai()
    user_msg = f"Original title: {original_title}\n\nArticle content:\n{content[:3000]}"

    try:
        resp = await client.chat.completions.create(
            model=settings.SUMMARIZATION_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            temperature=0.3,
            max_tokens=500,
        )
        raw = resp.choices[0].message.content.strip()
        # Parse JSON from response (handle markdown code blocks)
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
        result = json.loads(raw)
        summary_cache.set("summary", result, cache_params)
        return result
    except Exception as e:
        logger.error(f"Summarization failed for '{url}': {e}")
        return {
            "generated_title": original_title,
            "summary": content[:200] + "..." if len(content) > 200 else content,
            "clickbait_score": 0.0,
            "is_clickbait": False,
        }


async def batch_summarize(articles: list[dict]) -> list[dict]:
    """Enrich a list of article dicts with summaries and generated titles."""
    import asyncio

    async def _process(article: dict) -> dict:
        content = article.get("content_snippet", "")
        if not content or len(content) < 50:
            # Try to fetch content from URL
            from .news_fetcher import extract_article_content
            content = await extract_article_content(article["original_url"])
            article["content_snippet"] = content

        result = await summarize_article(
            article["original_title"],
            content,
            article["original_url"],
        )
        article["generated_title"] = result.get("generated_title", article["original_title"])
        article["summary"] = result.get("summary", "")
        article["clickbait_score"] = result.get("clickbait_score", 0.0)
        article["is_clickbait"] = result.get("is_clickbait", False)
        return article

    # Process in batches of 5 to avoid rate limits
    batch_size = 5
    enriched = []
    for i in range(0, len(articles), batch_size):
        batch = articles[i : i + batch_size]
        results = await asyncio.gather(*[_process(a) for a in batch])
        enriched.extend(results)

    return enriched
