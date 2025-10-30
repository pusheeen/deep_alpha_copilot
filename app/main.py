# main.py

"""
Main FastAPI application file, adapted to use the Google ADK agent system.
"""
import asyncio
import csv
import logging
import json
import math
import os
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional, Any

import databases
import sqlalchemy
import stripe
from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# --- ADK Imports (Optional) ---
try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    print("Warning: Google ADK not available. Agent features will be disabled.")

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"], # Allows all methods
    allow_headers=["*"], # Allows all headers
)

# --- Import your new ADK root agent and utilities ---
from dotenv import load_dotenv  # <-- ADD THIS
if ADK_AVAILABLE:
    try:
        from app.agents.agents import root_agent, search_latest_news
    except ImportError:
        ADK_AVAILABLE = False
        print("Warning: Could not import agents. Agent features will be disabled.")
from app.scoring import compute_company_scores, ScoreComputationError
load_dotenv()

# Utility function to sanitize data for JSON serialization
def sanitize_for_json(obj):
    """Recursively replace NaN and infinity values with None for JSON compliance."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj

# --- Configuration ---
APP_DIR = Path(__file__).resolve().parent
# Stripe configuration
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
stripe.api_key = STRIPE_SECRET_KEY or None
DOMAIN = os.getenv("DOMAIN", "http://localhost:8000")
PRICE_ID = os.getenv("STRIPE_PRICE_ID")
# Flag whether Stripe is configured
HAS_STRIPE = bool(STRIPE_SECRET_KEY and PRICE_ID)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("hashed_password", sqlalchemy.String),
    sqlalchemy.Column("stripe_customer_id", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("stripe_subscription_id", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("subscription_status", sqlalchemy.String, nullable=True),
)

engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
metadata.create_all(engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

DATA_ROOT = Path(__file__).resolve().parents[1] / "data"
STRUCTURED_DIR = DATA_ROOT / "structured"
SECTOR_METRICS_DIR = STRUCTURED_DIR / "sector_metrics"
RUNTIME_DIR = DATA_ROOT / "runtime"
PRICE_SNAPSHOT_DIR = RUNTIME_DIR / "price_snapshots"
REALTIME_NEWS_DIR = RUNTIME_DIR / "news"
COMPANY_STATIC_DIR = DATA_ROOT / "company"
COMPANY_RUNTIME_DIR = RUNTIME_DIR / "company"

for directory in [RUNTIME_DIR, PRICE_SNAPSHOT_DIR, REALTIME_NEWS_DIR, COMPANY_STATIC_DIR, COMPANY_RUNTIME_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

SUPPORTED_TICKERS_CACHE: List[str] = []
SUPPORTED_TICKERS_CACHE_TIME: Optional[datetime] = None
SUPPORTED_TICKERS_TTL = timedelta(minutes=30)
REALTIME_NEWS_TTL = timedelta(minutes=30)
COMPANIES_FILE = DATA_ROOT / "companies.csv"
COMPANY_METADATA_CACHE: Dict[str, Dict[str, str]] = {}
COMPANY_METADATA_CACHE_TIME: Optional[datetime] = None
COMPANY_METADATA_TTL = timedelta(minutes=30)

sentiment_analyzer = SentimentIntensityAnalyzer()


def _latest_company_metrics_file() -> Optional[Path]:
    files = sorted(SECTOR_METRICS_DIR.glob("company_metrics_*.json"))
    return files[-1] if files else None


def load_supported_tickers() -> List[str]:
    global SUPPORTED_TICKERS_CACHE, SUPPORTED_TICKERS_CACHE_TIME
    now = datetime.now(timezone.utc)
    if (
        SUPPORTED_TICKERS_CACHE
        and SUPPORTED_TICKERS_CACHE_TIME
        and now - SUPPORTED_TICKERS_CACHE_TIME < SUPPORTED_TICKERS_TTL
    ):
        return SUPPORTED_TICKERS_CACHE

    try:
        from target_tickers import TARGET_TICKERS
        base_tickers = [ticker.upper() for ticker in TARGET_TICKERS]
    except Exception:
        base_tickers = []

    metrics_file = _latest_company_metrics_file()
    tickers: List[str] = base_tickers[:]
    if metrics_file and metrics_file.exists():
        try:
            with metrics_file.open("r") as fh:
                data = json.load(fh)
            metric_tickers = [entry["ticker"].upper() for entry in data if entry.get("ticker")]
            extras = [ticker for ticker in metric_tickers if ticker not in tickers]
            tickers.extend(extras)
        except Exception:
            pass

    if not tickers:
        tickers = base_tickers

    SUPPORTED_TICKERS_CACHE = tickers
    SUPPORTED_TICKERS_CACHE_TIME = now
    return tickers


def load_company_metadata() -> Dict[str, Dict[str, str]]:
    global COMPANY_METADATA_CACHE, COMPANY_METADATA_CACHE_TIME
    now = datetime.now(timezone.utc)
    if (
        COMPANY_METADATA_CACHE
        and COMPANY_METADATA_CACHE_TIME
        and now - COMPANY_METADATA_CACHE_TIME < COMPANY_METADATA_TTL
    ):
        return COMPANY_METADATA_CACHE

    tickers = load_supported_tickers()
    metadata: Dict[str, Dict[str, str]] = {
        ticker: {"name": ticker, "industry": "Unknown"} for ticker in tickers
    }

    metrics_file = _latest_company_metrics_file()
    metrics_lookup: Dict[str, Dict[str, Any]] = {}
    if metrics_file and metrics_file.exists():
        try:
            with metrics_file.open("r") as fh:
                metrics_data = json.load(fh)
            for entry in metrics_data:
                ticker = entry.get("ticker")
                if ticker and ticker in metadata:
                    metadata[ticker]["industry"] = entry.get("industry") or metadata[ticker]["industry"]
                    metrics_lookup[ticker] = entry
        except Exception:
            pass

    if COMPANIES_FILE.exists():
        try:
            with COMPANIES_FILE.open("r") as fh:
                reader = csv.DictReader(fh)
                for row in reader:
                    ticker = row.get("ticker")
                    name = row.get("company_name") or row.get("name")
                    if ticker and ticker in metadata and name:
                        metadata[ticker]["name"] = name
        except Exception:
            pass

    # Persist static company snapshot
    for ticker in metadata:
        static_payload = {
            "ticker": ticker,
            "name": metadata[ticker]["name"],
            "industry": metadata[ticker]["industry"],
            "sources": {
                "metrics_file": metrics_file.name if metrics_file else None,
                "companies_csv": str(COMPANIES_FILE.name) if COMPANIES_FILE.exists() else None,
            },
            "metrics": metrics_lookup.get(ticker),
            "updated_at": now.isoformat(),
        }
        static_path = COMPANY_STATIC_DIR / f"{ticker}.json"
        try:
            with static_path.open("w") as fh:
                json.dump(static_payload, fh, indent=2)
        except Exception as exc:
            logger.warning("Failed to write static profile for %s: %s", ticker, exc)

    COMPANY_METADATA_CACHE = metadata
    COMPANY_METADATA_CACHE_TIME = now
    return metadata


def _news_cache_path(ticker: str) -> Path:
    return REALTIME_NEWS_DIR / f"{ticker.upper()}_realtime_news.json"


def _load_cached_news(ticker: str) -> Optional[dict]:
    path = _news_cache_path(ticker)
    if not path.exists():
        return None
    try:
        with path.open("r") as fh:
            data = json.load(fh)
        fetched_at = datetime.fromisoformat(data.get("fetched_at"))
        if datetime.now(timezone.utc) - fetched_at.replace(tzinfo=timezone.utc) > REALTIME_NEWS_TTL:
            return None
        return data
    except Exception:
        return None


def _save_cached_news(ticker: str, payload: dict) -> None:
    try:
        path = _news_cache_path(ticker)
        with path.open("w") as fh:
            json.dump(payload, fh, indent=2)
        _update_company_runtime(ticker, "news", payload)
    except Exception:
        pass


def _compute_article_sentiment(title: str, snippet: str) -> Dict[str, Any]:
    text = " ".join(filter(None, [title, snippet]))
    sentiment = sentiment_analyzer.polarity_scores(text)
    score = sentiment["compound"]
    if score >= 0.25:
        label = "Positive"
    elif score <= -0.25:
        label = "Negative"
    else:
        label = "Neutral"
    return {"score": round(score, 3), "label": label}


def _update_company_runtime(ticker: str, section: str, payload: dict) -> None:
    ticker = ticker.upper()
    runtime_path = COMPANY_RUNTIME_DIR / f"{ticker}.json"
    try:
        if runtime_path.exists():
            with runtime_path.open("r") as fh:
                existing = json.load(fh)
        else:
            existing = {"ticker": ticker}
        existing.setdefault("runtime", {})
        existing["runtime"][section] = payload
        existing["updated_at"] = datetime.now(timezone.utc).isoformat()
        with runtime_path.open("w") as fh:
            json.dump(existing, fh, indent=2)
    except Exception as exc:
        logger.warning("Failed to update runtime cache for %s: %s", ticker, exc)


def _load_offline_news_summary(ticker: str) -> Optional[dict]:
    try:
        from fetch_data import get_latest_news_file
    except Exception:
        return None

    news_file = get_latest_news_file(ticker)
    if not news_file:
        return None

    try:
        with open(news_file, "r") as fh:
            news_data = json.load(fh)
    except Exception:
        return None

    articles = []
    seen_links = set()
    for article in news_data.get("articles", []):
        link = article.get("link") or article.get("url")
        title = article.get("title")
        if not title:
            continue
        key = link or title
        if key in seen_links:
            continue
        seen_links.add(key)
        sentiment_info = _compute_article_sentiment(title, article.get("summary", ""))
        articles.append(
            {
                "title": title,
                "source": article.get("publisher") or article.get("source"),
                "link": link,
                "published": article.get("publish_time"),
                "snippet": article.get("summary") or "",
                "sentiment": sentiment_info,
            }
        )

    if not articles:
        return None

    avg_score = sum(a["sentiment"]["score"] for a in articles) / len(articles)
    if avg_score >= 0.2:
        sentiment = "Positive"
        rating = "Buy"
    elif avg_score <= -0.2:
        sentiment = "Negative"
        rating = "Sell"
    else:
        sentiment = "Neutral"
        rating = "Hold"

    key_points = []
    for entry in sorted(articles, key=lambda x: abs(x["sentiment"]["score"]), reverse=True)[:3]:
        prefix = {"Positive": "✅", "Negative": "⚠️", "Neutral": "ℹ️"}.get(entry["sentiment"]["label"], "ℹ️")
        key_points.append(f"{prefix} {entry['title']}")

    return {
        "ticker": ticker.upper(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "headline": "Latest coverage snapshot",
            "sentiment": sentiment,
            "rating": rating,
            "confidence": "Low",
            "key_points": key_points,
            "rationale": "Derived from cached news files.",
            "conclusion": "Supplement with live data for the freshest read.",
        },
        "articles": articles,
    }
    _update_company_runtime(ticker, "news", payload)
    return payload


def fetch_realtime_news(ticker: str, window_hours: int = 72, max_results: int = 8) -> dict:
    if not ADK_AVAILABLE or "search_latest_news" not in globals():
        fallback = _load_offline_news_summary(ticker)
        if fallback:
            return fallback
        return {
            "ticker": ticker.upper(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "sentiment": "Neutral",
                "rating": "Hold",
                "confidence": "Low",
                "headline": "Live news service unavailable",
                "key_points": [],
                "rationale": "Real-time news search is disabled. Showing placeholder guidance.",
                "conclusion": "Enable Google Custom Search credentials to receive live coverage.",
            },
            "articles": [],
        }

    query = f"{ticker} stock"
    response = search_latest_news(query=query, max_results=max_results)
    if isinstance(response, dict) and response.get("error"):
        fallback = _load_offline_news_summary(ticker)
        if fallback:
            return fallback
        return {
            "ticker": ticker.upper(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "sentiment": "Neutral",
                "rating": "Hold",
                "confidence": "Low",
                "headline": "Unable to retrieve live headlines",
                "key_points": [],
                "rationale": response.get("error"),
                "conclusion": "Retry later or verify Google Custom Search credentials.",
            },
            "articles": [],
        }

    items = response.get("results", []) if isinstance(response, dict) else []

    seen_links = set()
    articles: List[dict] = []

    for item in items:
        link = item.get("link")
        if not link or link in seen_links:
            continue
        seen_links.add(link)

        title = (item.get("title") or "").strip()
        snippet = (item.get("snippet") or "").strip()
        published = item.get("published")
        try:
            published_dt = (
                datetime.fromisoformat(published.replace("Z", "+00:00")) if published else None
            )
        except Exception:
            published_dt = None

        sentiment_info = _compute_article_sentiment(title, snippet)

        articles.append(
            {
                "title": title,
                "source": item.get("source"),
                "link": link,
                "published": published_dt.isoformat() if published_dt else None,
                "snippet": snippet,
                "sentiment": sentiment_info,
            }
        )

    if window_hours and articles:
        cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours)
        filtered = [
            art
            for art in articles
            if not art["published"]
            or datetime.fromisoformat(art["published"]).replace(tzinfo=timezone.utc) >= cutoff
        ]
        if filtered:
            articles = filtered

    articles = articles[:max_results]

    if not articles:
        fallback = _load_offline_news_summary(ticker)
        if fallback:
            return fallback
        return {
            "ticker": ticker.upper(),
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "sentiment": "Neutral",
                "rating": "Hold",
                "confidence": "Low",
                "headline": "No recent coverage available",
                "key_points": [],
                "rationale": "We could not locate reliable coverage within the selected lookback window.",
                "conclusion": "Monitor upcoming catalysts before taking action.",
            },
            "articles": [],
        }

    avg_score = sum(art["sentiment"]["score"] for art in articles) / len(articles)
    if avg_score >= 0.2:
        overall_sentiment = "Positive"
        rating = "Buy"
    elif avg_score <= -0.2:
        overall_sentiment = "Negative"
        rating = "Sell"
    else:
        overall_sentiment = "Neutral"
        rating = "Hold"

    sorted_articles = sorted(articles, key=lambda x: abs(x["sentiment"]["score"]), reverse=True)
    icon_by_label = {"Positive": "✅", "Negative": "⚠️", "Neutral": "ℹ️"}
    key_points = [
        f"{icon_by_label.get(art['sentiment']['label'], 'ℹ️')} {art['title']}"
        for art in sorted_articles[:3]
    ]

    positive = [a for a in articles if a["sentiment"]["label"] == "Positive"]
    negative = [a for a in articles if a["sentiment"]["label"] == "Negative"]
    rationale_parts = []
    if positive:
        rationale_parts.append(f"{len(positive)} source(s) highlight supportive catalysts.")
    if negative:
        rationale_parts.append(f"{len(negative)} source(s) flag emerging risks.")
    if not rationale_parts:
        rationale_parts.append("Coverage is balanced without a dominant directional signal.")

    payload = {
        "ticker": ticker.upper(),
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "sentiment": overall_sentiment,
            "rating": rating,
            "confidence": "Medium" if len(articles) >= 3 else "Low",
            "headline": f"Latest coverage skews {overall_sentiment.lower()}",
            "key_points": key_points,
            "rationale": " ".join(rationale_parts),
            "conclusion": (
                "Momentum favors accumulation on strength."
                if rating == "Buy"
                else "Maintain exposure and reassess frequently."
                if rating == "Hold"
                else "Consider trimming positions or tightening stops."
            ),
        },
        "articles": articles,
    }
    return payload

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

async def get_user_by_email(email: str):
    query = users.select().where(users.c.email == email)
    return await database.fetch_one(query)

async def get_user_by_id(user_id: int):
    query = users.select().where(users.c.id == user_id)
    return await database.fetch_one(query)

async def authenticate_user(email: str, password: str):
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

async def get_current_user(request: Request):
    user_id = request.session.get("user")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- ADK Agent Runner Setup ---
if ADK_AVAILABLE:
    class AgentCaller:
        """A simple wrapper class for interacting with an ADK agent."""
        def __init__(self, agent: Agent, runner: Runner, user_id: str, session_id: str):
            self.agent = agent
            self.runner = runner
            self.user_id = user_id
            self.session_id = session_id

        async def call(self, user_message: str, include_reasoning: bool = False) -> dict:
            content = types.Content(role='user', parts=[types.Part(text=user_message)])

            final_response = {
                'answer': "Agent did not produce a final response.",
                'status': 'error'
            }

            reasoning_steps = []
            tools_used = set()

            async for event in self.runner.run_async(user_id=self.user_id, session_id=self.session_id, new_message=content):
                if include_reasoning and event.author != self.agent.name and not event.is_final_response():
                     # Capture tool calls and observations as reasoning steps
                     if event.content and event.content.parts and hasattr(event.content.parts[0], 'tool_code'):
                         tool_call = event.content.parts[0].tool_code
                         reasoning_steps.append({
                             'tool': tool_call.name,
                             'input': str(tool_call.args),
                             'output': "Pending..."
                         })
                         tools_used.add(tool_call.name)
                     elif event.content and event.content.parts and hasattr(event.content.parts[0], 'tool_result'):
                         if reasoning_steps:
                            reasoning_steps[-1]['output'] = str(event.content.parts[0].tool_result.result)

                if event.is_final_response() and event.content and event.content.parts:
                    final_response['answer'] = event.content.parts[0].text
                    final_response['status'] = 'success'
                    break

            if include_reasoning:
                final_response['reasoning_steps'] = reasoning_steps
                final_response['tools_used'] = list(tools_used)

            return final_response

    async def make_agent_caller(agent: Agent) -> AgentCaller:
        """Factory function to create an AgentCaller instance."""
        app_name = agent.name + "_app"
        user_id = agent.name + "_user"
        session_id = agent.name + "_session_01"

        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
        return AgentCaller(agent, runner, user_id, session_id)


# --- FastAPI Application ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup, initialize the ADK AgentCaller (if available)
    if ADK_AVAILABLE:
        print("Initializing ADK Agent...")
        app.state.agent_caller = await make_agent_caller(root_agent)
        print("Agent is ready.")
    else:
        print("ADK not available. Agent features disabled.")
        app.state.agent_caller = None
    yield
    # On shutdown (not essential for this example, but good practice)
    print("Shutting down.")


app = FastAPI(
    title="Clinical Assistant API (ADK Version)",
    description="An API for interacting with the Clinical AI Assistant, powered by Google ADK.",
    version="2.0.0",
    lifespan=lifespan
)

# Add session middleware and template rendering
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "changeme"))
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

class QueryRequest(BaseModel):
    """Defines the structure of the request body for the /chat endpoint."""
    question: str
    include_reasoning: bool = False

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serves the main index.html file."""
    user = None
    user_id = request.session.get("user")
    if user_id:
        user = await get_user_by_id(user_id)
    supported_tickers = load_supported_tickers()
    company_metadata = load_company_metadata()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user,
            "supported_tickers": supported_tickers,
            "supported_tickers_json": json.dumps(supported_tickers),
            "company_metadata_json": json.dumps(company_metadata),
        },
    )


