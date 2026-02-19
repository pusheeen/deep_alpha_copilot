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
import re
import shutil
import ssl
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import databases
import sqlalchemy
import stripe
from fastapi import FastAPI, Request, Form, Depends, HTTPException, status, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordBearer
from fastapi.templating import Jinja2Templates
from jose import jwt, JWTError
from passlib.context import CryptContext
from pydantic import BaseModel
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import FileResponse
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from fetch_data import token_usage as token_usage_module
from fetch_data.token_usage import fetch_and_save_token_usage
from fetch_data.news_analysis import interpret_news_with_deep_alpha, save_news_interpretation
from fetch_data.utils import NEWS_INTERPRETATION_DIR

try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    GENAI_AVAILABLE = False

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

# --- Import your new ADK root agent and utilities ---
from dotenv import load_dotenv  # <-- ADD THIS
# Try to import search_latest_news separately as it doesn't depend on ADK core
try:
    from app.agents.agents import search_latest_news
    SEARCH_AVAILABLE = True
except ImportError:
    SEARCH_AVAILABLE = False
    print("Warning: Could not import search_latest_news.")

if ADK_AVAILABLE:
    try:
        from app.agents.agents import root_agent
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
# Use /tmp for SQLite in Cloud Run (read-only filesystem)
default_db_path = "sqlite:////tmp/users.db" if os.getenv("K_SERVICE") else "sqlite:///./users.db"
DATABASE_URL = os.getenv("DATABASE_URL", default_db_path)
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

# --- Authentication Helpers ---
SECRET_KEY = os.getenv("SECRET_KEY", "09d25e094faa6ca2556c818166b7a9563b93f7099f6f0f4caa6cf63b88e8d3e7")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    query = users.select().where(users.c.username == username)
    user = await database.fetch_one(query)
    if user is None:
        raise credentials_exception
    return user

DATA_ROOT = Path(os.getenv("DATA_ROOT", str(Path(__file__).resolve().parents[1] / "data")))
STRUCTURED_DIR = DATA_ROOT / "structured"
SECTOR_METRICS_DIR = STRUCTURED_DIR / "sector_metrics"
FLOW_DATA_DIR = STRUCTURED_DIR / "flow_data"
TOKEN_USAGE_DIR = DATA_ROOT / "unstructured" / "token_usage"
LEGACY_TOKEN_USAGE_DIR = Path(__file__).resolve().parents[1] / "data" / "unstructured" / "token_usage"
RUNTIME_DIR = DATA_ROOT / "runtime"
PRICE_SNAPSHOT_DIR = RUNTIME_DIR / "price_snapshots"
REALTIME_NEWS_DIR = RUNTIME_DIR / "news"
COMPANY_STATIC_DIR = DATA_ROOT / "company"
COMPANY_RUNTIME_DIR = RUNTIME_DIR / "company"

