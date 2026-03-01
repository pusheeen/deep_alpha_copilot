"""
Closed Loop — News Aggregator API

FastAPI backend that fetches, summarizes, and de-clickbaits news from
Google News, email newsletters, Chrome bookmarks, and custom RSS feeds.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.database import init_db
from .core.cache import news_cache, summary_cache
from .routers import auth, news, sources

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Closed Loop API...")
    await init_db()
    logger.info("Database initialized.")
    yield
    # Cleanup
    news_cache.clear()
    summary_cache.clear()
    logger.info("Shutting down Closed Loop API.")


app = FastAPI(
    title="Closed Loop — News Aggregator",
    description="AI-powered news aggregator with anti-clickbait summarization",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — allow frontend origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "https://*.vercel.app",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount routers
app.include_router(auth.router)
app.include_router(news.router)
app.include_router(sources.router)


@app.get("/api/health")
async def health():
    return {"status": "ok", "service": "closed-loop"}