@app.get("/api/scores/{ticker}")
async def get_scores(ticker: str, news_only: bool = False, query: Optional[str] = None):
    """Return the latest computed scorecard for a company or fetch news snippets for a query."""
    loop = asyncio.get_event_loop()
    if news_only:
        try:
            search_query = query or ticker
            data = await loop.run_in_executor(None, search_latest_news, search_query)
            results = data.get("results", []) if isinstance(data, dict) else []
            return {"status": "success", "data": {"latest_news": results}}
        except Exception as exc:  # pragma: no cover - network failures
            return {"status": "error", "message": f"Failed to fetch news: {exc}"}
    try:
        data = await loop.run_in_executor(None, compute_company_scores, ticker.upper())
        # Sanitize data to handle NaN/infinity values
        data = sanitize_for_json(data)
        return {"status": "success", "data": data}
    except ScoreComputationError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - unexpected errors bubbled to client
        return {"status": "error", "message": f"Unexpected error: {exc}"}

@app.get("/api/price-history/{ticker}")
async def get_price_history(ticker: str, period: str = "1m"):
    """Return price history with events for a specific time period."""
    from app.scoring.engine import get_price_history_with_events

    try:
        # For now, we'll use empty news items since we're focusing on significant moves
        news_items = []
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, get_price_history_with_events, ticker.upper(), news_items, period)
        data = sanitize_for_json(data)
        return {"status": "success", "data": data}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch price history: {exc}"}

