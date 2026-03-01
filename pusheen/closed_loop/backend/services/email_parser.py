"""
Email newsletter parser — extracts news content from email subscriptions.

Supports two modes:
1. Manual paste: user pastes email content via API
2. Gmail API: connects to Gmail via OAuth to pull newsletter emails
"""
import logging
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_email_html(html_content: str, sender: str = "", subject: str = "") -> list[dict]:
    """Extract news items from an HTML email newsletter."""
    soup = BeautifulSoup(html_content, "html.parser")

    # Remove styles and scripts
    for tag in soup(["script", "style"]):
        tag.decompose()

    articles: list[dict] = []

    # Strategy 1: find links with surrounding text
    for link in soup.find_all("a", href=True):
        href = link["href"]
        # Skip unsubscribe, social, tracking links
        if any(skip in href.lower() for skip in [
            "unsubscribe", "mailto:", "facebook.com", "twitter.com",
            "linkedin.com", "instagram.com", "#", "javascript:",
        ]):
            continue

        title = link.get_text(strip=True)
        if len(title) < 10:
            continue

        # Try to get surrounding context
        parent = link.find_parent(["td", "div", "li", "p"])
        snippet = parent.get_text(strip=True) if parent else title

        articles.append({
            "source_type": "email",
            "original_title": title,
            "original_url": href,
            "content_snippet": snippet[:500],
            "author": sender,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "category": f"Email: {subject}" if subject else "Email Newsletter",
        })

    # Deduplicate by URL
    seen: set[str] = set()
    deduped: list[dict] = []
    for a in articles:
        if a["original_url"] not in seen:
            seen.add(a["original_url"])
            deduped.append(a)

    return deduped


def parse_email_text(text_content: str, sender: str = "", subject: str = "") -> list[dict]:
    """Extract news items from plain-text email newsletters."""
    articles: list[dict] = []
    url_pattern = re.compile(r'https?://[^\s<>"]+')

    lines = text_content.split("\n")
    for i, line in enumerate(lines):
        urls = url_pattern.findall(line)
        for url in urls:
            # Skip common non-article URLs
            if any(skip in url.lower() for skip in ["unsubscribe", "mailto:", "facebook", "twitter"]):
                continue

            # Use surrounding lines as context
            start = max(0, i - 2)
            end = min(len(lines), i + 3)
            context = " ".join(lines[start:end]).strip()

            # Try to extract a title from the line or previous line
            title = line.strip()
            if len(title) < 10 and i > 0:
                title = lines[i - 1].strip()

            articles.append({
                "source_type": "email",
                "original_title": title[:200] if title else subject,
                "original_url": url,
                "content_snippet": context[:500],
                "author": sender,
                "published_at": datetime.now(timezone.utc).isoformat(),
                "category": f"Email: {subject}" if subject else "Email Newsletter",
            })

    return articles
