from fastapi import APIRouter, Depends, HTTPException, Header, UploadFile, File
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..core.database import get_db
from ..core.security import decode_access_token
from ..models.source import UserSource
from ..models.article import Bookmark
from ..services.email_parser import parse_email_html, parse_email_text
from ..services.bookmark_parser import parse_chrome_bookmarks_html, bookmarks_to_articles
from ..services.summarizer import batch_summarize
from ..services.news_fetcher import extract_article_content

router = APIRouter(prefix="/api/sources", tags=["sources"])


def _get_user_id(authorization: str = Header(default="")) -> int:
    token = authorization.replace("Bearer ", "") if authorization.startswith("Bearer ") else authorization
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    return int(payload["sub"])


# ── Source management ──────────────────────────────────────────────────────

class AddSourceRequest(BaseModel):
    source_type: str  # google_news, rss, email
    name: str
    config: dict = {}


@router.post("/add")
async def add_source(
    req: AddSourceRequest,
    user_id: int = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    source = UserSource(
        user_id=user_id,
        source_type=req.source_type,
        name=req.name,
        config=req.config,
    )
    db.add(source)
    await db.commit()
    await db.refresh(source)
    return {"id": source.id, "source_type": source.source_type, "name": source.name}


@router.get("/list")
async def list_sources(
    user_id: int = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSource).where(UserSource.user_id == user_id)
    )
    sources = result.scalars().all()
    return [
        {"id": s.id, "source_type": s.source_type, "name": s.name, "config": s.config}
        for s in sources
    ]


@router.delete("/{source_id}")
async def delete_source(
    source_id: int,
    user_id: int = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(UserSource).where(UserSource.id == source_id, UserSource.user_id == user_id)
    )
    source = result.scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=404, detail="Source not found")
    await db.delete(source)
    await db.commit()
    return {"deleted": True}


# ── Email newsletter import ───────────────────────────────────────────────

class EmailImportRequest(BaseModel):
    content: str
    content_type: str = "html"  # html or text
    sender: str = ""
    subject: str = ""
    summarize: bool = True


@router.post("/email/import")
async def import_email(
    req: EmailImportRequest,
    user_id: int = Depends(_get_user_id),
):
    if req.content_type == "html":
        articles = parse_email_html(req.content, req.sender, req.subject)
    else:
        articles = parse_email_text(req.content, req.sender, req.subject)

    if req.summarize and articles:
        articles = await batch_summarize(articles[:20])

    return {"articles": articles, "total": len(articles)}


# ── Chrome bookmarks import ───────────────────────────────────────────────

@router.post("/bookmarks/import")
async def import_bookmarks(
    file: UploadFile = File(...),
    user_id: int = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    content = await file.read()
    html_content = content.decode("utf-8", errors="ignore")
    bookmarks = parse_chrome_bookmarks_html(html_content)

    # Save bookmarks to DB
    for bm in bookmarks:
        db_bookmark = Bookmark(
            user_id=user_id,
            url=bm["url"],
            title=bm.get("title"),
            folder=bm.get("folder"),
        )
        db.add(db_bookmark)
    await db.commit()

    # Convert to articles for news feed
    articles = bookmarks_to_articles(bookmarks[:30])

    return {
        "bookmarks_imported": len(bookmarks),
        "articles": articles,
    }


@router.post("/bookmarks/summarize")
async def summarize_bookmarks(
    user_id: int = Depends(_get_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Fetch and summarize content from user's saved bookmarks."""
    result = await db.execute(
        select(Bookmark).where(Bookmark.user_id == user_id).limit(20)
    )
    bookmarks = result.scalars().all()
    articles = [
        {
            "source_type": "bookmark",
            "original_title": bm.title or bm.url,
            "original_url": bm.url,
            "content_snippet": "",
            "category": f"Bookmark: {bm.folder}" if bm.folder else "Bookmarks",
        }
        for bm in bookmarks
    ]

    if articles:
        articles = await batch_summarize(articles)

    return {"articles": articles, "total": len(articles)}