@app.get("/api/valuation-metrics/{ticker}")
async def get_valuation_metrics(ticker: str):
    """Return historical P/E and P/S ratios with industry benchmarks."""
    from app.scoring.engine import get_valuation_metrics

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, get_valuation_metrics, ticker.upper())
        data = sanitize_for_json(data)
        return {"status": "success", "data": data}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch valuation metrics: {exc}"}

@app.get("/api/market-conditions")
async def get_market_conditions():
    """Return current market condition indicators."""
    from app.scoring.engine import get_market_conditions

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, get_market_conditions)
        return {"status": "success", "data": data}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch market conditions: {exc}"}

@app.get("/api/latest-news/{ticker}")
async def get_latest_news(ticker: str):
    """Return the latest news and interpretation for a ticker."""
    try:
        ticker = ticker.upper()

        payload = _load_cached_news(ticker)
        if not payload:
            payload = fetch_realtime_news(ticker)
            _save_cached_news(ticker, payload)

        # Attach legacy interpretation for deeper dive if available
        interpretation_summary = None
        interpretation_dir = DATA_ROOT / "unstructured" / "news_interpretation"
        interpretation_files = sorted(
            [
                file_path
                for file_path in interpretation_dir.glob(f"{ticker}_news_interpretation_*.json")
            ]
        )
        if interpretation_files:
            try:
                with interpretation_files[-1].open("r") as fh:
                    interpretation_summary = json.load(fh).get("analysis")
            except Exception:
                interpretation_summary = None

        payload["legacy_analysis"] = interpretation_summary

        return {"status": "success", "data": payload}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch latest news: {exc}"}