for directory in [RUNTIME_DIR, PRICE_SNAPSHOT_DIR, REALTIME_NEWS_DIR, COMPANY_STATIC_DIR, COMPANY_RUNTIME_DIR, FLOW_DATA_DIR, TOKEN_USAGE_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

logger = logging.getLogger(__name__)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
FLOW_SUMMARY_MODEL = os.getenv("FLOW_SUMMARY_MODEL", "gemini-1.5-flash")

if GENAI_AVAILABLE and GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as exc:  # pragma: no cover - configuration edge cases
        GENAI_AVAILABLE = False
        logger.warning("Gemini configuration failed: %s", exc)
else:
    GENAI_AVAILABLE = False

token_usage_module.TOKEN_USAGE_DIR = str(TOKEN_USAGE_DIR)
TOKEN_USAGE_LOCK = asyncio.Lock()

SUPPORTED_TICKERS_CACHE: List[str] = []
SUPPORTED_TICKERS_CACHE_TIME: Optional[datetime] = None
SUPPORTED_TICKERS_TTL = timedelta(minutes=30)
REALTIME_NEWS_TTL = timedelta(hours=12)  # Refresh news every 12 hours
COMPANIES_FILE = DATA_ROOT / "companies.csv"
COMPANY_METADATA_CACHE: Dict[str, Dict[str, str]] = {}
COMPANY_METADATA_CACHE_TIME: Optional[datetime] = None
COMPANY_METADATA_TTL = timedelta(minutes=30)

sentiment_analyzer = SentimentIntensityAnalyzer()
ARTICLE_HTML_SNIFF_BYTES = 65536
ARTICLE_TIMESTAMP_CACHE: Dict[str, Optional[str]] = {}
META_TIMESTAMP_PATTERNS = [
    re.compile(r'property=["\']article:published_time["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'property=["\']og:updated_time["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'name=["\']pubdate["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE),
    re.compile(r'name=["\']date["\']\s+content=["\']([^"\']+)["\']', re.IGNORECASE),
]
JSONLD_TIMESTAMP_PATTERNS = [
    re.compile(r'"datePublished"\s*:\s*"([^"]+)"'),
    re.compile(r'"dateCreated"\s*:\s*"([^"]+)"'),
    re.compile(r'"dateModified"\s*:\s*"([^"]+)"'),
]
SSL_CONTEXT = ssl.create_default_context()

# --- Deep Alpha heuristics for contextual data and watchlist ---
AI_LAYER_SECTOR_DEFAULTS: Dict[str, str] = {
    "technology": "Compute",
    "communication services": "Interconnect",
    "industrials": "Interconnect",
    "energy": "Energy",
    "utilities": "Energy",
    "materials": "Materials",
    "basic materials": "Materials",
    "consumer defensive": "Services",
    "consumer cyclical": "Services",
    "healthcare": "Healthcare",
    "financial services": "Services",
}

AI_LAYER_INDUSTRY_KEYWORDS: Dict[str, str] = {
    "semiconductor": "Compute",
    "chip": "Compute",
    "cloud": "Compute",
    "software": "Compute",
    "hardware": "Compute",
    "ai": "Compute",
    "network": "Interconnect",
    "communication": "Interconnect",
    "telecom": "Interconnect",
    "defense": "Energy",
    "battery": "Energy",
    "solar": "Energy",
    "wind": "Energy",
    "uranium": "Materials",
    "lithium": "Materials",
    "mining": "Materials",
    "chemical": "Materials",
    "insurance": "Services",
    "bank": "Services",
    "retail": "Services",
    "logistics": "Interconnect",
}

WATCHLIST_LIMIT = int(os.getenv("DEEP_ALPHA_WATCHLIST_LIMIT", "4"))


def _latest_company_metrics_file() -> Optional[Path]:
    files = sorted(SECTOR_METRICS_DIR.glob("company_metrics_*.json"))
    return files[-1] if files else None


def _latest_sector_metrics_file() -> Optional[Path]:
    files = sorted(SECTOR_METRICS_DIR.glob("sector_metrics_*.json"))
    return files[-1] if files else None


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _infer_ai_layer(sector: Optional[str], industry: Optional[str]) -> str:
    sector_key = (sector or "").strip().lower()
    industry_key = (industry or "").strip().lower()

    if not sector_key and not industry_key:
        return "N/A"

    for keyword, layer in AI_LAYER_INDUSTRY_KEYWORDS.items():
        if keyword in industry_key:
            return layer

    inferred = AI_LAYER_SECTOR_DEFAULTS.get(sector_key)
    if inferred:
        return inferred

    for keyword, layer in AI_LAYER_INDUSTRY_KEYWORDS.items():
        if keyword in sector_key:
            return layer

    return "N/A"


def _infer_conviction_quadrant(metrics: Optional[Dict[str, Any]]) -> str:
    if not isinstance(metrics, dict) or not metrics:
        return "Balanced Execution"

    momentum_6m = _safe_float(metrics.get("momentum_6m"))
    volatility = _safe_float(metrics.get("volatility"))
    debt_to_equity = _safe_float(metrics.get("debt_to_equity"))
    cagr = _safe_float(metrics.get("cagr"))

    if momentum_6m is not None and volatility is not None:
        if momentum_6m >= 40 and volatility >= 45:
            return "High-Growth Challenger"
        if momentum_6m >= 10 and volatility < 45 and (debt_to_equity is None or debt_to_equity < 120):
            return "Strategic Compounder"
        if momentum_6m <= -5 and debt_to_equity and debt_to_equity > 200:
            return "Turnaround Risk"

    if cagr is not None and cagr >= 25 and (debt_to_equity is None or debt_to_equity < 100):
        return "Expansion Flywheel"

    return "Balanced Execution"


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


def _build_watchlist_entry(
    company: Dict[str, Any],
    sector_info: Dict[str, Any],
    metadata: Dict[str, str]
) -> Dict[str, Any]:
    ticker = company.get("ticker", "UNKNOWN")
    sector = company.get("sector", "Unknown")
    industry = company.get("industry", metadata.get("industry"))
    company_name = metadata.get("name", ticker)

    quality_score = _safe_float(sector_info.get("quality_score"))
    sector_momentum = _safe_float(sector_info.get("avg_momentum_3m"))
    sector_momentum6 = _safe_float(sector_info.get("avg_momentum_6m"))

    cagr = _safe_float(company.get("cagr"))
    momentum_3m = _safe_float(company.get("momentum_3m"))
    momentum_6m = _safe_float(company.get("momentum_6m"))
    volatility = _safe_float(company.get("volatility"))
    pe_ratio = _safe_float(company.get("pe_ratio"))
    ps_ratio = _safe_float(company.get("ps_ratio"))
    debt_to_equity = _safe_float(company.get("debt_to_equity"))
    interest_coverage = _safe_float(company.get("interest_coverage"))

    explosive_sector = False
    if quality_score is not None and quality_score >= 70:
        explosive_sector = True
    if sector_momentum is not None and sector_momentum >= 15:
        explosive_sector = True

    growth_fast = False
    if momentum_6m is not None and momentum_6m >= 40:
        growth_fast = True
    if cagr is not None and cagr >= 25:
        growth_fast = True

    ai_layer = _infer_ai_layer(sector, industry)
    conviction_quadrant = _infer_conviction_quadrant(company)

    debt_manageable = True
    if debt_to_equity is not None and debt_to_equity > 180:
        debt_manageable = False
    if interest_coverage is not None and interest_coverage < 4:
        debt_manageable = False

    backlog_signal = True if momentum_3m and momentum_3m >= 5 else False

    base_pe_text = "N/A"
    bull_pe_text = "N/A"
    base_ps_text = "N/A"
    bull_ps_text = "N/A"
    if pe_ratio is not None and pe_ratio > 0:
        base_pe_text = f"{pe_ratio:.1f}"
        bull_pe_text = f"{pe_ratio * 1.2:.1f}"
    if ps_ratio is not None and ps_ratio > 0:
        base_ps_text = f"{ps_ratio:.1f}"
        bull_ps_text = f"{ps_ratio * 1.2:.1f}"

    came_down_from_highs = momentum_3m is not None and momentum_3m < 0

    score = 0
    if explosive_sector:
        score += 2
    if growth_fast:
        score += 2
    if ai_layer != "N/A":
        score += 1
    if debt_manageable:
        score += 1
    if backlog_signal:
        score += 1
    if pe_ratio is not None and pe_ratio < 80:
        score += 1
    if volatility is not None and volatility < 90:
        score += 1
    if came_down_from_highs:
        score += 0.5

    rating = "Monitor"
    if score >= 6:
        rating = "Buy"
    elif score >= 4.5:
        rating = "Watch"

    thesis_points: List[str] = []
    if explosive_sector:
        components = []
        if quality_score is not None:
            components.append(f"quality {quality_score:.0f}/100")
        if sector_momentum is not None:
            components.append(f"3M momentum {sector_momentum:+.1f}%")
        if sector_momentum6 is not None:
            components.append(f"6M momentum {sector_momentum6:+.1f}%")
        thesis_points.append(f"Explosive {sector} sector with {'; '.join(components)} supporting national and policy tailwinds.")
    else:
        thesis_points.append(f"{sector} sector momentum is mixed; position sizing should reflect policy and demand uncertainty.")

    if growth_fast:
        thesis_points.append(
            f"Growth accelerates as 6M momentum {momentum_6m or 0:+.1f}% and CAGR {cagr or 0:.1f}% reflect rapid adoption."
        )
    else:
        thesis_points.append("Growth trajectory is stabilizing; monitor for new catalysts before adding risk.")

    if ai_layer != "N/A":
        thesis_points.append(f"Technology readiness: positioned in the {ai_layer} layer of the AI stack, supporting feasibility of deployments.")

    if debt_manageable:
        thesis_points.append(
            f"Balance sheet manageable with Debt/Equity {debt_to_equity or 'N/A'} and interest coverage {interest_coverage or 'N/A'}."
        )
    else:
        thesis_points.append("Leverage profile elevated; prioritize cash flow monitoring before scaling exposure.")

    if backlog_signal:
        thesis_points.append(
            f"Demand visibility remains solid: 3M momentum {momentum_3m or 0:+.1f}% suggests healthy backlog conversion."
        )
    else:
        thesis_points.append("Order momentum has cooled; validate backlog commentary on the next call.")

    valuation_commentary = f"Valuation base P/E {base_pe_text} (bull {bull_pe_text}); P/S {base_ps_text} (bull {bull_ps_text})."
    thesis_points.append(valuation_commentary)

    if came_down_from_highs:
        thesis_points.append("Shares have pulled back from recent highs, offering a reset entry to rebuild positions.")
    else:
        thesis_points.append("Shares continue to probe highs; add on weakness to avoid chasing momentum.")

    thesis_points.append("Leadership & insider activity: no major turnover flagged; monitor Form 4 filings for unexpected selling.")
    thesis_points.append("Strategic deals & hiring: track press releases for partnerships and career-site hiring momentum to confirm execution.")
    thesis_points.append(f"Ecosystem role: {company_name} anchors {industry or 'its niche'}, providing {ai_layer if ai_layer != 'N/A' else 'core capabilities'} across the value chain.")

    risk_items: List[Dict[str, str]] = []
    risk_highlights: List[str] = []

    if volatility is not None and volatility > 90:
        risk_items.append({
            "title": "Volatility",
            "summary": f"Annualized volatility at {volatility:.1f}% implies sharp swings; size positions accordingly."
        })
        risk_highlights.append("High volatility")

    if debt_to_equity is not None and debt_to_equity > 180:
        risk_items.append({
            "title": "Leverage",
            "summary": f"Debt/Equity {debt_to_equity:.0f}x with interest coverage {interest_coverage or 'N/A'} requires disciplined cash management."
        })
        risk_highlights.append("Elevated leverage")

    if sector_momentum is not None and sector_momentum < 5:
        risk_items.append({
            "title": "Sector momentum",
            "summary": f"Sector momentum at {sector_momentum:+.1f}% could fade if policy or demand catalysts stall."
        })
        risk_highlights.append("Momentum fragile")

    if not risk_items:
        risk_items.append({
            "title": "Execution",
            "summary": "Track backlog conversion, tariff exposure, and supply chain reliability to avoid thesis drift."
        })
        risk_highlights.append("Execution vigilance")

    risk_summary = ", ".join(risk_highlights[:2])

    return {
        "ticker": ticker,
        "name": company_name,
        "sector": sector,
        "industry": industry,
        "ai_layer": ai_layer,
        "conviction": conviction_quadrant,
        "rating": rating,
        "score": round(score, 1),
        "thesis_points": thesis_points,
        "valuation": {
            "pe_base": base_pe_text,
            "pe_bull": bull_pe_text,
            "ps_base": base_ps_text,
            "ps_bull": bull_ps_text,
        },
        "risk": {
            "summary": risk_summary,
            "items": risk_items,
        },
    }


def build_deep_alpha_watchlist(
    company_metadata: Dict[str, Dict[str, str]],
    limit: int = WATCHLIST_LIMIT,
) -> List[Dict[str, Any]]:
    metrics_file = _latest_company_metrics_file()
    sector_file = _latest_sector_metrics_file()
    if not metrics_file or not metrics_file.exists():
        return []

    try:
        with metrics_file.open("r") as fh:
            company_metrics_data = json.load(fh)
    except Exception as exc:
        logger.warning("Failed to load company metrics for watchlist: %s", exc)
        return []

    sector_map: Dict[str, Any] = {}
    if sector_file and sector_file.exists():
        try:
            with sector_file.open("r") as fh:
                sector_payload = json.load(fh)
            sector_map = sector_payload.get("sectors", {})
        except Exception as exc:
            logger.warning("Failed to load sector metrics for watchlist: %s", exc)

    entries: List[Dict[str, Any]] = []
    for company in company_metrics_data:
        ticker = company.get("ticker")
        if not ticker:
            continue
        metadata = company_metadata.get(ticker, {})
        sector = company.get("sector", metadata.get("industry"))
        sector_info = sector_map.get(sector, {}) if isinstance(sector_map, dict) else {}

        entry = _build_watchlist_entry(company, sector_info, metadata)
        entries.append(entry)

    entries = sorted(entries, key=lambda item: item.get("score", 0), reverse=True)
    return entries[:limit]


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


def _normalize_link(link: Optional[str]) -> Optional[str]:
    if not link:
        return None
    cleaned = link.split("#", 1)[0].rstrip("/")
    return cleaned.lower() if cleaned else None


def _normalize_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    normalized = re.sub(r"\s+", " ", title).strip().lower()
    return normalized or None


def _article_identity(link: Optional[str], title: Optional[str]) -> Optional[str]:
    return _normalize_link(link) or _normalize_title(title)


def _article_matches_company(article: Dict[str, Any], ticker: str, company_name: Optional[str]) -> bool:
    text = " ".join(
        filter(
            None,
            [
                article.get("title"),
                article.get("summary"),
                article.get("snippet"),
                article.get("description"),
            ],
        )
    ).lower()
    if not text.strip():
        return False
    ticker_token = re.escape(ticker.lower())
    if re.search(rf"\b{ticker_token}\b", text):
        return True
    name_token = (company_name or "").strip().lower()
    if name_token and name_token in text:
        return True
    return False


def _parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    else:
        parsed = parsed.astimezone(timezone.utc)
    return parsed


def _coerce_timestamp(raw_value: Optional[str]) -> Optional[str]:
    if not raw_value:
        return None

    candidate = raw_value.strip()
    if not candidate:
        return None

    try:
        if candidate.endswith("Z"):
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(candidate)
        return parsed.astimezone(timezone.utc).isoformat()
    except ValueError:
        try:
            parsed = parsedate_to_datetime(candidate)
        except (TypeError, ValueError):
            parsed = None

        if parsed:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            else:
                parsed = parsed.astimezone(timezone.utc)
            return parsed.isoformat()
    except Exception:
        return None
    return None


def _extract_timestamp_from_html(html: str) -> Optional[str]:
    for pattern in META_TIMESTAMP_PATTERNS:
        match = pattern.search(html)
        if match:
            coerced = _coerce_timestamp(match.group(1))
            if coerced:
                return coerced

    for pattern in JSONLD_TIMESTAMP_PATTERNS:
        match = pattern.search(html)
        if match:
            coerced = _coerce_timestamp(match.group(1))
            if coerced:
                return coerced

    return None


def _fetch_article_timestamp(url: str) -> Optional[str]:
    cached = ARTICLE_TIMESTAMP_CACHE.get(url)
    if cached is not None:
        return cached

    timestamp: Optional[str] = None
    snippet = b""
    last_modified: Optional[str] = None

    try:
        request = Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (compatible; deep-alpha/1.0)"},
        )
        with urlopen(request, timeout=5, context=SSL_CONTEXT) as response:
            last_modified = response.headers.get("Last-Modified")
            snippet = response.read(ARTICLE_HTML_SNIFF_BYTES)
    except (HTTPError, URLError, TimeoutError, ValueError):
        snippet = b""
    except Exception:
        snippet = b""

    if snippet:
        try:
            html = snippet.decode("utf-8", errors="ignore")
        except Exception:
            html = ""
        if html:
            timestamp = _extract_timestamp_from_html(html)

    if not timestamp and last_modified:
        timestamp = _coerce_timestamp(last_modified)

    ARTICLE_TIMESTAMP_CACHE[url] = timestamp
    return timestamp


def _build_article_lookup(articles: List[dict]) -> Dict[str, Dict[str, dict]]:
    by_link: Dict[str, dict] = {}
    by_title: Dict[str, dict] = {}
    for article in articles:
        link_norm = _normalize_link(article.get("link"))
        if link_norm and link_norm not in by_link:
            by_link[link_norm] = article
        title_norm = _normalize_title(article.get("title"))
        if title_norm and title_norm not in by_title:
            by_title[title_norm] = article
    return {"by_link": by_link, "by_title": by_title}


def _load_offline_articles(ticker: str) -> List[dict]:
    try:
        from fetch_data import get_latest_news_file
    except Exception:
        return []

    news_file = get_latest_news_file(ticker)
    if not news_file:
        return []

    try:
        with open(news_file, "r") as fh:
            news_data = json.load(fh)
    except Exception:
        return []

    articles: List[dict] = []
    seen: set = set()

    for article in news_data.get("articles", []):
        title = article.get("title")
        link = article.get("link") or article.get("url")
        if not title:
            continue

        identity = _article_identity(link, title)
        if identity and identity in seen:
            continue
        if identity:
            seen.add(identity)

        snippet = article.get("summary") or article.get("snippet") or ""
        sentiment_info = _compute_article_sentiment(title, snippet)
        articles.append(
            {
                "title": title,
                "source": article.get("publisher") or article.get("source"),
                "link": link,
                "published": _coerce_timestamp(article.get("publish_time") or article.get("published")),
                "snippet": snippet,
                "sentiment": sentiment_info,
                "origin": "cached",
            }
        )

    return articles


def _merge_article_fields(primary: dict, fallback: Optional[dict]) -> dict:
    if not fallback:
        return primary

    for field in ("source", "snippet", "published"):
        if not primary.get(field) and fallback.get(field):
            primary[field] = fallback[field]

    if not primary.get("sentiment") and fallback.get("sentiment"):
        primary["sentiment"] = fallback["sentiment"]

    return primary


def _enrich_article_metadata(
    article: dict,
    lookup: Dict[str, Dict[str, dict]],
) -> dict:
    link = article.get("link")
    title = article.get("title")
    match = None

    link_norm = _normalize_link(link)
    if link_norm and link_norm in lookup["by_link"]:
        match = lookup["by_link"][link_norm]
    else:
        title_norm = _normalize_title(title)
        if title_norm and title_norm in lookup["by_title"]:
            match = lookup["by_title"][title_norm]

    article = _merge_article_fields(article, match)

    if not article.get("published") and link:
        article["published"] = _fetch_article_timestamp(link)

    return article


def _sort_articles_descending(articles: List[dict]) -> List[dict]:
    def sort_key(entry: dict) -> datetime:
        published_dt = _parse_iso_datetime(entry.get("published"))
        if published_dt:
            return published_dt
        return datetime.fromtimestamp(0, tz=timezone.utc)

    return sorted(articles, key=sort_key, reverse=True)


def _load_offline_news_summary(ticker: str) -> Optional[dict]:
    articles = _load_offline_articles(ticker)
    if not articles:
        return None

    metadata = load_company_metadata()
    company_profile = metadata.get(ticker.upper(), {})
    company_name = company_profile.get("name", ticker)

    articles = _sort_articles_descending(articles)
    relevant_articles = [a for a in articles if _article_matches_company(a, ticker, company_name)]
    if relevant_articles:
        articles = relevant_articles

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

    origin_counter = Counter(a.get("origin", "cached") for a in articles)
    origin_breakdown = []
    if origin_counter.get("live"):
        origin_breakdown.append(f"{origin_counter['live']} live")
    if origin_counter.get("cached"):
        origin_breakdown.append(f"{origin_counter['cached']} cached")

    headlines = [
        {
            "title": art.get("title"),
            "source": art.get("source"),
            "link": art.get("link"),
            "origin": art.get("origin", "cached"),
            "published": art.get("published"),
            "snippet": art.get("snippet"),
        }
        for art in articles[:3]
    ]

    extended_commentary = (
        f"Snapshot built from {len(articles)} cached article(s). "
        + " ".join(
            f"{headline.get('source', 'Source')} on \"{headline.get('title')}\""
            for headline in headlines[:2]
            if headline.get("title")
        )
    ).strip()

    payload = {
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
            "headlines": headlines,
            "source_note": "Derived from cached news files",
            "extended_commentary": extended_commentary,
        },
        "articles": articles,
    }
    _update_company_runtime(ticker, "news", payload)
    return payload


def fetch_realtime_news(ticker: str, window_hours: int = 72, max_results: int = 8) -> dict:
    ticker = ticker.upper()
    metadata = load_company_metadata()
    company_profile = metadata.get(ticker, {})
    company_name = company_profile.get("name", ticker)
    offline_articles = _load_offline_articles(ticker)
    offline_lookup = _build_article_lookup(offline_articles) if offline_articles else {"by_link": {}, "by_title": {}}

    # Check if search is available (using new SEARCH_AVAILABLE flag or ADK_AVAILABLE fallback)
    search_is_active = globals().get("SEARCH_AVAILABLE", False) or (globals().get("ADK_AVAILABLE", False) and "search_latest_news" in globals())

    if not search_is_active:
        fallback = _load_offline_news_summary(ticker)
        if fallback:
            return fallback
        return {
            "ticker": ticker,
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
            "ticker": ticker,
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

    seen_keys = set()
    articles: List[dict] = []
    cutoff = datetime.now(timezone.utc) - timedelta(hours=window_hours) if window_hours else None

    for item in items:
        link = item.get("link")
        title = (item.get("title") or "").strip()
        identity = _article_identity(link, title)
        if not title or (identity and identity in seen_keys):
            continue
        if identity:
            seen_keys.add(identity)

        snippet = (item.get("snippet") or "").strip()
        sentiment_info = _compute_article_sentiment(title, snippet)

        article = {
            "title": title,
            "source": item.get("source"),
            "link": link,
            "published": _coerce_timestamp(item.get("published")),
            "snippet": snippet,
            "sentiment": sentiment_info,
            "origin": "live",
        }

        article = _enrich_article_metadata(article, offline_lookup)

        if cutoff and article.get("published"):
            published_dt = _parse_iso_datetime(article.get("published"))
            if published_dt and published_dt < cutoff:
                continue

        articles.append(article)

    relevant_articles = [a for a in articles if _article_matches_company(a, ticker, company_name)]
    if relevant_articles:
        articles = relevant_articles

    if window_hours and articles:
        filtered: List[dict] = []
        for art in articles:
            published_dt = _parse_iso_datetime(art.get("published"))
            if not published_dt or published_dt >= cutoff:
                filtered.append(art)
        if filtered:
            articles = filtered

    if len(articles) < max_results and offline_articles:
        for offline_article in offline_articles:
            identity = _article_identity(offline_article.get("link"), offline_article.get("title"))
            if identity and identity in seen_keys:
                continue
            if cutoff and offline_article.get("published"):
                offline_dt = _parse_iso_datetime(offline_article.get("published"))
                if offline_dt and offline_dt < cutoff:
                    continue
            articles.append(offline_article)
            if identity:
                seen_keys.add(identity)
            if len(articles) >= max_results:
                break

    articles = _sort_articles_descending(articles)[:max_results]

    if not articles:
        fallback = _load_offline_news_summary(ticker)
        if fallback:
            return fallback
        return {
            "ticker": ticker,
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
    if offline_articles:
        rationale_parts.append("Live feed supplemented with cached Yahoo Finance coverage for continuity.")
    else:
        rationale_parts.append("Live headlines sourced within the last 72 hours.")

    origin_counter = Counter(a.get("origin", "live") for a in articles)
    origin_breakdown = []
    if origin_counter.get("live"):
        origin_breakdown.append(f"{origin_counter['live']} live")
    if origin_counter.get("cached"):
        origin_breakdown.append(f"{origin_counter['cached']} cached")
    source_note = (
        f"Derived from {len(articles)} ticker-specific headline(s)"
        + (f" ({', '.join(origin_breakdown)})" if origin_breakdown else "")
    )

    headlines = [
        {
            "title": art.get("title"),
            "source": art.get("source"),
            "link": art.get("link"),
            "origin": art.get("origin", "live"),
            "published": art.get("published"),
            "snippet": art.get("snippet"),
        }
        for art in articles[:3]
    ]
    key_points = [
        f"{headline.get('source', 'Source')}: {headline.get('title')}"
        for headline in headlines
        if headline.get("title")
    ]

    drivers = [
        f"{headline.get('source', 'Source')} on \"{headline.get('title')}\""
        for headline in headlines[:2]
        if headline.get("title")
    ]
    extended_commentary = (
        f"Snapshot built from {len(articles)} {ticker} article(s) ({', '.join(origin_breakdown) or 'mixed sources'}). "
        f"{' • '.join(drivers)}"
        if articles
        else "No recent coverage matched the ticker filters."
    )

    payload = {
        "ticker": ticker,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "sentiment": overall_sentiment,
            "rating": rating,
            "confidence": "Medium" if len(articles) >= 3 else "Low",
            "headline": f"Latest coverage skews {overall_sentiment.lower()}",
            "key_points": key_points,
            "headlines": headlines,
            "rationale": " ".join(rationale_parts),
            "conclusion": (
                "Momentum favors accumulation on strength."
                if rating == "Buy"
                else "Maintain exposure and reassess frequently."
                if rating == "Hold"
                else "Consider trimming positions or tightening stops."
            ),
            "source_note": source_note,
            "extended_commentary": extended_commentary,
        },
        "articles": articles,
    }
    _update_company_runtime(ticker, "news", payload)
    return payload


def _load_flow_snapshot(ticker: str, flow_type: str = "combined") -> Dict[str, Any]:
    """Load the most recent flow file for a ticker and flow type."""
    ticker = ticker.upper()
    if flow_type == "combined":
        pattern = f"{ticker}_combined_flow_*.json"
    elif flow_type == "institutional":
        pattern = f"{ticker}_institutional_flow_*.json"
    elif flow_type == "retail":
        pattern = f"{ticker}_retail_flow_*.json"
    else:
        raise ValueError(f"Invalid flow_type: {flow_type}")

    flow_files = sorted(FLOW_DATA_DIR.glob(pattern))
    if not flow_files:
        raise FileNotFoundError(f"No flow data found for {ticker}")

    latest_file = flow_files[-1]
    with latest_file.open("r") as fh:
        payload = json.load(fh)

    file_date = latest_file.stem.split("_")[-1]
    return {
        "data": payload,
        "file_date": file_date,
        "file_name": latest_file.name,
    }


def _generate_flow_summary(ticker: str, flow_payload: Dict[str, Any]) -> Dict[str, Any]:
    """Use Gemini (if available) to summarize flow data."""
    fallback = {
        "headline": f"{ticker} flow update",
        "summary": "Detailed flow summary is unavailable. Please expand to review the underlying data.",
        "callouts": [],
    }
    if not flow_payload:
        return fallback

    institutional = flow_payload.get("institutional", {}) or {}
    retail = flow_payload.get("retail", {}) or {}
    changes = flow_payload.get("institutional_changes", {}) or {}
    retail_metrics = retail.get("metrics", {}) or {}
    retail_interpretation = retail.get("interpretation", {}) or {}

    summary_context = {
        "ticker": ticker,
        "institutional": {
            "ownership_pct": institutional.get("institutional_ownership_pct"),
            "top_holder": (institutional.get("top_10_holders") or [{}])[0:3],
            "total_value": institutional.get("total_institutional_value"),
        },
        "changes": {
            "net_change_pct": changes.get("net_change_pct"),
            "institutions_increased": changes.get("institutions_increased"),
            "institutions_decreased": changes.get("institutions_decreased"),
        },
        "retail": {
            "estimated_participation": retail_metrics.get("estimated_avg_retail_participation_pct"),
            "net_flow_indicator": retail_metrics.get("net_flow_indicator_pct"),
            "trend": retail_interpretation.get("retail_trend"),
            "flow_direction": retail_interpretation.get("flow_direction"),
        },
    }

    if GENAI_AVAILABLE:
        prompt = (
            "You are a sell-side analyst summarizing institutional and retail flow data for investors.\n"
            "Given the JSON context below, respond strictly in JSON with keys "
            "`headline` (<=120 characters), `summary` (2 concise sentences), "
            "and `callouts` (list of up to 3 short bullet strings highlighting notable stats).\n"
            f"Context: {json.dumps(summary_context)}"
        )
        try:
            model = genai.GenerativeModel(FLOW_SUMMARY_MODEL)
            response = model.generate_content(prompt)
            text = (response.text or "").strip()
            if text.startswith("```"):
                text = text.strip("`")
                text = re.sub(r"^json", "", text, flags=re.IGNORECASE).strip()
            parsed = json.loads(text)
            return {
                "headline": parsed.get("headline", fallback["headline"]),
                "summary": parsed.get("summary", fallback["summary"]),
                "callouts": parsed.get("callouts", fallback["callouts"]),
            }
        except Exception as exc:  # pragma: no cover - graceful degradation
            logger.warning("Flow summary generation failed: %s", exc)

    # Fallback summary built from available metrics
    ownership_pct = institutional.get("institutional_ownership_pct")
    net_flow = changes.get("net_change_pct")
    retail_trend = retail_interpretation.get("retail_trend") or "stable"
    fallback["headline"] = (
        f"{ticker} institutional ownership {ownership_pct:.1f}%"
        if isinstance(ownership_pct, (int, float))
        else f"{ticker} flow snapshot"
    )
    change_text = (
        f"Net institutional { 'inflows' if (net_flow or 0) >= 0 else 'outflows' } of {abs(net_flow):.1f}%"
        if isinstance(net_flow, (int, float))
        else "Institutional activity mixed across recent filings"
    )
    retail_text = (
        f"Retail participation trend appears {retail_trend} with estimated share "
        f"{retail_metrics.get('estimated_avg_retail_participation_pct', 'n/a')}%."
    )
    fallback["summary"] = f"{change_text}. {retail_text}"
    fallback["callouts"] = [
        change_text,
        retail_text,
    ]
    return fallback


def _sync_token_usage_outputs():
    """Move any legacy-generated files under /app/data into DATA_ROOT."""
    try:
        if LEGACY_TOKEN_USAGE_DIR.resolve() == TOKEN_USAGE_DIR.resolve():
            return
    except FileNotFoundError:
        return

    if not LEGACY_TOKEN_USAGE_DIR.exists():
        return

    for artifact in LEGACY_TOKEN_USAGE_DIR.glob("token_usage_*"):
        target = TOKEN_USAGE_DIR / artifact.name
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            if artifact.resolve() == target.resolve():
                continue
        except FileNotFoundError:
            continue

        try:
            shutil.copy2(artifact, target)
            artifact.unlink(missing_ok=True)
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Unable to sync %s to %s: %s", artifact, target, exc)


def _latest_token_usage_files():
    token_files = sorted(TOKEN_USAGE_DIR.glob("token_usage_*.json"))
    plot_files = sorted(TOKEN_USAGE_DIR.glob("token_usage_plot_*.png"))
    return (token_files[-1] if token_files else None, plot_files[-1] if plot_files else None)


async def _ensure_token_usage_assets():
    token_file, plot_file = _latest_token_usage_files()
    plot_required = getattr(token_usage_module, "MATPLOTLIB_AVAILABLE", True)
    if token_file and (plot_file or not plot_required):
        return token_file, plot_file

    async with TOKEN_USAGE_LOCK:
        token_file, plot_file = _latest_token_usage_files()
        if token_file and (plot_file or not plot_required):
            return token_file, plot_file

        loop = asyncio.get_event_loop()
        logger.info("No token usage data found. Generating snapshot from OpenRouter rankings...")
        await loop.run_in_executor(None, fetch_and_save_token_usage, 365)
        _sync_token_usage_outputs()
        token_file, plot_file = _latest_token_usage_files()
        if not token_file:
            raise RuntimeError("Token usage generation failed to produce artifacts.")
        if not plot_file:
            if plot_required:
                raise RuntimeError("Token usage generation failed to produce plot artifacts.")
            logger.warning("Token usage plot skipped because matplotlib is unavailable in this environment.")
        logger.info("Token usage snapshot generated: %s", token_file.name)
        return token_file, plot_file


# --- ADK Agent Runner Setup ---
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

def _download_data_sync():
    """Synchronous wrapper for data download."""
    try:
        from storage_helper import get_storage_manager
        storage_manager = get_storage_manager()
        return storage_manager.download_all_data()
    except Exception as e:
        print(f"⚠️ Warning: Could not download data from Cloud Storage: {e}")
        return 0

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background data download (non-blocking)
    # This allows the app to start serving requests immediately
    if os.getenv("K_SERVICE") or os.getenv("FORCE_STARTUP_DOWNLOAD"):
        print("Starting background data download from Cloud Storage...")
        loop = asyncio.get_event_loop()
        # Fire and forget - don't await, app starts immediately
        loop.run_in_executor(None, _download_data_sync)
        print("✅ Background data download started (app ready, data loading in background)")
    
    # On startup, initialize the ADK AgentCaller
    if ADK_AVAILABLE:
        print("Initializing ADK Agent...")
        try:
            app.state.agent_caller = await make_agent_caller(root_agent)
            print("Agent is ready.")
        except Exception as e:
            print(f"Failed to initialize agent: {e}")
            app.state.agent_caller = None
    else:
        print("ADK not available. Agent features disabled.")
        app.state.agent_caller = None
    
    await database.connect()
    yield
    await database.disconnect()
    print("Shutting down.")


app = FastAPI(
    title="Clinical Assistant API (ADK Version)",
    description="An API for interacting with the Clinical AI Assistant, powered by Google ADK.",
    version="2.0.0",
    lifespan=lifespan
)

# Add session middleware and template rendering
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "changeme"))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
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
    watchlist = build_deep_alpha_watchlist(company_metadata)
    
    return templates.TemplateResponse(
        "index.html", 
        {
        "request": request,
        "user": user,
        "supported_tickers": supported_tickers,
        "supported_tickers_json": json.dumps(supported_tickers),
        "company_metadata_json": json.dumps(company_metadata),
        "watchlist_json": json.dumps(watchlist),
        }
    )


