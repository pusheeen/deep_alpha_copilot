"""
Chrome bookmarks parser — imports and processes user's Chrome bookmarks.

Users upload their Chrome bookmarks HTML export file, and we extract
articles from their bookmarked pages.
"""
import logging
from datetime import datetime, timezone

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


def parse_chrome_bookmarks_html(html_content: str) -> list[dict]:
    """Parse Chrome's exported bookmarks HTML file and extract URLs."""
    soup = BeautifulSoup(html_content, "html.parser")
    bookmarks: list[dict] = []

    for link in soup.find_all("a"):
        url = link.get("href", "")
        if not url.startswith(("http://", "https://")):
            continue

        title = link.get_text(strip=True)
        add_date = link.get("add_date")
        added_at = None
        if add_date:
            try:
                added_at = datetime.fromtimestamp(int(add_date), tz=timezone.utc)
            except (ValueError, OSError):
                pass

        # Find the parent folder
        folder = None
        parent_dl = link.find_parent("dl")
        if parent_dl:
            prev_h3 = parent_dl.find_previous_sibling("h3")
            if not prev_h3:
                # Try parent's previous sibling
                parent_dt = parent_dl.find_parent("dt")
                if parent_dt:
                    prev_h3 = parent_dt.find("h3")
            if prev_h3:
                folder = prev_h3.get_text(strip=True)

        bookmarks.append({
            "url": url,
            "title": title,
            "folder": folder,
            "added_at": added_at.isoformat() if added_at else None,
        })

    return bookmarks


def bookmarks_to_articles(bookmarks: list[dict]) -> list[dict]:
    """Convert parsed bookmarks into article format for processing."""
    articles: list[dict] = []
    for bm in bookmarks:
        articles.append({
            "source_type": "bookmark",
            "original_title": bm["title"] or bm["url"],
            "original_url": bm["url"],
            "content_snippet": "",  # will be fetched later
            "published_at": bm.get("added_at"),
            "category": f"Bookmark: {bm['folder']}" if bm.get("folder") else "Bookmarks",
        })
    return articles