@app.post("/chat")
async def chat(request: QueryRequest, http_request: Request):
    """
    Receives a question, processes it through the ADK agent, and returns the response.
    """
    # Basic validation
    if not request.question or len(request.question.strip()) < 5:
        return {
            'answer': "Invalid query: Question seems too short to be meaningful",
            'status': 'validation_error'
        }

    # Access the agent_caller initialized at startup
    agent_caller = http_request.app.state.agent_caller

    if not agent_caller:
        return {
            'answer': "Agent features are not available. Please contact support.",
            'status': 'agent_unavailable'
        }

    # Process the query using the ADK agent
    response = await agent_caller.call(
        user_message=request.question,
        include_reasoning=request.include_reasoning
    )
    return response
  
# User authentication and subscription routes

# Register
@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    # Simple registration form
    html_content = """
<html><body>
<h2>Register</h2>
<form method='post'>
  Username: <input name='username'/><br/>
  Email: <input type='email' name='email'/><br/>
  Password: <input type='password' name='password'/><br/>
  <button type='submit'>Register</button>
</form>
</body></html>
"""
    return HTMLResponse(html_content)

@app.post("/register")
async def register_post(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    existing_user = await get_user_by_email(email)
    if existing_user:
        return HTMLResponse("Email already registered", status_code=400)
    hashed_password = get_password_hash(password)
    await database.execute(users.insert().values(username=username, email=email, hashed_password=hashed_password))
    return RedirectResponse(url="/login", status_code=302)

# Login
@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    # Simple login form
    html_content = """
<html><body>
<h2>Login</h2>
<form method='post'>
  Email: <input type='email' name='email'/><br/>
  Password: <input type='password' name='password'/><br/>
  <button type='submit'>Login</button>
</form>
</body></html>
"""
    return HTMLResponse(html_content)

@app.post("/login")
async def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    user = await authenticate_user(email, password)
    if not user:
        return HTMLResponse("Invalid credentials", status_code=401)
    request.session["user"] = user["id"]
    return RedirectResponse(url="/account", status_code=302)

# Logout
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)