@app.get("/about", response_class=HTMLResponse)
async def get_about(request: Request):
    """Serves the marketing about page."""
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/research", response_class=HTMLResponse)
async def get_research(request: Request):
    """Serves the research/architecture page."""
    return templates.TemplateResponse("research.html", {"request": request})


@app.get("/team", response_class=HTMLResponse)
async def get_team(request: Request):
    """Serves the team page."""
    return templates.TemplateResponse("team.html", {"request": request})


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

        # Attach per-ticker data freshness info
        t = ticker.upper()
        def _file_age_info(directory: Path, pattern: str) -> Optional[dict]:
            if not directory.exists():
                return None
            files = sorted(directory.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
            if not files:
                return None
            ts = datetime.fromtimestamp(files[0].stat().st_mtime, tz=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            return {"last_updated": ts.isoformat(), "age_hours": round(age_hours, 1)}

        data["data_freshness"] = {
            "prices": _file_age_info(DATA_ROOT / "structured" / "prices", f"{t}_prices.csv"),
            "financials": _file_age_info(DATA_ROOT / "structured" / "financials", f"{t}_financials*.json"),
            "earnings": _file_age_info(DATA_ROOT / "structured" / "earnings", f"{t}_earnings*.json"),
            "news": _file_age_info(DATA_ROOT / "unstructured" / "news", f"{t}_news_*.json"),
            "reddit": _file_age_info(DATA_ROOT / "unstructured" / "reddit", f"{t}_reddit_posts_*.json"),
            "twitter": _file_age_info(DATA_ROOT / "unstructured" / "x", f"{t}_x_posts_*.json"),
            "flow": _file_age_info(DATA_ROOT / "structured" / "flow_data", f"{t}_flow_*.json"),
        }

        return {"status": "success", "data": data}
    except ScoreComputationError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - unexpected errors bubbled to client
        return {"status": "error", "message": f"Unexpected error: {exc}"}

@app.get("/api/universe")
async def get_universe_overview():
    """Return lightweight overview data for all tickers in the coverage universe."""
    import yfinance as yf
    from target_tickers import TARGET_TICKERS

    def _fetch_universe():
        tickers_data = []
        # Batch download basic info for all tickers
        for ticker in TARGET_TICKERS:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info or {}
                price = info.get("currentPrice") or info.get("regularMarketPrice") or 0
                prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose") or 0
                day_change_pct = ((price - prev_close) / prev_close * 100) if prev_close > 0 else 0

                tickers_data.append({
                    "ticker": ticker,
                    "name": info.get("shortName") or info.get("longName") or ticker,
                    "sector": info.get("sector") or "N/A",
                    "industry": info.get("industry") or "N/A",
                    "price": round(price, 2),
                    "day_change_pct": round(day_change_pct, 2),
                    "market_cap": info.get("marketCap") or 0,
                    "pe_ratio": info.get("trailingPE"),
                    "forward_pe": info.get("forwardPE"),
                    "beta": info.get("beta"),
                    "profit_margin": round((info.get("profitMargins") or 0) * 100, 1) if info.get("profitMargins") else None,
                    "revenue_growth": round((info.get("revenueGrowth") or 0) * 100, 1) if info.get("revenueGrowth") else None,
                    "dividend_yield": round((info.get("dividendYield") or 0) * 100, 2) if info.get("dividendYield") else None,
                    "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
                    "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
                })
            except Exception:
                tickers_data.append({
                    "ticker": ticker,
                    "name": ticker,
                    "sector": "N/A",
                    "industry": "N/A",
                    "price": 0,
                    "day_change_pct": 0,
                    "market_cap": 0,
                    "pe_ratio": None,
                    "forward_pe": None,
                    "beta": None,
                    "profit_margin": None,
                    "revenue_growth": None,
                    "dividend_yield": None,
                    "fifty_two_week_high": None,
                    "fifty_two_week_low": None,
                })
        return tickers_data

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, _fetch_universe)
        data = sanitize_for_json(data)
        return {"status": "success", "data": data}
    except Exception as exc:
        return {"status": "error", "message": f"Universe fetch failed: {exc}"}

@app.get("/api/personas/{ticker}")
async def get_persona_analysis(ticker: str, personas: Optional[str] = None, context: Optional[str] = None):
    """Run investor persona analysis for a ticker.

    Optional query params:
        personas: comma-separated persona IDs (e.g. ?personas=buffett,burry)
        context: strategic/geopolitical context to factor into analysis
    """
    from app.scoring import compute_company_scores, analyze_all_personas

    try:
        loop = asyncio.get_event_loop()
        scores_data = await loop.run_in_executor(None, compute_company_scores, ticker.upper())
        persona_ids = [p.strip() for p in personas.split(",") if p.strip()] if personas else None
        result = await loop.run_in_executor(
            None, analyze_all_personas, scores_data, persona_ids, 4, context
        )
        result = sanitize_for_json(result)
        return {"status": "success", "data": result}
    except Exception as exc:
        return {"status": "error", "message": f"Persona analysis failed: {exc}"}

@app.post("/api/personas/{ticker}/reconcile")
async def reconcile_personas(ticker: str, request: Request):
    """Run full persona analysis + reconciliation for a ticker.

    Accepts optional JSON body:
        {"prompt": "...", "context": "strategic context..."}
    """
    from app.scoring import compute_company_scores, analyze_all_personas, run_reconciliation

    try:
        body = {}
        try:
            body = await request.json()
        except Exception:
            pass
        custom_prompt = body.get("prompt") if isinstance(body, dict) else None
        strategic_context = body.get("context") if isinstance(body, dict) else None

        loop = asyncio.get_event_loop()
        scores_data = await loop.run_in_executor(None, compute_company_scores, ticker.upper())
        persona_results = await loop.run_in_executor(
            None, analyze_all_personas, scores_data, None, 4, strategic_context
        )
        reconciliation = await loop.run_in_executor(
            None, run_reconciliation, persona_results, scores_data, custom_prompt
        )

        result = {
            "personas": persona_results,
            "reconciliation": reconciliation,
        }
        result = sanitize_for_json(result)
        return {"status": "success", "data": result}
    except Exception as exc:
        return {"status": "error", "message": f"Reconciliation failed: {exc}"}

@app.get("/api/forward-pe/{ticker}")
async def get_forward_pe_analysis(ticker: str):
    """Return forward P/E cross-referencing analysis for a ticker."""
    from app.scoring import compute_company_scores, compute_forward_pe_reliability

    try:
        loop = asyncio.get_event_loop()
        scores_data = await loop.run_in_executor(None, compute_company_scores, ticker.upper())
        quick_facts = scores_data.get("quick_facts", {})
        scores = scores_data.get("scores", {})

        trailing_pe = quick_facts.get("pe_ratio")
        forward_pe = quick_facts.get("forward_pe")
        revenue_growth = quick_facts.get("revenue_growth_yoy")

        financial_inputs = {}
        fin_score = scores.get("financial")
        if fin_score:
            if hasattr(fin_score, "inputs"):
                financial_inputs = fin_score.inputs if isinstance(fin_score.inputs, dict) else {}
            elif isinstance(fin_score, dict):
                financial_inputs = fin_score.get("inputs", {})

        result = compute_forward_pe_reliability(
            trailing_pe, forward_pe, revenue_growth, financial_inputs
        )
        result = sanitize_for_json(result)
        return {"status": "success", "data": result}
    except Exception as exc:
        return {"status": "error", "message": f"Forward P/E analysis failed: {exc}"}

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
        
        # If no cached news OR cached news has no articles, fetch realtime
        if not payload or not payload.get("articles") or len(payload.get("articles", [])) == 0:
            # Try to download news file from GCS if in production
            if os.getenv("K_SERVICE"):
                from storage_helper import get_storage_manager
                storage_manager = get_storage_manager()
                try:
                    if storage_manager.bucket:
                        # Try to download latest news file for this ticker
                        prefix = f"data/unstructured/news/{ticker}_news_"
                        blobs = list(storage_manager.bucket.list_blobs(prefix=prefix))
                        if blobs:
                            latest_blob = sorted(blobs, key=lambda b: b.name, reverse=True)[0]
                            news_dir = DATA_ROOT / "unstructured" / "news"
                            news_dir.mkdir(parents=True, exist_ok=True)
                            local_path = news_dir / latest_blob.name.split("/")[-1]
                            storage_manager.download_file(latest_blob.name, local_path)
                            logger.info(f"Downloaded news file from GCS: {latest_blob.name}")
                            # Reload from cache after download
                            payload = _load_cached_news(ticker)
                except Exception as e:
                    logger.debug(f"Could not download news file from GCS for {ticker}: {e}")
            
            # If still no articles, fetch realtime
            if not payload or not payload.get("articles") or len(payload.get("articles", [])) == 0:
                logger.info(f"Fetching realtime news for {ticker} (no cached articles)")
                payload = fetch_realtime_news(ticker)
                if payload and payload.get("articles"):
                    _save_cached_news(ticker, payload)

        # Try to download interpretation files from GCS if in production
        interpretation_dir = DATA_ROOT / "unstructured" / "news_interpretation"
        interpretation_dir.mkdir(parents=True, exist_ok=True)
        if os.getenv("K_SERVICE"):
            from storage_helper import get_storage_manager
            storage_manager = get_storage_manager()
            # Try to download latest interpretation file from GCS
            try:
                if storage_manager.bucket:
                    # List files in GCS
                    prefix = f"data/unstructured/news_interpretation/{ticker}_news_interpretation_"
                    blobs = list(storage_manager.bucket.list_blobs(prefix=prefix))
                    if blobs:
                        # Download the latest one
                        latest_blob = sorted(blobs, key=lambda b: b.name, reverse=True)[0]
                        local_path = interpretation_dir / latest_blob.name.split("/")[-1]
                        storage_manager.download_file(latest_blob.name, local_path)
            except Exception as e:
                logger.debug(f"Could not download interpretation from GCS for {ticker}: {e}")

        # Attach Deep Alpha interpretation card (new structure) and legacy text fallback if available
        deep_alpha_card: Optional[dict] = None
        interpretation_summary: Optional[str] = None
        card_generated_at: Optional[str] = None
        
        interpretation_files = sorted(
            [
                file_path
                for file_path in interpretation_dir.glob(f"{ticker}_news_interpretation_*.json")
            ]
        )
        if interpretation_files:
            try:
                with interpretation_files[-1].open("r") as fh:
                    interpretation_blob = json.load(fh)
                card_generated_at = interpretation_blob.get("interpretation_timestamp")
                raw_interpretation = (
                    interpretation_blob.get("interpretation")
                    or interpretation_blob.get("analysis")
                )

                if isinstance(raw_interpretation, dict):
                    deep_alpha_card = raw_interpretation
                    # Preserve metadata if present (for quality indicators)
                    if '_metadata' in deep_alpha_card:
                        # Keep metadata for UI display
                        pass
                elif isinstance(raw_interpretation, str):
                    try:
                        parsed = json.loads(raw_interpretation)
                        if isinstance(parsed, dict):
                            deep_alpha_card = parsed
                        else:
                            interpretation_summary = raw_interpretation
                    except json.JSONDecodeError:
                        interpretation_summary = raw_interpretation
                elif raw_interpretation is not None:
                    interpretation_summary = str(raw_interpretation)

                # Preserve legacy analysis field if available separately
                if not interpretation_summary:
                    interpretation_summary = interpretation_blob.get("analysis")
                
                # Check if interpretation is stale (older than news) or if news articles have changed
                interpretation_stale = False
                news_changed = False
                
                if card_generated_at and payload.get("fetched_at"):
                    try:
                        interp_time = datetime.fromisoformat(card_generated_at.replace('Z', '+00:00'))
                        news_time = datetime.fromisoformat(payload["fetched_at"].replace('Z', '+00:00'))
                        # If interpretation is older than news, it's stale
                        if interp_time < news_time:
                            interpretation_stale = True
                            logger.info(f"Interpretation for {ticker} is older than news data (interp: {card_generated_at}, news: {payload['fetched_at']})")
                    except Exception:
                        pass
                
                # Check if news articles have changed by comparing article links
                if not interpretation_stale and deep_alpha_card:
                    try:
                        # Get article links from current news
                        current_article_links = set()
                        for article in payload.get("articles", []):
                            link = article.get("link") or article.get("url")
                            if link:
                                current_article_links.add(link)
                        
                        # Get article links from interpretation metadata
                        interp_articles = interpretation_blob.get("articles", [])
                        interp_article_links = set()
                        for article in interp_articles:
                            link = article.get("link") or article.get("url")
                            if link:
                                interp_article_links.add(link)
                        
                        # If article sets differ significantly, news has changed
                        if current_article_links and interp_article_links:
                            # Check if more than 30% of articles are different
                            common_links = current_article_links & interp_article_links
                            if len(common_links) / max(len(current_article_links), len(interp_article_links)) < 0.7:
                                news_changed = True
                                logger.info(f"News articles changed for {ticker}: {len(current_article_links)} current vs {len(interp_article_links)} in interpretation")
                    except Exception as e:
                        logger.debug(f"Error comparing articles: {e}")
                
                # If interpretation is stale or news changed, clear it to force regeneration
                if interpretation_stale or news_changed:
                    logger.info(f"Regenerating interpretation for {ticker} (stale: {interpretation_stale}, news_changed: {news_changed})")
                    deep_alpha_card = None
                    interpretation_summary = None
                    card_generated_at = None
                    
            except Exception as e:
                logger.warning(f"Error loading interpretation for {ticker}: {e}")
                interpretation_summary = None
        
        # If no interpretation exists (or was cleared due to stale/changed news) and we have articles, generate one on-the-fly
        articles_list = payload.get("articles", [])
        if not deep_alpha_card and not interpretation_summary and articles_list and len(articles_list) > 0:
            try:
                logger.info(f"Generating interpretation on-the-fly for {ticker} with {len(articles_list)} articles...")
                loop = asyncio.get_event_loop()
                interpretation_json = await loop.run_in_executor(
                    None,
                    interpret_news_with_deep_alpha,
                    ticker,
                    articles_list
                )
                if interpretation_json:
                    try:
                        parsed = json.loads(interpretation_json)
                        if isinstance(parsed, dict):
                            deep_alpha_card = parsed
                            card_generated_at = datetime.now(timezone.utc).isoformat()
                            logger.info(f"✅ Generated interpretation for {ticker} on-the-fly")
                            
                            # Save the new interpretation to cache and GCS
                            try:
                                from fetch_data.news_analysis import save_news_interpretation
                                from pathlib import Path
                                import tempfile
                                
                                # Create a temporary news file with current payload for save_news_interpretation
                                news_dir = DATA_ROOT / "unstructured" / "news"
                                news_dir.mkdir(parents=True, exist_ok=True)
                                temp_news_file = news_dir / f"{ticker}_news_temp_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
                                
                                # Save current payload as news file format
                                news_payload = {
                                    "ticker": ticker,
                                    "articles": articles_list,
                                    "fetch_timestamp": payload.get("fetched_at"),
                                    "fetched_at": payload.get("fetched_at")
                                }
                                with temp_news_file.open("w") as f:
                                    json.dump(news_payload, f, indent=2)
                                
                                # Save interpretation
                                interpretation_path = save_news_interpretation(ticker, str(temp_news_file))
                                if interpretation_path:
                                    logger.info(f"✅ Saved new interpretation for {ticker} to {interpretation_path}")
                                
                                # Clean up temp file
                                try:
                                    temp_news_file.unlink()
                                except:
                                    pass
                                    
                            except Exception as save_error:
                                logger.warning(f"Could not save interpretation for {ticker}: {save_error}")
                        else:
                            interpretation_summary = interpretation_json
                    except json.JSONDecodeError:
                        interpretation_summary = interpretation_json
            except Exception as e:
                logger.warning(f"Failed to generate interpretation for {ticker}: {e}")
                import traceback
                logger.debug(f"Traceback: {traceback.format_exc()}")

        payload["deep_alpha_analysis"] = deep_alpha_card
        payload["legacy_analysis"] = interpretation_summary
        payload["analysis_generated_at"] = card_generated_at

        return {"status": "success", "data": payload}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch latest news: {exc}"}


@app.get("/api/flow-data/{ticker}")
async def get_flow_data(ticker: str, flow_type: str = "combined"):
    """Return institutional and retail flow data for a ticker."""
    try:
        snapshot = _load_flow_snapshot(ticker, flow_type)
        return {"status": "success", "data": snapshot}
    except ValueError as ve:
        return {"status": "error", "message": str(ve)}
    except FileNotFoundError:
        return {"status": "error", "message": f"No flow data found for {ticker.upper()}"}
    except Exception as exc:
        logger.error(f"Error loading flow data for {ticker}: {exc}")
        return {"status": "error", "message": f"Failed to fetch flow data: {exc}"}


@app.post("/api/scheduler/update/{data_type}")
async def scheduler_update_data(data_type: str, request: Request):
    """
    Endpoint for Cloud Scheduler to trigger data updates.
    Protected by checking for Cloud Scheduler user agent or secret header.
    """
    # Verify request is from Cloud Scheduler (basic security)
    # In production, you should use Cloud Scheduler's OIDC token or a secret header
    scheduler_secret = os.getenv("SCHEDULER_SECRET")
    request_secret = request.headers.get("X-Scheduler-Secret")
    
    if scheduler_secret and request_secret != scheduler_secret:
        return {"status": "error", "message": "Unauthorized"}
    
    try:
        from scheduler_jobs import update_last_updated_timestamp
        
        if data_type == "scoring_data":
            # Update financial statements, earnings, prices (quarterly)
            from fetch_data import fetch_financial_statements, fetch_quarterly_earnings, fetch_stock_prices
            # This would call the actual fetch functions
            update_last_updated_timestamp("scoring_data")
            return {"status": "success", "message": f"Updated {data_type}"}
        
        elif data_type == "sentiment_data":
            # Update Reddit and X sentiment (weekly)
            from fetch_data import fetch_reddit_sentiment, fetch_x_sentiment
            update_last_updated_timestamp("sentiment_data")
            return {"status": "success", "message": f"Updated {data_type}"}
        
        elif data_type == "news_data":
            # Fetch latest news (past 72 hours, daily at 2am PST)
            from app.main import fetch_realtime_news
            from target_tickers import TARGET_TICKERS
            loop = asyncio.get_event_loop()
            for ticker in TARGET_TICKERS:
                try:
                    payload = await loop.run_in_executor(None, fetch_realtime_news, ticker, 72, 8)
                    _save_cached_news(ticker, payload)
                except Exception as e:
                    logger.warning(f"Failed to fetch news for {ticker}: {e}")
            update_last_updated_timestamp("news_data")
            return {"status": "success", "message": f"Updated {data_type}"}
        
        elif data_type == "institutional_flow":
            # Update institutional flow data (quarterly)
            from fetch_data import fetch_combined_flow_data
            from target_tickers import TARGET_TICKERS
            from pathlib import Path
            flow_dir = Path("data/unstructured/flow")
            for ticker in TARGET_TICKERS:
                try:
                    fetch_combined_flow_data(ticker, flow_dir)
                except Exception as e:
                    logger.warning(f"Failed to fetch flow data for {ticker}: {e}")
            update_last_updated_timestamp("institutional_flow")
            return {"status": "success", "message": f"Updated {data_type}"}
        
        elif data_type == "momentum_data":
            # Update price data and technical indicators (daily at 2am PST)
            from fetch_data import fetch_stock_prices
            from target_tickers import TARGET_TICKERS
            for ticker in TARGET_TICKERS:
                try:
                    fetch_stock_prices(ticker)
                except Exception as e:
                    logger.warning(f"Failed to fetch momentum data for {ticker}: {e}")
            update_last_updated_timestamp("momentum_data")
            return {"status": "success", "message": f"Updated {data_type}"}
        
        else:
            return {"status": "error", "message": f"Unknown data type: {data_type}"}
    
    except Exception as exc:
        logger.error(f"Error updating {data_type}: {exc}")
        return {"status": "error", "message": str(exc)}


@app.get("/api/data-status")
async def get_data_status():
    """Return last updated timestamps for all data types, computed from actual files."""
    try:
        from scheduler_jobs import UPDATE_SCHEDULES

        def _newest_file_time(directory: Path, pattern: str = "*") -> Optional[datetime]:
            """Return the modification time of the newest file matching pattern."""
            if not directory.exists():
                return None
            files = sorted(directory.glob(pattern), key=lambda f: f.stat().st_mtime, reverse=True)
            if not files:
                return None
            return datetime.fromtimestamp(files[0].stat().st_mtime, tz=timezone.utc)

        def _freshness_status(last_updated: Optional[datetime], max_age_hours: float) -> dict:
            """Compute freshness status: fresh / stale / critical."""
            if not last_updated:
                return {"label": "unavailable", "color": "slate"}
            now = datetime.now(timezone.utc)
            age_hours = (now - last_updated).total_seconds() / 3600
            if age_hours <= max_age_hours:
                return {"label": "fresh", "color": "emerald"}
            elif age_hours <= max_age_hours * 3:
                return {"label": "stale", "color": "amber"}
            else:
                return {"label": "critical", "color": "red"}

        # Scan actual data directories
        prices_dir = DATA_ROOT / "structured" / "prices"
        financials_dir = DATA_ROOT / "structured" / "financials"
        earnings_dir = DATA_ROOT / "structured" / "earnings"
        news_dir = DATA_ROOT / "unstructured" / "news"
        reddit_dir = DATA_ROOT / "unstructured" / "reddit"
        x_dir = DATA_ROOT / "unstructured" / "x"
        flow_dir = DATA_ROOT / "structured" / "flow_data"

        # Max age thresholds (hours)
        thresholds = {
            "prices": 24,          # 1 day
            "financials": 2160,    # 90 days
            "earnings": 2160,      # 90 days
            "news": 12,            # 12 hours
            "reddit_sentiment": 6, # 6 hours
            "x_sentiment": 6,      # 6 hours
            "institutional_flow": 2160,  # 90 days
        }

        data_categories = {
            "prices": {
                "last_updated": _newest_file_time(prices_dir, "*_prices.csv"),
                "label": "Prices",
                "frequency": "Daily",
            },
            "financials": {
                "last_updated": _newest_file_time(financials_dir, "*.json"),
                "label": "Financials",
                "frequency": "Quarterly",
            },
            "earnings": {
                "last_updated": _newest_file_time(earnings_dir, "*.json"),
                "label": "Earnings",
                "frequency": "Quarterly",
            },
            "news": {
                "last_updated": _newest_file_time(news_dir, "*_news_*.json"),
                "label": "News",
                "frequency": "Daily",
            },
            "reddit_sentiment": {
                "last_updated": _newest_file_time(reddit_dir, "*_reddit_posts_*.json"),
                "label": "Reddit",
                "frequency": "Weekly",
            },
            "x_sentiment": {
                "last_updated": _newest_file_time(x_dir, "*_x_posts_*.json"),
                "label": "X / Twitter",
                "frequency": "Weekly",
            },
            "institutional_flow": {
                "last_updated": _newest_file_time(flow_dir, "*_flow_*.json"),
                "label": "Flow Data",
                "frequency": "Quarterly",
            },
        }

        status = {}
        for key, info in data_categories.items():
            ts = info["last_updated"]
            freshness = _freshness_status(ts, thresholds[key])
            status[key] = {
                "last_updated": ts.isoformat() if ts else None,
                "label": info["label"],
                "frequency": info["frequency"],
                "freshness": freshness["label"],
                "freshness_color": freshness["color"],
            }

        # Also include schedule info for compatibility
        for data_type, schedule in UPDATE_SCHEDULES.items():
            if data_type not in status:
                status[data_type] = {
                    "last_updated": None,
                    "label": data_type.replace("_", " ").title(),
                    "frequency": schedule["frequency"],
                    "description": schedule["description"],
                    "freshness": "unavailable",
                    "freshness_color": "slate",
                }

        return {"status": "success", "data": status}
    except Exception as exc:
        logger.error(f"Error getting data status: {exc}")
        return {"status": "error", "message": str(exc)}


@app.get("/api/token-usage")
async def get_token_usage():
    """Return the latest token usage data."""
    try:
        token_file, plot_file = await _ensure_token_usage_assets()
        with token_file.open("r") as f:
            token_data = json.load(f)

        token_data["_has_plot"] = bool(plot_file)

        return {
            "status": "success",
            "data": token_data
        }
    except Exception as exc:
        logger.error(f"Error loading token usage data: {exc}")
        return {"status": "error", "message": f"Failed to fetch token usage: {exc}"}


@app.get("/api/token-usage-plot")
async def get_token_usage_plot():
    """Return the token usage plot image."""
    try:
        from fastapi.responses import FileResponse

        _, plot_file = await _ensure_token_usage_assets()
        if not plot_file:
            raise HTTPException(status_code=503, detail="Token usage chart unavailable in this deployment.")
        return FileResponse(
            plot_file,
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300"}
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error(f"Error loading token usage plot: {exc}")
        return {"status": "error", "message": f"Failed to fetch plot: {exc}"}


@app.get("/api/flow-plot/{ticker}")
async def get_flow_plot(ticker: str):
    """Return the generated flow time-series plot for a ticker."""
    try:
        from fastapi.responses import FileResponse

        ticker = ticker.upper()
        flow_dir = DATA_ROOT / "structured" / "flow_data"
        flow_dir.mkdir(parents=True, exist_ok=True)

        plot_files = sorted(flow_dir.glob(f"{ticker}_flow_plot_*.png"))
        if not plot_files:
            return {"status": "error", "message": f"No flow plot found for {ticker}"}

        return FileResponse(
            plot_files[-1],
            media_type="image/png",
            headers={"Cache-Control": "public, max-age=300"},
        )
    except Exception as exc:
        logger.error(f"Error loading flow plot for {ticker}: {exc}")
        return {"status": "error", "message": f"Failed to fetch flow plot: {exc}"}


@app.get("/api/flow-summary/{ticker}")
async def flow_summary_endpoint(ticker: str):
    """Return a language-model generated summary of the latest flow data."""
    try:
        snapshot = _load_flow_snapshot(ticker, "combined")
    except FileNotFoundError:
        return {"status": "error", "message": f"No flow data found for {ticker.upper()}"}
    except Exception as exc:
        logger.error("Failed to load flow data for summary: %s", exc)
        return {"status": "error", "message": f"Failed to build summary for {ticker.upper()}"}

    summary = _generate_flow_summary(ticker.upper(), snapshot.get("data", {}))
    return {"status": "success", "summary": summary}

# --- Comparison Routes ---

@app.get("/comparison", response_class=HTMLResponse)
async def get_comparison(request: Request):
    """Serves the comparison tool page."""
    return templates.TemplateResponse("comparison.html", {"request": request})

class ComparisonRequest(BaseModel):
    tickers: list[str]

@app.post("/api/compare")
async def compare_stocks(request: ComparisonRequest):
    """
    Compares a list of tickers using momentum and fundamental data.
    Returns a list of comparison results suitable for the frontend.
    Optimized with parallel score computation.
    """
    try:
        import yfinance as yf
        import pandas as pd
        import numpy as np
        from app.scoring.engine import compute_company_scores

        tickers = [t.upper() for t in request.tickers]
        
        # Fetch price data for all tickers in parallel
        data = yf.download(tickers, period="2y", group_by='ticker', progress=False)
        
        # Pre-compute scores in parallel for faster response
        async def compute_score_async(ticker):
            """Compute score for a single ticker."""
            loop = asyncio.get_event_loop()
            try:
                scores = await loop.run_in_executor(None, compute_company_scores, ticker)
                if scores and scores.get('overall'):
                    return ticker, float(scores.get('overall', {}).get('score', np.nan))
            except Exception:
                pass
            return ticker, np.nan
        
        # Compute all scores in parallel
        score_tasks = [compute_score_async(ticker) for ticker in tickers]
        score_results = await asyncio.gather(*score_tasks)
        score_dict = {ticker: score for ticker, score in score_results}
        
        results = []

        for ticker in tickers:
            try:
                # Handle yfinance data structure
                if len(tickers) > 1:
                    if ticker in data.columns.levels[0]:
                        df = data[ticker].copy()
                    else:
                        continue
                else:
                    df = data.copy()
                
                if df.empty: continue
                
                closes = df['Close'].fillna(method='ffill')
                if closes.empty: continue
                
                current_price = float(closes.iloc[-1])
                
                # Momentum Metrics
                ma50 = float(closes.rolling(window=50).mean().iloc[-1])
                ma200 = float(closes.rolling(window=200).mean().iloc[-1])
                r6m = float((current_price / closes.iloc[-126] - 1) if len(closes) > 126 else 0)
                r12m = float((current_price / closes.iloc[-252] - 1) if len(closes) > 252 else 0)
                
                # RSI
                delta = closes.diff()
                gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
                loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
                rs = gain / loss
                rsi = float(100 - (100 / (1 + rs)).iloc[-1])
                
                # Deep Alpha Score (already computed in parallel above)
                da_score = score_dict.get(ticker, np.nan)
                
                # Recommendation Logic
                points = 0
                reasons = []
                
                # Trend Analysis
                if current_price > ma50:
                    if ma50 > ma200: 
                        points += 2
                        reasons.append("Strong Uptrend (Price > MA50 > MA200)")
                    else:
                        points += 1
                        reasons.append("Moderate Uptrend (Price > MA50)")
                elif current_price < ma50 and ma50 < ma200:
                    reasons.append("Downtrend (Price < MA50 < MA200)")
                
                # Momentum Strength
                if r6m > 0.20: 
                    points += 1
                    reasons.append(f"High 6M Velocity (+{r6m*100:.0f}%)")
                if r12m > 0.30: 
                    points += 1
                    
                # RSI Context
                if rsi > 70:
                    reasons.append("Overbought (RSI > 70)")
                elif rsi < 30:
                    points += 1 # Potential mean reversion
                    reasons.append("Oversold (RSI < 30)")
                elif 50 <= rsi <= 70:
                    points += 1
                    reasons.append("Bullish RSI Range")
                
                # Fundamental Impact (Score) - affects points but not text description
                if pd.notnull(da_score) and da_score >= 6.5: 
                    points += 2
                elif pd.notnull(da_score) and da_score < 4.0: 
                    points -= 2
                
                action = "BUY" if points >= 5 else "HOLD" if points >= 3 else "SELL"
                
                results.append({
                    'ticker': ticker,
                    'action': action,
                    'price': f"{current_price:.2f}",
                    'trend': "Bullish" if current_price > ma50 > ma200 else "Mixed/Bearish",
                    'rsi': f"{rsi:.1f}",
                    'mom_6m': f"{r6m * 100:.1f}%",
                    'mom_12m': f"{r12m * 100:.1f}%",
                    'da_score': f"{da_score:.1f}" if pd.notnull(da_score) else "N/A",
                    'reasoning': "; ".join(reasons) if reasons else "Neutral technicals"
                })
                
            except Exception as e:
                print(f"Error processing {ticker}: {e}")
                
        return {"status": "success", "results": results}

    except Exception as e:
        return {"status": "error", "message": str(e)}


async def _extract_ticker_and_intent_with_openai(question: str) -> tuple[str | None, str]:
    """
    Fallback to OpenAI API when Gemini quota is exceeded.
    Returns (ticker, intent) tuple.
    """
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            logger.debug("No OPENAI_API_KEY found for fallback")
            return None, "general"
        
        import openai
        client = openai.OpenAI(api_key=api_key)
        
        extraction_prompt = f"""Extract ticker and intent from this question. Return ONLY JSON:

Question: "{question}"

JSON format:
{{
    "ticker": "NVDA" or null,
    "intent": "momentum" | "sentiment" | "news" | "financials" | "investment_recommendation" | "general"
}}

Only extract actual stock tickers (2-5 uppercase letters). Return null if none found."""
        
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: client.chat.completions.create(
                model="gpt-4o-mini",  # Using mini for cost efficiency
                messages=[{"role": "user", "content": extraction_prompt}],
                temperature=0.3,
                max_tokens=200
            )
        )
        
        response_text = response.choices[0].message.content.strip()
        
        # Extract JSON
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        import json
        analysis = json.loads(response_text)
        ticker = analysis.get("ticker")
        intent = analysis.get("intent", "general")
        
    except ImportError:
        logger.error("openai module not installed. Install with: pip install openai")
        return None, "general"
    except Exception as e:
        logger.error(f"OpenAI fallback extraction failed: {e}")
        return None, "general"

    # Validate ticker is supported; if not, return an unsupported marker
    if ticker:
        supported_tickers = load_supported_tickers()
        if ticker not in supported_tickers:
            return f"UNSUPPORTED:{ticker}", intent
        
        logger.info(f"OpenAI fallback extracted ticker: {ticker}, intent: {intent}")
        return ticker, intent


async def _extract_ticker_and_intent_with_gemini(question: str, model_name: str) -> tuple[str | None, str]:
    """
    Helper function to extract ticker and intent using a specific Gemini model.
    Returns (ticker, intent) tuple.
    """
    ticker = None
    intent = "general"
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return None, "general"
    
    import google.generativeai as genai
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    
    extraction_prompt = f"""Extract ticker and intent from this question. Return ONLY JSON:

Question: "{question}"

JSON format:
{{
    "ticker": "NVDA" or null,
    "intent": "momentum" | "sentiment" | "news" | "financials" | "investment_recommendation" | "general"
}}

Only extract actual stock tickers (2-5 uppercase letters). Return null if none found."""
    
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(None, model.generate_content, extraction_prompt)
    response_text = response.text.strip()
    
    # Extract JSON
    if "```json" in response_text:
        response_text = response_text.split("```json")[1].split("```")[0].strip()
    elif "```" in response_text:
        response_text = response_text.split("```")[1].split("```")[0].strip()
    
    import json
    analysis = json.loads(response_text)
    ticker = analysis.get("ticker")
    intent = analysis.get("intent", "general")
    
    # Validate ticker is supported; if not, return an unsupported marker
    if ticker:
        supported_tickers = load_supported_tickers()
        if ticker not in supported_tickers:
            return f"UNSUPPORTED:{ticker}", intent
    
    return ticker, intent


async def _extract_ticker_and_intent_with_llm(question: str) -> tuple[str | None, str]:
    """
    Shared function to extract ticker and intent using Gemini LLM.
    Uses tiered fallback: gemini-2.0-flash -> gemini-1.5-flash -> OpenAI
    Returns (ticker, intent) tuple.
    This avoids duplicate LLM calls when intelligent chat falls back to fallback handler.
    """
    # Tier 1: Try gemini-2.0-flash (primary model)
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            logger.debug("No GEMINI_API_KEY found, trying OpenAI fallback")
            return await _extract_ticker_and_intent_with_openai(question)
        
        import google.generativeai as genai
        result = await _extract_ticker_and_intent_with_gemini(question, 'gemini-2.0-flash')
        if result[0] is not None:  # Successfully extracted ticker
            return result
        
    except ImportError:
        logger.error("google.generativeai module not installed. Install with: pip install google-generativeai")
        return await _extract_ticker_and_intent_with_openai(question)
    except Exception as e:
        # Check if it's a quota/rate limit error
        error_str = str(e)
        is_quota_error = "429" in error_str or "quota" in error_str.lower() or "rate limit" in error_str.lower()
        
        if is_quota_error:
            logger.warning(f"Gemini 2.0-flash quota exceeded, trying gemini-1.5-flash (lower tier): {e}")
            # Tier 2: Try gemini-1.5-flash (lower tier, potentially higher quota)
            try:
                result = await _extract_ticker_and_intent_with_gemini(question, 'gemini-1.5-flash')
                if result[0] is not None:  # Successfully extracted ticker
                    logger.info("Successfully used gemini-1.5-flash fallback")
                    return result
            except Exception as e2:
                error_str2 = str(e2)
                is_quota_error2 = "429" in error_str2 or "quota" in error_str2.lower() or "rate limit" in error_str2.lower()
                if is_quota_error2:
                    logger.warning(f"Gemini 1.5-flash also quota exceeded, trying OpenAI fallback: {e2}")
                else:
                    logger.error(f"Gemini 1.5-flash extraction failed: {e2}")
            
            # Tier 3: Fall back to OpenAI
            return await _extract_ticker_and_intent_with_openai(question)
        else:
            logger.error(f"Gemini 2.0-flash LLM extraction failed: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            # Try OpenAI as fallback
            return await _extract_ticker_and_intent_with_openai(question)
    
    # If we get here, gemini-2.0-flash didn't extract a ticker, try fallbacks
    logger.warning("Gemini 2.0-flash didn't extract ticker, trying gemini-1.5-flash")
    try:
        result = await _extract_ticker_and_intent_with_gemini(question, 'gemini-1.5-flash')
        if result[0] is not None:
            return result
    except Exception:
        pass
    
    # Final fallback to OpenAI
    try:
        result = await _extract_ticker_and_intent_with_openai(question)
        if result[0] is not None:
            return result
    except Exception as e:
        logger.error(f"OpenAI extraction also failed: {e}")
    
    # Last resort: simple regex pattern matching for ticker extraction
    import re
    ticker_pattern = r'\b([A-Z]{2,5})\b'
    potential_tickers = re.findall(ticker_pattern, question.upper())
    supported_tickers = load_supported_tickers()
    
    for ticker in potential_tickers:
        if ticker in supported_tickers:
            # Try to infer intent from question
            intent = "general"
            question_lower = question.lower()
            if any(word in question_lower for word in ['buy', 'sell', 'should', 'shall', 'recommend']):
                intent = "investment_recommendation"
            elif any(word in question_lower for word in ['momentum', 'trend', 'going up']):
                intent = "momentum"
            elif any(word in question_lower for word in ['sentiment', 'feeling']):
                intent = "sentiment"
            elif any(word in question_lower for word in ['news', 'latest']):
                intent = "news"
            
            logger.info(f"Regex fallback extracted ticker: {ticker}, intent: {intent}")
            return ticker, intent
    
    # If we saw any potential tickers but none supported, surface that
    if potential_tickers:
        return f"UNSUPPORTED:{potential_tickers[0]}", "general"
    
    # No ticker found
    return None, "general"


async def _handle_intelligent_chat(question: str, include_reasoning: bool = False) -> dict:
    """
    Intelligent chatbot using google.generativeai directly.
    Uses Gemini to understand intent, route to tools, and format responses.
    """
    try:
        import google.generativeai as genai

        # Configure Gemini
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            # Fall back to simple handler if no API key
            return await _handle_chat_fallback(question, include_reasoning)

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        # Step 1: Use shared LLM extraction function (avoid duplicate calls)
        ticker, intent = await _extract_ticker_and_intent_with_llm(question)
        
        # Step 1b: Infer data_needed from intent (no need for additional LLM call)
        data_needed = []
        if intent == "momentum":
            data_needed = ["company_data"]
        elif intent == "sentiment":
            data_needed = ["reddit", "news"]
        elif intent == "news":
            data_needed = ["news"]
        elif intent in ["financials", "investment_recommendation"]:
            data_needed = ["company_data", "news"]

        # Validate ticker is supported
        if ticker:
            supported_tickers = load_supported_tickers()
            if ticker not in supported_tickers:
                ticker = None

        # Step 2: Get data based on intent (use executors for blocking calls)
        tool_data = {}

        if ticker:
            # Get company data for most queries
            if intent in ["investment_recommendation", "financials", "general"]:
                try:
                    from app.agents.agents import query_company_data
                    tool_data["company_data"] = await loop.run_in_executor(None, query_company_data, ticker, "all")
                except Exception as e:
                    logger.debug(f"Failed to get company data for {ticker}: {e}")

            # Get momentum data
            if intent == "momentum":
                try:
                    tool_data["momentum"] = await loop.run_in_executor(None, compute_company_scores, ticker)
                except Exception as e:
                    logger.debug(f"Failed to get momentum data for {ticker}: {e}")

            # Get news
            if intent == "news" or "news" in data_needed:
                try:
                    from app.agents.agents import search_latest_news
                    tool_data["news"] = await loop.run_in_executor(None, search_latest_news, ticker)
                except Exception as e:
                    logger.debug(f"Failed to get news for {ticker}: {e}")

            # Get sentiment
            if intent == "sentiment" or "reddit" in data_needed:
                try:
                    from app.agents.agents import query_reddit_sentiment
                    tool_data["reddit"] = await loop.run_in_executor(None, query_reddit_sentiment, ticker, 10)
                except Exception as e:
                    logger.debug(f"Failed to get sentiment for {ticker}: {e}")

        # Step 3: Use Gemini to format a natural response
        if not tool_data:
            return await _handle_chat_fallback(question, include_reasoning, ticker=ticker, intent=intent)

        format_prompt = f"""You are a financial analyst assistant. Based on the user's question and the data provided, give a helpful, natural answer.

User Question: "{question}"

Data Available:
{json.dumps(tool_data, indent=2, default=str)[:3000]}

Provide a clear, concise answer focusing on what the user asked. If they asked for investment recommendations, provide a structured recommendation with rating, action, reasoning, and risks. Keep the response under 300 words."""

        # Run Gemini API call in executor to avoid blocking
        final_response = await loop.run_in_executor(None, model.generate_content, format_prompt)
        answer = final_response.text.strip()

        return {
            'answer': answer,
            'status': 'success',
            'intent': intent if include_reasoning else None,
            'ticker': ticker if include_reasoning else None
        }

    except Exception as e:
        logger.error(f"Intelligent chat failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        # Fall back to simple handler (it will extract ticker/intent itself since we don't have them)
        return await _handle_chat_fallback(question, include_reasoning)


@app.post("/chat")
async def chat(request: QueryRequest, http_request: Request):
    """
    Intelligent chatbot powered by Financial_Root_Agent (ADK) or Gemini fallback.
    Uses the ADK agent system when available, falls back to direct Gemini when not.
    """
    # Basic validation
    if not request.question or len(request.question.strip()) < 5:
        return {
            'answer': "Invalid query: Question seems too short to be meaningful",
            'status': 'validation_error'
        }

    # Try to use ADK root agent first (preferred architecture)
    if hasattr(http_request.app.state, 'agent_caller') and http_request.app.state.agent_caller:
        logger.info(f"Using root agent for query: {request.question[:50]}...")
        try:
            result = await http_request.app.state.agent_caller.call(
                request.question, 
                include_reasoning=request.include_reasoning
            )
            logger.info(f"Root agent returned status: {result.get('status')}")
            return result
        except Exception as e:
            logger.error(f"Root agent chat failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fall through to fallback handler
    else:
        logger.warning("Root agent not available, using fallback handler")

    # Fallback: Use direct Gemini chatbot (when ADK not available)
    try:
        return await _handle_chat_fallback(request.question, request.include_reasoning)
    except Exception as e:
        logger.error(f"Chat fallback failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'answer': f"I encountered an error processing your question. Please try rephrasing it or ask about a specific ticker (e.g., 'Should I buy MU?' or 'What is NVDA's momentum?').",
            'status': 'error',
            'error': str(e)
        }


def _format_chat_response(
    tldr: str,
    key_points: list[str] | None = None,
    details: list[str] | None = None,
    followups: list[str] | None = None,
) -> str:
    """
    Helper to keep answers concise and structured:
    - TL;DR first
    - Key points in bullets
    - Optional details and quick follow-ups
    """
    key_points = key_points or []
    details = details or []
    followups = followups or []

    parts: list[str] = [f"TL;DR: {tldr}"]

    if key_points:
        parts.append("\nKey points:")
        parts.extend([f"- {p}" for p in key_points if p])

    if details:
        parts.append("\nDetails:")
        parts.extend([f"- {d}" for d in details if d])

    if followups:
        parts.append("\nQuick follow-up (optional):")
        parts.extend([f"- {f}" for f in followups if f])

    return "\n".join(parts)


async def _handle_chat_fallback(question: str, include_reasoning: bool = False, ticker: str | None = None, intent: str | None = None) -> dict:
    """
    Fallback chatbot that uses tools directly without ADK.
    Uses LLM to extract ticker and intent if not already provided (to avoid duplicate calls).
    """
    question_lower = question.lower().strip()
    
    # Only extract if not already provided (avoids duplicate LLM calls)
    if ticker is None or intent is None:
        logger.info(f"Extracting ticker and intent from: {question[:50]}...")
        ticker, intent = await _extract_ticker_and_intent_with_llm(question)
        logger.info(f"Extracted ticker: {ticker}, intent: {intent}")
    if intent is None:
        intent = "general"

    # Handle unsupported tickers (marked as UNSUPPORTED:<TICKER>)
    if ticker and isinstance(ticker, str) and ticker.startswith("UNSUPPORTED:"):
        unsupported = ticker.split("UNSUPPORTED:", 1)[1]
        supported = ", ".join(sorted(load_supported_tickers())[:20])
        return {
            'answer': f"Sorry, {unsupported} is outside our current coverage. Supported tickers include: {supported}. Please try one of those.",
            'status': 'unsupported_ticker'
        }
    
    logger.info(f"Processing fallback chat - ticker: {ticker}, intent: {intent}")
    
    try:
        loop = asyncio.get_event_loop()
        
        # Handle momentum questions (using LLM-extracted intent or keyword fallback)
        if intent == "momentum" or any(word in question_lower for word in ['momentum', 'going up', 'trend', 'direction', 'price movement']):
            if ticker:
                try:
                    from app.scoring import compute_company_scores
                    data = await loop.run_in_executor(None, compute_company_scores, ticker)
                    technical_score = data.get("scores", {}).get("technical", {}).get("score", 0)
                    recommendation = data.get("recommendation", {}).get("rating", "HOLD")

                    momentum_view = "strong positive" if technical_score >= 7 else "balanced/mixed" if technical_score >= 5 else "weak/negative"
                    action_hint = "Consider adding or accumulating on dips" if technical_score >= 7 else "Monitor for a clearer setup" if technical_score >= 5 else "Caution; wait for trend to improve"
                    tldr = f"{ticker} momentum is {momentum_view} (technical {technical_score:.1f}/10; rec: {recommendation})"
                    key_points = [
                        f"Trend read: {momentum_view} based on our technical composite",
                        f"Recommendation: {recommendation}; action: {action_hint}",
                        "Drivers: price trend, volume, and volatility signals in the technical pillar",
                    ]
                    followups = ["Time horizon and risk tolerance? (changes how aggressive to be)"]
                    answer = _format_chat_response(tldr, key_points, followups=followups)
                    return {'answer': answer, 'status': 'success'}
                except Exception as e:
                    logger.error(f"Error getting momentum for {ticker}: {e}")
        
        # Handle sentiment questions (using LLM-extracted intent or keyword fallback)
        if intent == "sentiment" or any(word in question_lower for word in ['sentiment', 'feeling', 'mood', 'outlook', 'perception']):
            if ticker:
                try:
                    # Actually call Reddit and Twitter agents for sentiment
                    from app.agents.agents import query_reddit_sentiment, query_twitter_data
                    
                    reddit_data = None
                    twitter_data = None
                    
                    # Fetch Reddit sentiment
                    try:
                        reddit_data = await loop.run_in_executor(None, query_reddit_sentiment, ticker, 20)
                    except Exception as e:
                        logger.debug(f"Reddit sentiment fetch failed for {ticker}: {e}")
                    
                    # Fetch Twitter sentiment
                    try:
                        twitter_data = await loop.run_in_executor(None, query_twitter_data, ticker)
                    except Exception as e:
                        logger.debug(f"Twitter sentiment fetch failed for {ticker}: {e}")
                    
                    # Also get overall sentiment score
                    from app.scoring import compute_company_scores
                    data = await loop.run_in_executor(None, compute_company_scores, ticker)
                    sentiment_score = data.get("scores", {}).get("sentiment", {}).get("score", 0)
                    overall_score = data.get("overall", {}).get("score", 0)
                    
                    reddit_line = None
                    if reddit_data and not reddit_data.get("error"):
                        reddit_sentiment = reddit_data.get("sentiment_summary", "")
                        post_count = reddit_data.get("total_posts", 0)
                        if post_count > 0:
                            reddit_line = f"Reddit: {reddit_sentiment} ({post_count} posts)"

                    twitter_line = None
                    if twitter_data and not twitter_data.get("error"):
                        twitter_sentiment = twitter_data.get("sentiment_summary", "")
                        if twitter_sentiment:
                            twitter_line = f"Twitter/X: {twitter_sentiment}"

                    if sentiment_score >= 7:
                        sentiment_desc = "very positive"
                    elif sentiment_score >= 5:
                        sentiment_desc = "moderately positive"
                    elif sentiment_score >= 3:
                        sentiment_desc = "neutral to slightly negative"
                    else:
                        sentiment_desc = "negative"

                    tldr = f"Sentiment for {ticker} is {sentiment_desc} ({sentiment_score:.1f}/10); overall score {overall_score:.1f}/10"
                    key_points = [
                        line for line in [reddit_line, twitter_line] if line
                    ]
                    key_points.append(f"Composite sentiment score: {sentiment_score:.1f}/10; Deep Alpha overall: {overall_score:.1f}/10")
                    followups = ["Anything specific you want to probe (news, risks, or time horizon)?"]
                    answer = _format_chat_response(tldr, key_points, followups=followups)
                    return {'answer': answer, 'status': 'success'}
                except Exception as e:
                    logger.error(f"Error getting sentiment for {ticker}: {e}")
                    # Fallback to basic answer
                    try:
                        from app.scoring import compute_company_scores
                        data = await loop.run_in_executor(None, compute_company_scores, ticker)
                        sentiment_score = data.get("scores", {}).get("sentiment", {}).get("score", 0)
                        tldr = f"Sentiment for {ticker}: {sentiment_score:.1f}/10 (composite from news/market signals)"
                        key_points = ["Data-driven sentiment composite; ask if you want news drivers"]
                        answer = _format_chat_response(tldr, key_points)
                        return {'answer': answer, 'status': 'success'}
                    except:
                        pass
        
        # Handle investment recommendation questions (buy/sell/hold)
        if intent == "investment_recommendation" or any(word in question_lower for word in ['buy', 'sell', 'should i', 'shall i', 'recommend', 'investment']):
            if ticker:
                try:
                    from app.scoring import compute_company_scores
                    data = await loop.run_in_executor(None, compute_company_scores, ticker)
                    
                    overall_score = data.get("overall", {}).get("score", 0)
                    rec_data = data.get("recommendation", {})
                    recommendation = rec_data.get("rating", "HOLD")
                    confidence = rec_data.get("confidence", "Medium")
                    action = rec_data.get("action", "Monitor")
                    timing = rec_data.get("timing", "Monitor for developments")
                    
                    scores_data = data.get("scores", {})
                    business_score = scores_data.get("business", {}).get("score", 0)
                    financial_score = scores_data.get("financial", {}).get("score", 0)
                    sentiment_score = scores_data.get("sentiment", {}).get("score", 0)
                    technical_score = scores_data.get("technical", {}).get("score", 0)
                    leadership_score = scores_data.get("leadership", {}).get("score", 0)
                    
                    company_name = data.get("quick_facts", {}).get("name", ticker)
                    info = data.get("company", {}).get("info", {})
                    forward_pe = info.get("forwardPE") or info.get("trailingPE") or 0
                    
                    strengths = rec_data.get("strengths", [])
                    weaknesses = rec_data.get("weaknesses", [])
                    risks = rec_data.get("risks", [])
                    
                    pillar_summaries = [
                        f"Business {business_score:.1f}/10: {scores_data.get('business', {}).get('summary', 'Business fundamentals assessment')}",
                        f"Financial {financial_score:.1f}/10: {scores_data.get('financial', {}).get('summary', 'Financial health assessment')}",
                        f"Sentiment {sentiment_score:.1f}/10: {scores_data.get('sentiment', {}).get('summary', 'Market sentiment assessment')}",
                        f"Technical {technical_score:.1f}/10: {scores_data.get('technical', {}).get('summary', 'Technical momentum assessment')}",
                        f"Leadership {leadership_score:.1f}/10: {scores_data.get('leadership', {}).get('summary', 'Leadership assessment')}",
                    ]
                    if forward_pe > 0:
                        pillar_summaries.append(f"Valuation: P/E ~{forward_pe:.1f}")
                    
                    # Bull case (based on strengths and positive factors)
                    bull_likelihood = min(90, max(30, (overall_score / 10) * 70 + 20))  # Convert score to likelihood
                    bull_assumptions = []
                    if business_score >= 7:
                        bull_assumptions.append("Strong business fundamentals continue")
                    if financial_score >= 7:
                        bull_assumptions.append("Financial health remains robust")
                    if technical_score >= 7:
                        bull_assumptions.append("Positive momentum persists")
                    if sentiment_score >= 7:
                        bull_assumptions.append("Market sentiment remains favorable")
                    if not bull_assumptions:
                        bull_assumptions = ["Current positive trends continue"]
                    
                    answer_parts.append(f"\n**Bull Case (Likelihood: {bull_likelihood:.0f}%)**\n")
                    if strengths:
                        answer_parts.append(f"- {', '.join(strengths[:3])}\n")
                    answer_parts.append(f"- Assumptions: {', '.join(bull_assumptions[:3])}\n")
                    answer_parts.append(f"- Likelihood: {bull_likelihood:.0f}% probability\n")
                    answer_parts.append(f"- Catalysts: Positive developments in business fundamentals, market sentiment, or technical momentum\n")
                    
                    # Bear case (based on risks and weaknesses)
                    bear_likelihood = min(70, max(20, (10 - overall_score) / 10 * 50 + 10))
                    bear_assumptions = []
                    if business_score <= 4:
                        bear_assumptions.append("Business fundamentals deteriorate")
                    if financial_score <= 4:
                        bear_assumptions.append("Financial stress increases")
                    if technical_score <= 4:
                        bear_assumptions.append("Negative momentum continues")
                    if sentiment_score <= 4:
                        bear_assumptions.append("Market sentiment turns negative")
                    if not bear_assumptions:
                        bear_assumptions = ["Negative factors materialize"]

                    tldr = f"{company_name} ({ticker}): {recommendation} (overall {overall_score:.1f}/10, confidence {confidence})"
                    key_points = pillar_summaries
                    details = [
                        f"Bull case ({bull_likelihood:.0f}%): {', '.join(strengths[:3]) or 'Upside if strengths persist'}; assumptions: {', '.join(bull_assumptions[:3])}",
                        f"Bear case ({bear_likelihood:.0f}%): {', '.join(risks[:3]) or 'Macro/competitive risks'}; assumptions: {', '.join(bear_assumptions[:3])}",
                        f"Action: {action}; Timing: {timing}",
                    ]
                    followups = ["What's your time horizon and risk tolerance?", "Any constraints (tax, concentration, liquidity)?"]
                    answer = _format_chat_response(tldr, key_points, details, followups)
                    return {'answer': answer, 'status': 'success'}
                except Exception as e:
                    logger.error(f"Error getting investment recommendation for {ticker}: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
        
        # Handle general company questions
        if ticker:
            try:
                from app.scoring import compute_company_scores
                data = await loop.run_in_executor(None, compute_company_scores, ticker)
                overall_score = data.get("overall", {}).get("score", 0)
                recommendation = data.get("recommendation", {}).get("rating", "HOLD")
                company_name = data.get("quick_facts", {}).get("name", ticker)

                tldr = f"{company_name} ({ticker}) score: {overall_score:.1f}/10; recommendation: {recommendation}"
                key_points = []
                if 'financial' in question_lower or 'health' in question_lower:
                    financial_score = data.get("scores", {}).get("financial", {}).get("score", 0)
                    key_points.append(f"Financial health: {financial_score:.1f}/10")
                risks = data.get("recommendation", {}).get("risks", [])
                if 'risk' in question_lower or 'concern' in question_lower:
                    if risks:
                        key_points.append(f"Key risks: {', '.join(risks[:3])}")
                followups = ["Want momentum, sentiment, or news next?", "Any portfolio constraints or time horizon?"]
                answer = _format_chat_response(tldr, key_points, followups=followups)
                return {'answer': answer, 'status': 'success'}
            except Exception as e:
                logger.error(f"Error getting company data for {ticker}: {e}")
        
        # Handle news questions (using LLM-extracted intent or keyword fallback)
        if intent == "news" or any(word in question_lower for word in ['news', 'latest', 'recent', 'happening']):
            if ticker:
                try:
                    payload = _load_cached_news(ticker)
                    if not payload:
                        payload = await loop.run_in_executor(None, fetch_realtime_news, ticker)
                    
                    articles = payload.get("articles", [])
                    if articles:
                        summary = payload.get("summary", {})
                        headline = summary.get("headline", "Latest news available")
                        tldr = f"Latest news for {ticker}: {headline}"
                        key_points = [
                            f"{len(articles)} recent articles reviewed",
                            f"Top headline: {articles[0].get('title', 'N/A')}" if articles else None,
                        ]
                        followups = ["Want a quick summary of the top 3 articles or sentiment impact?"]
                        answer = _format_chat_response(tldr, key_points, followups=followups)
                        return {'answer': answer, 'status': 'success'}
                    else:
                        tldr = f"No recent news found for {ticker}"
                        followups = ["Should I watch for updates and notify on notable moves?"]
                        answer = _format_chat_response(tldr, [], followups=followups)
                        return {'answer': answer, 'status': 'success'}
                except Exception as e:
                    logger.error(f"Error getting news for {ticker}: {e}")
        
        # Default response
        if ticker:
            return {
                'answer': _format_chat_response(
                    f"I can help with {ticker}.",
                    key_points=[
                        "Ask about momentum, sentiment, financials, risks, or news",
                        "I can summarize bull/bear cases and actions"
                    ],
                    followups=[
                        "Which angle matters most to you (momentum, fundamentals, or news)?",
                        "Any time horizon or risk tolerance to tailor the answer?"
                    ]
                ),
                'status': 'success'
            }
        else:
            return {
                'answer': _format_chat_response(
                    "I can help with stock questions once you share a ticker.",
                    key_points=[
                        "Coverage includes momentum, sentiment, financials, risks, and news",
                        "I can frame bull/bear cases and suggested actions"
                    ],
                    followups=[
                        "Which ticker and time horizon?",
                        "Any risk tolerance or portfolio constraint I should factor in?"
                    ]
                ),
                'status': 'success'
            }
    
    except Exception as e:
        logger.error(f"Error in chat fallback: {e}")
        return {
            'answer': f"I encountered an error processing your question. Please try rephrasing or contact support if the issue persists.",
            'status': 'error'
        }

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