# Account page
@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, current_user=Depends(get_current_user)):
    # Display account and subscription status
    subscribed = current_user.get("subscription_status") == "active"
    html = "<html><body>"
    html += f"<h2>Account for {current_user.get('username')}</h2>"
    html += f"<p>Email: {current_user.get('email')}</p>"
    html += "<h3>Subscription</h3>"
    if subscribed:
        html += "<p>Subscribed: $10/month (Active)</p>"
    else:
        if HAS_STRIPE:
            html += "<p>Monthly subscription: $10</p>"
            html += "<form method='post' action='/create-checkout-session'><button type='submit'>Subscribe</button></form>"
        else:
            html += "<p>Subscription feature is not yet configured.</p>"
    html += "<p><a href='/logout'>Logout</a> | <a href='/'>Home</a></p>"
    html += "</body></html>"
    return HTMLResponse(html)

# Create Stripe checkout session
@app.post("/create-checkout-session")
async def create_checkout_session(request: Request, current_user=Depends(get_current_user)):
    # Ensure Stripe integration is available
    if not HAS_STRIPE:
        raise HTTPException(status_code=503, detail="Stripe subscription is not configured")
    user = await get_user_by_id(current_user["id"])
    # Create Stripe customer if not exists
    if not user["stripe_customer_id"]:
        customer = stripe.Customer.create(email=user["email"])
        update_query = users.update().where(users.c.id == user["id"]).values(stripe_customer_id=customer["id"])
        await database.execute(update_query)
        stripe_customer_id = customer["id"]
    else:
        stripe_customer_id = user["stripe_customer_id"]
    try:
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=DOMAIN + "/subscription_success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=DOMAIN + "/account",
        )
        return RedirectResponse(session.url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Subscription success
@app.get("/subscription_success", response_class=HTMLResponse)
async def subscription_success(request: Request, session_id: str, current_user=Depends(get_current_user)):
    # Ensure Stripe integration is available
    if not HAS_STRIPE:
        raise HTTPException(status_code=503, detail="Stripe subscription is not configured")
    stripe_session = stripe.checkout.Session.retrieve(session_id)
    subscription_id = stripe_session.get("subscription")
    # Update subscription status
    await database.execute(users.update().where(users.c.id == current_user["id"]).values(
        stripe_subscription_id=subscription_id,
        subscription_status="active"
    ))
    html = "<html><body>"
    html += f"<h2>Subscription Successful!</h2><p>Thank you, {current_user.get('username')}.</p>"
    html += "<p>Your subscription is active. $10/month.</p>"
    html += "<p><a href='/account'>Go to Account</a> | <a href='/'>Home</a></p>"
    html += "</body></html>"
    return HTMLResponse(html)
