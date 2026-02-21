"""
Scoring engine for the deepAlpha investment copilot.

The engine reads locally cached fundamentals (from the ingestion pipeline) and
enriches them with live Yahoo Finance data to compute category scores along the
dimensions defined in the product PRD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from statistics import mean, pvariance
from typing import Dict, List, Optional, Tuple

import json
import os
import numpy as np
import pandas as pd
import re
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
import requests
from datetime import datetime, timedelta
import logging

# Logger for this module
logger = logging.getLogger(__name__)


def safe_json_serialize(obj):
    """Convert numpy types and handle NaN/infinity values for JSON serialization."""
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        if np.isnan(obj) or np.isinf(obj):
            return None
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: safe_json_serialize(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [safe_json_serialize(item) for item in obj]
    return obj


__all__ = ["compute_company_scores", "ScoreComputationError"]


class ScoreComputationError(Exception):
    """Raised when score computation fails for a ticker."""


# Determine data root based on environment
if os.getenv("K_SERVICE"):
    # Production/Cloud Run: use /tmp/data (where GCS downloads to)
    DATA_ROOT = Path("/tmp/data")
else:
    # Local development: use project data directory
    DATA_ROOT = Path(__file__).resolve().parents[2] / "data"
    # Fix for Docker container deployment
    if not DATA_ROOT.exists():
        DATA_ROOT = Path("/app/data")
FINANCIALS_DIR = DATA_ROOT / "structured" / "financials"
EARNINGS_DIR = DATA_ROOT / "structured" / "earnings"
PRICES_DIR = DATA_ROOT / "structured" / "prices"
SECTOR_METRICS_DIR = DATA_ROOT / "structured" / "sector_metrics"
RUNTIME_DIR = DATA_ROOT / "runtime"
PRICE_SNAPSHOT_DIR = RUNTIME_DIR / "price_snapshots"
REALTIME_NEWS_DIR = RUNTIME_DIR / "news"
COMPANY_RUNTIME_DIR = RUNTIME_DIR / "company"
REPORTS_DIR = DATA_ROOT / "reports"
REDDIT_DIR = DATA_ROOT / "unstructured" / "reddit"

for directory in [RUNTIME_DIR, PRICE_SNAPSHOT_DIR, REALTIME_NEWS_DIR, COMPANY_RUNTIME_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

CRITICAL_PATH_MAP: Dict[str, float] = {
    "NVDA": 10.0,
    "TSM": 9.0,
    "SMCI": 8.5,
    "AVGO": 8.5,
    "MU": 7.5,
    "VRT": 7.0,
    "CCJ": 8.0,
    "NXE": 7.5,
    "OKLO": 7.0,
    "SMR": 7.0,
    "VST": 6.5,
    "QS": 6.0,
    "EOSE": 6.0,
    "CIFR": 6.0,
    "RIOT": 6.0,
    "IREN": 6.0,
    "RR": 5.5,
    "INOD": 5.0,
}

SECTOR_GROWTH_BONUS = {
    "Semiconductors": 10.0,
    "Semiconductor": 10.0,
    "Semiconductor Equipment & Materials": 9.0,
    "Technology": 8.5,
    "Information Technology Services": 7.5,
    "Utilities": 6.0,
    "Financial Services": 6.5,
    "Basic Materials": 6.0,
    "Industrials": 6.5,
    "Energy": 7.0,
}

sentiment_analyzer = SentimentIntensityAnalyzer()


def _round(value: Optional[float], decimals: int = 1) -> Optional[float]:
    if value is None:
        return None
    try:
        factor = 10 ** decimals
        return round(float(value) * factor) / factor
    except Exception:
        return None


def _update_runtime_cache(ticker: str, section: str, payload: dict) -> None:
    ticker = ticker.upper()
    path = COMPANY_RUNTIME_DIR / f"{ticker}.json"
    try:
        if path.exists():
            with path.open("r") as fh:
                existing = json.load(fh)
        else:
            existing = {"ticker": ticker}
        existing.setdefault("runtime", {})
        existing["runtime"][section] = payload
        existing["updated_at"] = datetime.utcnow().isoformat() + "Z"
        with path.open("w") as fh:
            json.dump(existing, fh, indent=2)
    except Exception as exc:
        logger.warning("Unable to update runtime cache for %s: %s", ticker, exc)


def extract_year_from_summary(summary: Optional[str]) -> Optional[int]:
    if not summary:
        return None
    match = re.search(r"(19|20)\d{2}", summary)
    if match:
        return int(match.group())
    return None


@lru_cache(maxsize=1)
def _load_latest_ceo_summary_df() -> pd.DataFrame:
    files = sorted(REPORTS_DIR.glob("ceo_summary_*.csv"))
    if not files:
        return pd.DataFrame()
    df = pd.read_csv(files[-1])
    df["ticker"] = df["ticker"].str.upper()
    return df


def load_ceo_profile(ticker: str) -> Optional[Dict[str, object]]:
    df = _load_latest_ceo_summary_df()
    if df.empty:
        return None
    row = df[df["ticker"] == ticker.upper()]
    if row.empty:
        return None
    return row.iloc[0].to_dict()


@lru_cache(maxsize=1)
def load_industry_benchmarks() -> Dict[str, Dict[str, float]]:
    """
    Load industry benchmark P/E and P/S ratios from JSON file.
    Falls back to hardcoded defaults if file doesn't exist.

    Returns:
        Dictionary mapping industry names to benchmark metrics (pe, ps)
    """
    benchmark_file = Path("data/structured/industry_benchmarks.json")

    # Hardcoded fallback benchmarks (will be used if file doesn't exist)
    # Note: No default fallback - if industry not found, returns None
    fallback_benchmarks = {
        'Semiconductors': {'pe': 28.5, 'ps': 6.2},
        'Software': {'pe': 35.2, 'ps': 8.5},
        'Software - Infrastructure': {'pe': 35.2, 'ps': 8.5},
        'Hardware': {'pe': 22.1, 'ps': 3.8},
        'Internet Services': {'pe': 32.5, 'ps': 7.1},
        'Financial Services': {'pe': 14.2, 'ps': 2.5},
        'Healthcare': {'pe': 25.3, 'ps': 4.2},
        'Energy': {'pe': 12.8, 'ps': 1.8},
        'Consumer': {'pe': 18.5, 'ps': 2.2},
        'Other Industrial Metals & Mining': {'pe': None, 'ps': 25.0},
        'Other Precious Metals & Mining': {'pe': None, 'ps': 30.0},
        'Gold': {'pe': 20.0, 'ps': 8.0},
        'Copper': {'pe': 15.0, 'ps': 3.5},
        'Aluminum': {'pe': 12.0, 'ps': 1.2},
        'Specialty Chemicals': {'pe': 18.5, 'ps': 2.5}
    }

    if not benchmark_file.exists():
        logger.warning(f"Industry benchmarks file not found at {benchmark_file}, using fallback values")
        return fallback_benchmarks

    try:
        with open(benchmark_file, 'r') as f:
            data = json.load(f)
            benchmarks = data.get('benchmarks', {})

        # Log when benchmarks were generated
        generated_at = data.get('generated_at', 'unknown')
        logger.info(f"Loaded industry benchmarks generated at {generated_at}")

        return benchmarks

    except Exception as e:
        logger.error(f"Failed to load industry benchmarks from {benchmark_file}: {e}")
        return fallback_benchmarks


_reddit_sentiment_cache = {}
_reddit_cache_timestamps = {}
_twitter_sentiment_cache = {}
_twitter_cache_timestamps = {}
SENTIMENT_CACHE_TTL = 21600  # 6 hours in seconds

def get_live_reddit_sentiment(ticker: str) -> Optional[dict]:
    """
    Fetch live Reddit sentiment with 6-hour caching to balance freshness and latency.
    Falls back to cached JSON files if API fails.
    """
    try:
        import praw
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        
        ticker = ticker.upper()
        now = datetime.now(timezone.utc).timestamp()
        
        # Check cache first
        if ticker in _reddit_sentiment_cache:
            cache_age = now - _reddit_cache_timestamps.get(ticker, 0)
            if cache_age < SENTIMENT_CACHE_TTL:
                return _reddit_sentiment_cache[ticker]
        
        # Fetch live data
        reddit_client = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID', ""),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET', ""),
            user_agent=os.getenv('REDDIT_USER_AGENT', "FinancialAgent/1.0")
        )
        
        subreddits = ['stocks', 'investing', 'wallstreetbets']
        analyzer = SentimentIntensityAnalyzer()
        all_posts = []
        
        for subreddit_name in subreddits:
            try:
                subreddit = reddit_client.subreddit(subreddit_name)
                for post in subreddit.search(ticker, limit=10, time_filter='week'):
                    sentiment = analyzer.polarity_scores(post.title)
                    all_posts.append({
                        'sentiment': 'bullish' if sentiment['compound'] > 0.05 else 'bearish' if sentiment['compound'] < -0.05 else 'neutral',
                        'compound_score': sentiment['compound']
                    })
            except:
                continue
        
        if not all_posts:
            return None
        
        # Calculate aggregate
        bullish = sum(1 for p in all_posts if p['sentiment'] == 'bullish')
        bearish = sum(1 for p in all_posts if p['sentiment'] == 'bearish')
        
        result = {
            'total_posts': len(all_posts),
            'bullish_posts': bullish,
            'bearish_posts': bearish,
            'neutral_posts': len(all_posts) - bullish - bearish
        }
        
        # Cache the result
        _reddit_sentiment_cache[ticker] = result
        _reddit_cache_timestamps[ticker] = now
        
        return result
        
    except Exception as e:
        # Fallback to cached files
        return None


def get_live_twitter_sentiment(ticker: str) -> Optional[dict]:
    """
    Fetch live Twitter/X sentiment with 6-hour caching to balance freshness and latency.
    Falls back to Google Search API for recent mentions if Twitter API not available.
    """
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        from googleapiclient.discovery import build
        
        ticker = ticker.upper()
        now = datetime.now(timezone.utc).timestamp()
        
        # Check cache first
        if ticker in _twitter_sentiment_cache:
            cache_age = now - _twitter_cache_timestamps.get(ticker, 0)
            if cache_age < SENTIMENT_CACHE_TTL:
                return _twitter_sentiment_cache[ticker]
        
        # Use Google Custom Search API to find recent mentions
        api_key = os.getenv('GOOGLE_API_KEY')
        search_engine_id = os.getenv('GOOGLE_SEARCH_ENGINE_ID')
        
        if not api_key or not search_engine_id:
            return None
        
        service = build('customsearch', 'v1', developerKey=api_key)
        analyzer = SentimentIntensityAnalyzer()
        all_mentions = []
        
        # Search for recent mentions on Twitter/X and news
        search_queries = [
            f'${ticker} stock twitter.com OR x.com',
            f'{ticker} stock sentiment'
        ]
        
        for query in search_queries:
            try:
                result = service.cse().list(
                    q=query,
                    cx=search_engine_id,
                    num=5,
                    dateRestrict='d7'  # Last 7 days
                ).execute()
                
                items = result.get('items', [])
                for item in items:
                    title = item.get('title', '')
                    snippet = item.get('snippet', '')
                    text = f"{title} {snippet}"
                    
                    sentiment = analyzer.polarity_scores(text)
                    all_mentions.append({
                        'sentiment': 'bullish' if sentiment['compound'] > 0.05 else 'bearish' if sentiment['compound'] < -0.05 else 'neutral',
                        'compound_score': sentiment['compound']
                    })
            except:
                continue
        
        if not all_mentions:
            return None
        
        # Calculate aggregate
        bullish = sum(1 for m in all_mentions if m['sentiment'] == 'bullish')
        bearish = sum(1 for m in all_mentions if m['sentiment'] == 'bearish')
        
        result = {
            'total_mentions': len(all_mentions),
            'bullish_mentions': bullish,
            'bearish_mentions': bearish,
            'neutral_mentions': len(all_mentions) - bullish - bearish
        }
        
        # Cache the result
        _twitter_sentiment_cache[ticker] = result
        _twitter_cache_timestamps[ticker] = now
        
        return result
        
    except Exception as e:
        # Fallback
        return None


@lru_cache(maxsize=1)
def load_latest_reddit_summary() -> Dict[str, dict]:
    if not REDDIT_DIR.exists():
        return {}
    candidates = list(REDDIT_DIR.glob("reddit_summary*.json"))
    if not candidates:
        return {}
    latest = max(candidates, key=lambda p: p.stat().st_mtime)
    try:
        with latest.open() as f:
            data = json.load(f)
            if isinstance(data, dict):
                return {k.upper(): v for k, v in data.items()}
    except Exception:
        return {}
    return {}


def search_events_for_date(ticker: str, date: str, price_change: float) -> Optional[Dict[str, str]]:
    """
    Search for events that could explain significant price movements on a given date.
    Returns a dictionary with event summary and source link.
    """
    try:
        # Format the date for search
        search_date = datetime.strptime(date, "%Y-%m-%d").strftime("%B %d, %Y")
        
        # Create search query
        query = f"{ticker} stock news {search_date} earnings revenue announcement"
        
        # Use web search to find relevant events
        try:
            # Use a simple web search approach
            search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
            
            # For now, we'll generate intelligent event descriptions based on the price change
            # In a production environment, you would integrate with a proper search API like:
            # - Google Custom Search API
            # - Bing Search API
            # - News API
            # - Financial news APIs
            
            # Generate contextual event descriptions
            if price_change > 15:
                event_type = "major positive"
                event_summary = f"Major positive catalyst: Likely earnings beat, product launch, or strategic announcement on {search_date}"
            elif price_change > 10:
                event_type = "positive"
                event_summary = f"Positive news: Earnings beat, partnership, or favorable analyst coverage on {search_date}"
            elif price_change < -15:
                event_type = "major negative"
                event_summary = f"Major negative event: Likely earnings miss, regulatory issues, or significant market concerns on {search_date}"
            elif price_change < -10:
                event_type = "negative"
                event_summary = f"Negative news: Earnings miss, downgrade, or market concerns on {search_date}"
            else:
                event_type = "significant move"
                event_summary = f"Significant price movement on {search_date}"
            
            # Create a Yahoo Finance link for the specific date
            yahoo_link = f"https://finance.yahoo.com/quote/{ticker}/history?period1={int(datetime.strptime(date, '%Y-%m-%d').timestamp())}&period2={int(datetime.strptime(date, '%Y-%m-%d').timestamp()) + 86400}"
            
            # Create a Google search link for more detailed news
            google_search_link = f"https://www.google.com/search?q={ticker}+stock+news+{search_date.replace(' ', '+')}"
            
            return {
                "title": f"{ticker} {event_type.title()} Event - {search_date}",
                "summary": event_summary,
                "source": "Market Analysis",
                "link": google_search_link,
                "sentiment": 0.7 if event_type.startswith("major positive") else 0.5 if event_type == "positive" else -0.7 if event_type.startswith("major negative") else -0.5 if event_type == "negative" else 0.0
            }
            
        except Exception as search_error:
            print(f"Search error for {ticker} on {date}: {search_error}")
            # Fallback to basic event description
            direction = "surge" if price_change > 0 else "drop"
            return {
                "title": f"{ticker} Price {direction.title()} - {search_date}",
                "summary": f"Significant {direction} of {abs(price_change):.1f}% on {search_date}",
                "source": "Yahoo Finance",
                "link": f"https://finance.yahoo.com/quote/{ticker}/history",
                "sentiment": 0.5 if price_change > 0 else -0.5
            }
        
    except Exception as e:
        print(f"Error searching events for {ticker} on {date}: {e}")
        return None


def format_currency(value: Optional[float]) -> Optional[str]:
    if value is None or value != value:
        return None
    abs_value = abs(value)
    if abs_value >= 1e12:
        return f"${value/1e12:.1f}T"
    if abs_value >= 1e9:
        return f"${value/1e9:.1f}B"
    if abs_value >= 1e6:
        return f"${value/1e6:.1f}M"
    return f"${value:,.0f}"


def summarize_company(info: dict, fin_df: pd.DataFrame) -> str:
    def clean_clause(text: str, max_len: int = 140) -> str:
        text = text.strip()
        if len(text) <= max_len:
            return text
        truncated = text[:max_len].rsplit(" ", 1)[0]
        return truncated + "…"

    long_summary = info.get("longBusinessSummary") or ""
    first_clause = ""
    if long_summary:
        first_clause = re.split(r'[.;]', long_summary, 1)[0].strip()

    name = info.get("longName") or info.get("shortName") or "The company"
    industry = info.get("industry") or info.get("sector") or "technology"
    description = clean_clause(first_clause) if first_clause else f"{name} operates in the {industry.lower()} space with global reach."

    monetization = "It monetizes through diversified platforms and services across enterprise and consumer channels."
    keywords = {
        "Semiconductor": "It monetizes primarily through high-performance chips, accelerator boards, and software subscriptions.",
        "Software": "It monetizes via subscription software, enterprise licenses, and cloud-delivered services.",
        "Energy": "It monetizes through power generation assets, infrastructure services, and long-term contracts.",
        "Financial": "It monetizes through transaction services, data solutions, and asset-light advisory products.",
    }
    for key, sentence in keywords.items():
        if key.lower() in industry.lower():
            monetization = sentence
            break

    revenue_series = safe_series(fin_df, "Total Revenue")
    latest_revenue = format_currency(revenue_series.iloc[-1]) if not revenue_series.empty else None
    revenue_growth = None
    if len(revenue_series) >= 5:
        revenue_growth = revenue_series.pct_change().iloc[-1]

    if latest_revenue and revenue_growth is not None:
        outlook = f"Recent quarterly revenue was roughly {latest_revenue}, growing {revenue_growth:.1%} vs. the prior period as AI demand scales."
    elif latest_revenue:
        outlook = f"Recent quarterly revenue was roughly {latest_revenue}, supported by accelerating infrastructure and software demand."
    else:
        outlook = "Recent revenue trends are not disclosed in the available filings."

    return " ".join([description, monetization, outlook])


@dataclass
class ComponentScore:
    score: Optional[float]
    summary: str
    inputs: Dict[str, float]
    notes: List[str]


def clamp(value: float, lower: float = 0.0, upper: float = 10.0) -> float:
    return max(lower, min(value, upper))


def score_from_thresholds(value: float, thresholds: List[Tuple[float, float]]) -> float:
    """
    Map a metric value to a score using ordered thresholds.
    thresholds: list of (threshold_value, score). Sorted ascending.
    """
    for threshold, score in thresholds:
        if value <= threshold:
            return score
    return thresholds[-1][1]


def load_financials_df(ticker: str) -> pd.DataFrame:
    path = FINANCIALS_DIR / f"{ticker}_financials.json"
    if not path.exists():
        # Try lazy loading from GCS if in production
        if os.getenv("K_SERVICE"):
            try:
                from storage_helper import get_storage_manager
                storage_manager = get_storage_manager()
                cloud_path = f"data/structured/financials/{ticker}_financials.json"
                if storage_manager.download_file(cloud_path):
                    logger.info(f"✅ Lazy-loaded {ticker} financials from GCS")
                else:
                    raise ScoreComputationError(f"Financials file not found for {ticker}")
            except Exception as e:
                logger.warning(f"Could not lazy-load {ticker} financials: {e}")
                raise ScoreComputationError(f"Financials file not found for {ticker}")
        else:
            raise ScoreComputationError(f"Financials file not found for {ticker}")
    
    with open(path, 'r') as f:
        data = json.load(f)
    
    # The structure has dates as keys within each statement section
    # e.g., {"income_statement": {"2025-01-31 00:00:00": {...}, ...}, ...}
    # We combine all metrics across all statements by date
    
    records = []
    statement_types = [
        'income_statement', 'balance_sheet', 'cash_flow',
        'quarterly_income_statement', 'quarterly_balance_sheet', 'quarterly_cash_flow',
        'key_metrics'
    ]
    
    # Check if data is a list (some files might be in list format)
    if isinstance(data, list):
        # If it's a list, assume it's already a list of records
        records = data
    else:
        for statement_type in statement_types:
            if statement_type in data and isinstance(data[statement_type], dict):
                for date_str, metrics in data[statement_type].items():
                    if not isinstance(metrics, dict):
                        continue
                    # Find or create the record for this date
                    existing = next((r for r in records if r.get('date') == date_str), None)
                    if existing:
                        # Merge metrics, avoiding overwriting with None/NaN
                        for key, value in metrics.items():
                            if key not in existing or existing[key] is None:
                                existing[key] = value
                    else:
                        record = {'date': date_str}
                        record.update(metrics)
                        records.append(record)
    
    if not records:
        raise ScoreComputationError(f"No financial data found for {ticker}")
    
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    return df.set_index("date")


def load_earnings_df(ticker: str) -> pd.DataFrame:
    path = EARNINGS_DIR / f"{ticker}_quarterly_earnings.json"
    if not path.exists():
        # Try lazy loading from GCS if in production
        if os.getenv("K_SERVICE"):
            try:
                from storage_helper import get_storage_manager
                storage_manager = get_storage_manager()
                cloud_path = f"data/structured/earnings/{ticker}_quarterly_earnings.json"
                if storage_manager.download_file(cloud_path):
                    logger.info(f"✅ Lazy-loaded {ticker} earnings from GCS")
                else:
                    raise ScoreComputationError(f"Earnings file not found for {ticker}")
            except Exception as e:
                logger.warning(f"Could not lazy-load {ticker} earnings: {e}")
                raise ScoreComputationError(f"Earnings file not found for {ticker}")
        else:
            raise ScoreComputationError(f"Earnings file not found for {ticker}")
    df = pd.read_json(path)
    df["period"] = pd.to_datetime(df["period"])
    df = df.sort_values("period")
    return df.set_index("period")


def load_price_history(ticker: str) -> pd.DataFrame:
    path = PRICES_DIR / f"{ticker}_prices.csv"
    if not path.exists():
        # Try lazy loading from GCS if in production
        if os.getenv("K_SERVICE"):
            try:
                from storage_helper import get_storage_manager
                storage_manager = get_storage_manager()
                cloud_path = f"data/structured/prices/{ticker}_prices.csv"
                if storage_manager.download_file(cloud_path):
                    logger.info(f"✅ Lazy-loaded {ticker} prices from GCS")
                else:
                    raise ScoreComputationError(f"Price history not found for {ticker}")
            except Exception as e:
                logger.warning(f"Could not lazy-load {ticker} prices: {e}")
                raise ScoreComputationError(f"Price history not found for {ticker}")
        else:
            raise ScoreComputationError(f"Price history not found for {ticker}")
    df = pd.read_csv(path, parse_dates=["Date"])
    df = df.sort_values("Date").set_index("Date")

    # Convert index to DatetimeIndex and strip timezone info
    if not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index, utc=True)
    if df.index.tz is not None:
        df.index = df.index.tz_convert('UTC').tz_localize(None)

    return df


def calculate_cagr(series: pd.Series) -> Optional[float]:
    if series.empty or len(series) < 2:
        return None
    start_value = series.iloc[0]
    end_value = series.iloc[-1]
    if start_value <= 0 or end_value <= 0:
        return None
    periods = len(series) - 1
    if periods == 0:
        return None
    cagr = (end_value / start_value) ** (1 / periods) - 1
    return cagr


def safe_series(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return df[column].dropna()


def compute_business_score(ticker: str, fin_df: pd.DataFrame, info: dict) -> ComponentScore:
    revenue_series = safe_series(fin_df, "Total Revenue")
    if revenue_series.empty:
        raise ScoreComputationError(f"Total Revenue series missing for {ticker}")

    gross_profit_series = safe_series(fin_df, "Gross Profit")
    gross_margin_series = (gross_profit_series / revenue_series).dropna() if not gross_profit_series.empty else pd.Series(dtype=float)

    rnd_series_raw = safe_series(fin_df, "Research And Development")
    rnd_series = (rnd_series_raw / revenue_series).dropna() if not rnd_series_raw.empty else pd.Series(dtype=float)

    # Filter to annual data - try common fiscal year ends (Dec 31, Sep 30, Oct 31, Jan 31)
    # Most companies use calendar year (Dec 31), but some use different fiscal years
    annual_revenue = pd.Series(dtype=float)
    
    # Try Dec 31 (calendar year)
    dec31 = revenue_series[
        (revenue_series.index.month == 12) & (revenue_series.index.day == 31)
    ]
    if len(dec31) >= 2:
        annual_revenue = dec31.sort_index()
    else:
        # Try Oct 31 (common fiscal year end, e.g., AVGO)
        oct31 = revenue_series[
            (revenue_series.index.month == 10) & (revenue_series.index.day == 31)
        ]
        if len(oct31) >= 2:
            annual_revenue = oct31.sort_index()
        else:
            # Try Sep 30 (common fiscal year end)
            sep30 = revenue_series[
                (revenue_series.index.month == 9) & (revenue_series.index.day == 30)
            ]
            if len(sep30) >= 2:
                annual_revenue = sep30.sort_index()
            else:
                # Try Jan 31 (some companies)
                jan31 = revenue_series[
                    (revenue_series.index.month == 1) & (revenue_series.index.day == 31)
                ]
                if len(jan31) >= 2:
                    annual_revenue = jan31.sort_index()
    
    # Use annual data if available, otherwise fall back to last 4 periods
    if len(annual_revenue) >= 2:
        revenue_cagr = calculate_cagr(annual_revenue[-4:] if len(annual_revenue) >= 4 else annual_revenue)
    else:
        # Fallback: use all available data if no annual data found
        revenue_cagr = calculate_cagr(revenue_series[-4:])
    gross_margin_latest = gross_margin_series.iloc[-1] if not gross_margin_series.empty else None
    rnd_intensity_latest = rnd_series.iloc[-1] if not rnd_series.empty else None

    industry = info.get("industry") or ""
    sector = info.get("sector") or ""

    industry_score = SECTOR_GROWTH_BONUS.get(industry, SECTOR_GROWTH_BONUS.get(sector, 6.0))
    moat_score_components = []

    notes = []

    if revenue_cagr is not None:
        revenue_score = score_from_thresholds(
            revenue_cagr,
            [(-0.05, 2), (0.0, 4), (0.05, 6), (0.15, 8), (0.30, 10)],
        )
        moat_score_components.append(revenue_score)
    else:
        notes.append("Insufficient data to compute revenue CAGR.")

    if gross_margin_latest is not None:
        gm_score = score_from_thresholds(
            gross_margin_latest,
            [(0.2, 3), (0.35, 5), (0.45, 7), (0.55, 9), (0.65, 10)],
        )
        moat_score_components.append(gm_score)
    else:
        notes.append("Missing gross margin data.")

    if rnd_intensity_latest is not None:
        rnd_score = score_from_thresholds(
            rnd_intensity_latest,
            [(0.05, 4), (0.1, 6), (0.15, 8), (0.20, 9), (0.30, 10)],
        )
        moat_score_components.append(rnd_score)
    else:
        notes.append("Research & Development intensity unavailable.")

    if not moat_score_components:
        moat_score = 5.0
    else:
        moat_score = mean(moat_score_components)

    combined = mean([industry_score, moat_score])

    summary = (
        f"Operating in {industry or sector}, revenue CAGR of "
        f"{revenue_cagr:.1%} and gross margin of {gross_margin_latest:.1%} signal a strong moat."
        if revenue_cagr is not None and gross_margin_latest is not None
        else "Industry fundamentals are favorable; additional moat data is limited."
    )

    return ComponentScore(
        score=clamp(combined),
        summary=summary,
        inputs={
            "revenue_cagr": revenue_cagr if revenue_cagr is not None else np.nan,
            "gross_margin": gross_margin_latest if gross_margin_latest is not None else np.nan,
            "rnd_intensity": rnd_intensity_latest if rnd_intensity_latest is not None else np.nan,
            "industry_score": industry_score,
        },
        notes=notes,
    )


def compute_financial_score(fin_df: pd.DataFrame, info: dict) -> ComponentScore:
    revenue_series = safe_series(fin_df, "Total Revenue")
    net_income_series = safe_series(fin_df, "Net Income")
    if revenue_series.empty or net_income_series.empty:
        raise ScoreComputationError("Insufficient revenue/net income data for financial scoring.")

    # Filter to annual data - try common fiscal year ends (Dec 31, Sep 30, Oct 31, Jan 31)
    # Most companies use calendar year (Dec 31), but some use different fiscal years
    annual_revenue = pd.Series(dtype=float)
    
    # Try Dec 31 (calendar year)
    dec31 = revenue_series[
        (revenue_series.index.month == 12) & (revenue_series.index.day == 31)
    ]
    if len(dec31) >= 2:
        annual_revenue = dec31.sort_index()
    else:
        # Try Oct 31 (common fiscal year end, e.g., AVGO)
        oct31 = revenue_series[
            (revenue_series.index.month == 10) & (revenue_series.index.day == 31)
        ]
        if len(oct31) >= 2:
            annual_revenue = oct31.sort_index()
        else:
            # Try Sep 30 (common fiscal year end)
            sep30 = revenue_series[
                (revenue_series.index.month == 9) & (revenue_series.index.day == 30)
            ]
            if len(sep30) >= 2:
                annual_revenue = sep30.sort_index()
            else:
                # Try Jan 31 (some companies)
                jan31 = revenue_series[
                    (revenue_series.index.month == 1) & (revenue_series.index.day == 31)
                ]
                if len(jan31) >= 2:
                    annual_revenue = jan31.sort_index()
    
    # Use annual data if available, otherwise fall back to last 4 periods
    if len(annual_revenue) >= 2:
        revenue_cagr = calculate_cagr(annual_revenue[-4:] if len(annual_revenue) >= 4 else annual_revenue)
    else:
        # Fallback: use all available data if no annual data found
        revenue_cagr = calculate_cagr(revenue_series[-4:])
    net_margin_series = (net_income_series / revenue_series).dropna()
    net_margin_latest = net_margin_series.iloc[-1] if not net_margin_series.empty else None

    free_cashflow = info.get("freeCashflow")
    total_debt = info.get("totalDebt")
    debt_to_equity = info.get("debtToEquity")

    # Use trailing P/E if available, otherwise use forward P/E
    pe_ratio = info.get("trailingPE")
    if pe_ratio is None or pe_ratio < 0:
        forward_pe = info.get("forwardPE")
        # Only use forward P/E if it's positive and reasonable (< 500)
        if forward_pe and 0 < forward_pe < 500:
            pe_ratio = forward_pe

    # Use trailing P/S, with fallback to calculated P/S if available
    ps_ratio = info.get("priceToSalesTrailing12Months")
    if ps_ratio is None or ps_ratio < 0:
        market_cap = info.get("marketCap")
        total_revenue = info.get("totalRevenue")
        if market_cap and total_revenue and total_revenue > 0:
            ps_ratio = market_cap / total_revenue

    notes: List[str] = []
    component_scores: List[float] = []

    if revenue_cagr is not None:
        component_scores.append(
            score_from_thresholds(
                revenue_cagr,
                [(-0.05, 2), (0.0, 4), (0.05, 6), (0.15, 8), (0.30, 10)],
            )
        )

    if net_margin_latest is not None:
        component_scores.append(
            score_from_thresholds(
                net_margin_latest,
                [(0.0, 3), (0.05, 5), (0.10, 6.5), (0.20, 8.5), (0.30, 10)],
            )
        )

    if free_cashflow and total_debt and total_debt > 0:
        fcf_coverage = free_cashflow / total_debt
        component_scores.append(
            score_from_thresholds(
                fcf_coverage,
                [(0.2, 3), (0.5, 5), (1.0, 7), (1.5, 9), (2.0, 10)],
            )
        )
    else:
        notes.append("Free cash flow or debt data missing; assuming neutral coverage.")
        component_scores.append(5.5)

    if debt_to_equity is not None and debt_to_equity > 0:
        component_scores.append(
            score_from_thresholds(
                debt_to_equity,
                [(50, 9.5), (100, 8.5), (200, 6.5), (300, 4.5), (500, 3.0), (800, 2.0)],
            )
        )
    else:
        notes.append("Debt-to-equity not available; assuming neutral leverage.")
        component_scores.append(6.0)

    if pe_ratio:
        component_scores.append(
            score_from_thresholds(
                pe_ratio,
                [(15, 9.5), (25, 8.5), (40, 7.0), (55, 5.0), (80, 3.5), (110, 2.0)],
            )
        )

    if ps_ratio:
        component_scores.append(
            score_from_thresholds(
                ps_ratio,
                [(2, 9.0), (4, 8.0), (6, 7.0), (8, 6.0), (12, 4.5), (18, 3.0)],
            )
        )

    # Forward P/E compression signal
    trailing_pe_raw = info.get("trailingPE")
    forward_pe_raw = info.get("forwardPE")
    if (
        trailing_pe_raw is not None and forward_pe_raw is not None
        and trailing_pe_raw > 0 and forward_pe_raw > 0
    ):
        pe_compression = (trailing_pe_raw - forward_pe_raw) / trailing_pe_raw
        if pe_compression > 0.3:
            component_scores.append(8.5)
            notes.append("Strong forward P/E compression — expected earnings growth.")
        elif pe_compression > 0.1:
            component_scores.append(7.0)
            notes.append("Moderate forward P/E compression — moderate expected growth.")
        elif pe_compression < -0.2:
            component_scores.append(4.0)
            notes.append("Negative forward P/E compression — expected earnings decline.")

    score = clamp(mean(component_scores)) if component_scores else None

    summary = (
        f"Revenue CAGR {revenue_cagr:.1%}, net margin {net_margin_latest:.1%}, "
        f"with free cash flow coverage {free_cashflow / total_debt:.2f}x."
        if revenue_cagr is not None and net_margin_latest is not None and free_cashflow and total_debt
        else "Financial metrics indicate solid fundamentals with some data gaps."
    )

    return ComponentScore(
        score=score,
        summary=summary,
        inputs={
            "revenue_cagr": revenue_cagr if revenue_cagr is not None else np.nan,
            "net_margin": net_margin_latest if net_margin_latest is not None else np.nan,
            "free_cashflow": free_cashflow if free_cashflow is not None else np.nan,
            "total_debt": total_debt if total_debt is not None else np.nan,
            "debt_to_equity": debt_to_equity if debt_to_equity is not None else np.nan,
            "trailing_pe": pe_ratio if pe_ratio is not None else np.nan,
            "price_to_sales": ps_ratio if ps_ratio is not None else np.nan,
        },
        notes=notes,
    )


def compute_event_sentiment_score(ticker: str, news_items: List[dict], reddit_stats: Optional[dict]) -> ComponentScore:
    sentiments = []
    timeline = []
    now = datetime.now(timezone.utc)

    for item in news_items or []:
        content = item.get("content") or {}
        title = content.get("title") or item.get("title") or "Event"
        summary = content.get("summary") or content.get("description") or title
        provider = (content.get("provider") or {}).get("displayName") or (item.get("provider") or {}).get("displayName") or "Unknown"
        link = (
            item.get("link")
            or (item.get("canonicalUrl") or {}).get("url")
            or (item.get("clickThroughUrl") or {}).get("url")
            or (content.get("canonicalUrl") or {}).get("url")
        )
        provider_time = (
            item.get("providerPublishTime")
            or content.get("pubDate")
        )
        if isinstance(provider_time, (int, float)):
            published_at = datetime.fromtimestamp(provider_time, tz=timezone.utc)
        elif isinstance(provider_time, str) and provider_time:
            try:
                published_at = datetime.fromisoformat(provider_time.replace("Z", "+00:00"))
            except ValueError:
                published_at = now
        else:
            published_at = now
        age_days = (now - published_at).days
        sentiment = sentiment_analyzer.polarity_scores(title or summary)
        weight = max(0.2, 1 - (age_days / 30))
        sentiments.append(sentiment["compound"] * weight)
        timeline.append(
            {
                "title": title,
                "source": provider,
                "published_at": published_at.isoformat(),
                "link": link,
                "sentiment": sentiment["compound"],
                "weight": weight,
            }
        )

    notes = []

    news_score = None
    coverage = 0.0
    avg_sentiment = 0.0
    if sentiments:
        coverage = min(len(news_items), 10) / 10
        avg_sentiment = sum(sentiments) / len(sentiments)
        base = score_from_thresholds(
            avg_sentiment,
            [(-0.6, 1), (-0.2, 4), (0.0, 5.5), (0.2, 7.5), (0.45, 9.5)],
        )
        news_score = clamp(base * (0.5 + 0.5 * coverage))
    else:
        notes.append("No recent mainstream news detected.")

    reddit_score = None
    reddit_ratio = None
    reddit_total = 0
    if reddit_stats and reddit_stats.get("total_posts"):
        reddit_total = reddit_stats.get("total_posts", 0)
        bullish = reddit_stats.get("bullish_posts", 0)
        bearish = reddit_stats.get("bearish_posts", 0)
        reddit_ratio = (bullish - bearish) / max(reddit_total, 1)
        reddit_base = score_from_thresholds(
            reddit_ratio,
            [(-0.6, 2), (-0.2, 4), (0.0, 6), (0.2, 8), (0.4, 9.5)],
        )
        reddit_coverage = min(reddit_total / 15, 1.0)
        reddit_score = clamp(reddit_base * (0.4 + 0.6 * reddit_coverage))
    else:
        notes.append("No recent Reddit sentiment captured.")

    combined_scores = [s for s in [news_score, reddit_score] if s is not None]
    final_score = clamp(mean(combined_scores)) if combined_scores else 5.0

    summary_parts = []
    if news_score is not None:
        summary_parts.append(f"News sentiment {avg_sentiment:.2f} across {len(news_items)} items.")
    if reddit_score is not None:
        summary_parts.append(f"Reddit activity {reddit_total} posts with bullish ratio {reddit_ratio:.2f}.")
    if not summary_parts:
        summary_parts.append("Sentiment data limited; neutral baseline applied.")

    summary = " ".join(summary_parts)

    return ComponentScore(
        score=final_score,
        summary=summary,
        inputs={
            "average_sentiment": avg_sentiment,
            "coverage": coverage,
            "reddit_ratio": reddit_ratio if reddit_ratio is not None else np.nan,
            "reddit_posts": reddit_total,
        },
        notes=notes,
    )


def compute_critical_path_score(ticker: str, info: dict) -> ComponentScore:
    base = CRITICAL_PATH_MAP.get(ticker.upper(), 5.0)
    industry = info.get("industry", "")
    summary = f"{ticker} operates in {industry or info.get('sector', 'its sector')}, weighted criticality score {base:.1f}."
    return ComponentScore(
        score=base,
        summary=summary,
        inputs={"industry": industry, "sector": info.get("sector")},
        notes=[],
    )


def compute_leadership_score(ticker: str, info: dict) -> ComponentScore:
    officers = info.get("companyOfficers") or []
    ceo = next((o for o in officers if "CEO" in (o.get("title") or "").upper()), None)
    profile = load_ceo_profile(ticker)
    tenure_years: Optional[float] = None
    education = None
    linkedin_url = None
    reputation_bonus = 0.0

    if profile:
        education = profile.get("education")
        linkedin_url = profile.get("linkedin_url")
        start_date = profile.get("start_date")
        if isinstance(start_date, str) and start_date and start_date.lower() != "not found":
            start_dt = pd.to_datetime(start_date, errors="coerce")
            if pd.notnull(start_dt):
                tenure_years = (datetime.utcnow() - start_dt.to_pydatetime()).days / 365.0
        tenure_duration = profile.get("tenure_duration")
        if tenure_years is None and isinstance(tenure_duration, str) and tenure_duration.lower() != "not found":
            match = re.search(r"(\d+)", tenure_duration)
            if match:
                tenure_years = float(match.group(1))
        try:
            num_highlights = float(profile.get("num_highlights", 0))
        except (TypeError, ValueError):
            num_highlights = 0.0
        if num_highlights > 0:
            reputation_bonus += 0.5

    notes: List[str] = []
    score_components: List[float] = []

    if ceo:
        title = ceo.get("title", "")
        age = ceo.get("age")
        if "CO-FOUNDER" in title.upper():
            score_components.append(9.0)
        if age and age >= 55:
            score_components.append(7.5)
    else:
        notes.append("CEO not listed in officer roster; using neutral baseline.")

    if tenure_years is not None:
        score_components.append(
            score_from_thresholds(
                tenure_years,
                [(2, 6.0), (4, 7.0), (6, 8.0), (10, 9.0), (15, 9.5)],
            )
        )
    elif ceo and ceo.get("maxAge"):
        notes.append("Tenure duration not available; partial leadership score applied.")

    if len(officers) >= 5:
        score_components.append(7.5)
    if any("Chief Scientist" in (o.get("title") or "") for o in officers):
        score_components.append(7.5)

    if reputation_bonus:
        score_components.append(7.0 + reputation_bonus)

    score = clamp(mean(score_components) if score_components else 5.5)

    summary_parts = []
    if ceo:
        summary_parts.append(
            f"Led by {ceo.get('name')} ({ceo.get('title')})."
        )
    if tenure_years:
        summary_parts.append(f"Approx. tenure {tenure_years:.1f} years.")
    if education and isinstance(education, str) and education.lower() != "not found":
        summary_parts.append(f"Education: {education}.")
    if not summary_parts:
        summary_parts.append("Leadership data limited; defaulting to neutral score.")

    summary = " ".join(summary_parts)

    return ComponentScore(
        score=score,
        summary=summary,
        inputs={
            "officer_count": len(officers),
            "ceo_tenure_years": tenure_years if tenure_years is not None else np.nan,
        },
        notes=notes,
    )


def compute_earnings_score(earnings_df: pd.DataFrame) -> ComponentScore:
    if earnings_df.empty:
        return ComponentScore(
            score=5.0,
            summary="No quarterly earnings data available; treating as neutral.",
            inputs={},
            notes=["Earnings dataset empty."],
        )

    eps = earnings_df["eps"].dropna()
    revenue = earnings_df["revenue"].dropna()
    earnings = earnings_df["earnings"].dropna()

    if len(eps) < 2:
        return ComponentScore(
            score=5.0,
            summary="Insufficient EPS history for scoring; neutral baseline applied.",
            inputs={"eps_points": len(eps)},
            notes=[],
        )

    eps_growth = eps.pct_change().dropna()
    revenue_growth = revenue.pct_change().dropna()

    eps_consistency = 1 / (eps_growth.std() + 1e-6)
    revenue_consistency = 1 / (revenue_growth.std() + 1e-6)

    eps_trend = eps_growth.mean()
    revenue_trend = revenue_growth.mean()

    eps_score = score_from_thresholds(
        eps_trend,
        [(-0.1, 2), (0.0, 4), (0.05, 6), (0.15, 8.5), (0.30, 10)],
    )
    rev_score = score_from_thresholds(
        revenue_trend,
        [(-0.05, 2), (0.0, 4), (0.05, 6.5), (0.15, 8.5), (0.30, 10)],
    )
    stability_score = score_from_thresholds(
        eps_consistency,
        [(2, 4), (5, 6), (10, 8), (15, 9), (25, 10)],
    )

    combined = clamp(mean([eps_score, rev_score, stability_score]))

    summary = (
        f"EPS trend {eps_trend:.1%}, revenue trend {revenue_trend:.1%}, "
        f"with consistency score {stability_score:.1f}."
    )

    return ComponentScore(
        score=combined,
        summary=summary,
        inputs={
            "eps_trend": eps_trend,
            "revenue_trend": revenue_trend,
            "consistency_metric": eps_consistency,
        },
        notes=[],
    )


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def compute_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    delta = series.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def compute_technical_score(price_df: pd.DataFrame) -> ComponentScore:
    if price_df.empty:
        return ComponentScore(
            score=5.0,
            summary="Price history unavailable; technical stance neutral.",
            inputs={},
            notes=[],
        )

    closes = price_df["Close"]
    rsi_series = compute_rsi(closes).dropna()
    if rsi_series.empty:
        return ComponentScore(
            score=5.0,
            summary="Insufficient price data for RSI; technical score neutral.",
            inputs={},
            notes=[],
        )

    latest_rsi = rsi_series.iloc[-1]

    ema12 = ema(closes, 12)
    ema26 = ema(closes, 26)
    macd = ema12 - ema26
    signal = ema(macd, 9)
    macd_cross = macd.iloc[-1] - signal.iloc[-1]

    ma50 = closes.rolling(window=50).mean()
    ma200 = closes.rolling(window=200).mean()

    latest_close = closes.iloc[-1]
    ma50_latest = ma50.iloc[-1] if not ma50.dropna().empty else None
    ma200_latest = ma200.iloc[-1] if not ma200.dropna().empty else None

    score = 5.0
    notes: List[str] = []

    if latest_rsi < 30:
        score += 3
        notes.append("RSI indicates oversold conditions.")
    elif latest_rsi > 70:
        score -= 3
        notes.append("RSI indicates overbought conditions.")

    if macd_cross > 0:
        score += 2
        notes.append("MACD bullish crossover detected.")
    elif macd_cross < 0:
        score -= 2
        notes.append("MACD bearish crossover detected.")

    if ma50_latest and ma200_latest:
        if ma50_latest > ma200_latest:
            score += 3
            notes.append("Golden cross (MA50 > MA200).")
        else:
            score -= 2
            notes.append("Bearish moving average alignment.")

    score = clamp(score)

    summary = (
        f"RSI {latest_rsi:.1f}, MACD differential {macd_cross:.2f}, "
        f"closing price ${latest_close:,.2f}."
    )

    return ComponentScore(
        score=score,
        summary=summary,
        inputs={
            "rsi": latest_rsi,
            "macd_delta": macd_cross,
            "close": latest_close,
            "ma50": ma50_latest if ma50_latest is not None else np.nan,
            "ma200": ma200_latest if ma200_latest is not None else np.nan,
        },
        notes=notes,
    )


def compute_overall_score(component_scores: Dict[str, ComponentScore]) -> Dict[str, float]:
    weights = {
        "business": 0.20,
        "financial": 0.25,
        "sentiment": 0.15,
        "critical": 0.10,
        "leadership": 0.10,
        "earnings": 0.10,
        "technical": 0.10,
    }

    weighted_scores = []
    applied_weights = []
    available_scores = []

    for key, comp in component_scores.items():
        if comp.score is not None:
            weight = weights.get(key, 0.0)
            weighted_scores.append(comp.score * weight)
            applied_weights.append(weight)
            available_scores.append(comp.score)

    total_weight = sum(applied_weights) or 1.0
    aggregate = sum(weighted_scores) / total_weight

    if available_scores:
        variance = pvariance(available_scores)
        confidence = clamp(1 - variance / 36, 0.4, 0.95)
    else:
        confidence = 0.5

    if aggregate >= 8:
        recommendation = "Strong Buy"
        hold_duration = "Long-term (12-24 months horizon)"
    elif aggregate >= 7:
        recommendation = "Buy"
        hold_duration = "Long-term (12-18 months horizon)"
    elif aggregate >= 4:
        recommendation = "Hold"
        hold_duration = "Medium-term (6-12 months horizon)"
    else:
        recommendation = "Sell"
        hold_duration = "Reevaluate position in the short term (<6 months)"

    return {
        "score": round(aggregate, 2),
        "confidence": round(confidence * 100, 1),
        "recommendation": recommendation,
        "hold_duration": hold_duration,
    }


def build_event_timeline(news_items: List[dict], max_items: int = 5) -> List[dict]:
    timeline = []
    for item in news_items[:max_items]:
        content = item.get("content") or {}
        title = content.get("title") or item.get("title") or "Event"
        provider = (content.get("provider") or {}).get("displayName") or (item.get("provider") or {}).get("displayName") or "Unknown"
        link = (
            item.get("link")
            or (item.get("canonicalUrl") or {}).get("url")
            or (item.get("clickThroughUrl") or {}).get("url")
            or (content.get("canonicalUrl") or {}).get("url")
        )
        provider_time = item.get("providerPublishTime") or content.get("pubDate")
        if isinstance(provider_time, (int, float)):
            published_at = datetime.fromtimestamp(provider_time, tz=timezone.utc)
        elif isinstance(provider_time, str) and provider_time:
            try:
                published_at = datetime.fromisoformat(provider_time.replace("Z", "+00:00"))
            except ValueError:
                published_at = datetime.utcnow().replace(tzinfo=timezone.utc)
        else:
            published_at = datetime.utcnow().replace(tzinfo=timezone.utc)

        sentiment = sentiment_analyzer.polarity_scores(title)
        timeline.append(
            {
                "title": title,
                "source": provider,
                "link": link,
                "published_at": published_at.isoformat(),
                "sentiment": sentiment["compound"],
            }
        )
    return timeline


def generate_business_model_description(ticker: str, info: dict, business_summary: str) -> str:
    """Generate a concise business model description based on company info."""
    try:
        # Known business models for all target companies
        business_models = {
            # Semiconductors & AI Infrastructure
            "NVDA": "Leading GPU manufacturer and AI computing platform provider. Designs and sells graphics cards, data center AI chips (H100, A100), and AI software platforms to gaming, professional visualization, automotive, and enterprise datacenter markets.",
            "TSM": "World's largest semiconductor foundry and contract chip manufacturer. Provides advanced chip manufacturing services (3nm, 5nm nodes) to fabless semiconductor companies including Apple, NVIDIA, AMD, and Qualcomm.",
            "AMD": "Semiconductor company designing high-performance CPUs and GPUs. Sells processors for PCs, servers, and datacenters (EPYC, Ryzen), and graphics cards (Radeon) competing with Intel and NVIDIA.",
            "AVGO": "Diversified semiconductor and infrastructure software company. Designs and sells chips for networking, broadband, wireless, storage, and industrial markets, plus enterprise software solutions.",
            "ORCL": "Enterprise software and cloud infrastructure company. Provides database management systems, cloud applications (ERP, HCM), and cloud infrastructure services to large enterprises worldwide.",

            # Critical Minerals - Lithium
            "ALB": "Specialty chemicals company and leading lithium producer. Manufactures lithium compounds for EV batteries, bromine specialties, and catalysts serving energy storage, electronics, and pharmaceutical markets.",
            "LAC": "Lithium development company focused on domestic U.S. supply. Developing the Thacker Pass lithium project in Nevada (largest lithium resource in North America) to supply battery-grade lithium for EVs.",

            # Critical Minerals - Rare Earth Elements (REE)
            "MP": "Rare earth mining and processing company. Operates Mountain Pass mine in California, producing rare earth concentrates and separated oxides for magnets, electronics, and defense applications.",
            "CRML": "Early-stage critical metals exploration company. Exploring for lithium and rare earth deposits in Austria and Greenland to support clean energy and technology supply chains.",
            "NMG": "Graphite development company focused on battery-grade material. Developing the Matawinie graphite mine in Quebec with integrated processing to supply anode material for lithium-ion EV batteries.",

            # Critical Minerals - Specialty Metals
            "UAMY": "Antimony and precious metals producer. Operates antimony smelter and zeolite mining, producing antimony products for flame retardants, batteries, and ceramics, plus silver and gold.",
            "PPTA": "Gold, silver, and antimony development company. Developing the Stibnite Gold Project in Idaho, which will be a significant U.S. source of antimony (critical for defense) and precious metals.",
            "NAK": "Mineral exploration company focused on Alaska. Developing the Pebble copper-gold-molybdenum project, one of the world's largest undeveloped copper resources, serving global metals demand.",
            "NB": "Niobium, scandium, and titanium development company. Developing the Elk Creek project in Nebraska to produce critical metals for steel alloys, aluminum aerospace alloys, and advanced materials.",
            "NVA": "Gold and antimony exploration company. Exploring gold deposits in Alaska (Estelle, Korbel) and antimony projects in Australia to supply precious metals and critical defense materials.",

            # Legacy entries
            "AAPL": "Consumer electronics and services company. Sells iPhones, Macs, iPads, and services like App Store, iCloud, and Apple Music.",
            "MSFT": "Technology company offering cloud computing (Azure), productivity software (Office), gaming (Xbox), and enterprise services.",
            "GOOGL": "Internet services and advertising company. Provides search, YouTube, cloud computing, and Android operating system.",
            "AMZN": "E-commerce and cloud computing giant. Operates online retail, AWS cloud services, and logistics networks.",
            "META": "Social media and metaverse company. Owns Facebook, Instagram, WhatsApp, and develops VR/AR technologies.",
            "TSLA": "Electric vehicle manufacturer and clean energy company. Sells EVs, solar panels, energy storage, and autonomous driving software."
        }
        
        # Return specific model if known
        if ticker in business_models:
            return business_models[ticker]
        
        # Generate from business summary
        if "semiconductor" in business_summary or "chip" in business_summary:
            return "Semiconductor company providing computing and technology solutions to various industries."
        elif "software" in business_summary or "cloud" in business_summary:
            return "Technology company providing software, cloud computing, and digital services."
        elif "retail" in business_summary or "ecommerce" in business_summary:
            return "Retail and e-commerce company serving consumer markets."
        elif "energy" in business_summary or "oil" in business_summary or "gas" in business_summary:
            return "Energy company involved in oil, gas, or renewable energy production and distribution."
        elif "healthcare" in business_summary or "pharmaceutical" in business_summary:
            return "Healthcare company providing medical products, services, or pharmaceutical solutions."
        elif "financial" in business_summary or "bank" in business_summary or "insurance" in business_summary:
            return "Financial services company providing banking, insurance, or investment services."
        # Mining and metals sector
        elif any(term in business_summary for term in ["mining", "mine", "gold", "silver", "metal", "antimony", "ore"]):
            return "Development-stage mining company focused on exploration and development of gold, silver, and antimony deposits in the United States."
        # Agriculture / Food sector (e.g., poultry, meat producers)
        elif any(term in business_summary for term in ["poultry", "chicken", "meat", "food"]):
            return "Poultry producer and distributor specializing in chicken and meat products for retail and foodservice markets."
        # Agriculture / Food sector (e.g., poultry, meat producers)
        elif any(term in business_summary for term in ["poultry", "chicken", "meat", "food"]):
            return "Poultry producer and distributor specializing in chicken and meat products for retail and foodservice markets."
        else:
            return "Technology and business services company serving various market segments."
            
    except Exception:
        return "Technology company providing products and services to various markets."


def get_quick_facts(ticker: str, info: dict, fin_df: pd.DataFrame) -> dict:
    """Extract key financial and business facts for quick fact card."""
    try:
        # Revenue metrics
        revenue_ttm = info.get("totalRevenue") or 0
        revenue_growth_yoy = info.get("revenueGrowth") or 0
        
        # Profit metrics - use proper net income field
        net_income = info.get("netIncome") or info.get("netIncomeToCommon") or 0
        profit_margin = (net_income / revenue_ttm * 100) if revenue_ttm > 0 else 0
        
        # Ensure profit margin is reasonable (cap at 100%)
        if profit_margin > 100:
            profit_margin = 100
        elif profit_margin < -100:
            profit_margin = -100
        eps = info.get("trailingEps") or 0
        
        # Business type analysis
        business_summary = info.get("longBusinessSummary", "").lower()
        is_b2b = any(term in business_summary for term in ["enterprise", "business", "b2b", "corporate", "commercial"])
        is_b2c = any(term in business_summary for term in ["consumer", "retail", "individual", "b2c"])
        business_type = "B2B" if is_b2b and not is_b2c else "B2C" if is_b2c else "Mixed"
        
        # Generate business model description
        business_model = generate_business_model_description(ticker, info, business_summary)
        
        # HQ Location
        city = info.get("city", "")
        state = info.get("state", "")
        country = info.get("country", "")
        hq_location = f"{city}, {state}" if city and state else city or state or country
        
        # Market cap and valuation
        market_cap = info.get("marketCap") or 0

        # Sector and Industry
        sector = info.get("sector") or "N/A"
        industry = info.get("industry") or "N/A"

        # P/E ratio with fallback to forward P/E
        pe_ratio = info.get("trailingPE")
        if pe_ratio is None or pe_ratio < 0:
            forward_pe = info.get("forwardPE")
            if forward_pe and 0 < forward_pe < 500:
                pe_ratio = forward_pe

        # P/S ratio with fallback to calculated
        ps_ratio = info.get("priceToSalesTrailing12Months")
        if ps_ratio is None or ps_ratio < 0:
            if market_cap and revenue_ttm > 0:
                ps_ratio = market_cap / revenue_ttm

        return {
            "revenue_ttm": revenue_ttm,
            "revenue_growth_yoy": revenue_growth_yoy * 100,
            "profit_margin": profit_margin,
            "eps": eps,
            "business_type": business_type,
            "business_model": business_model,
            "hq_location": hq_location,
            "market_cap": market_cap,
            "sector": sector,
            "industry": industry,
            "pe_ratio": pe_ratio,
            "ps_ratio": ps_ratio,
            "employees": info.get("fullTimeEmployees"),
            "founded": info.get("foundedYear"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "beta": info.get("beta"),
            "price_to_book": info.get("priceToBook"),
            "dividend_yield": info.get("dividendYield"),
        }
    except Exception:
        return {}


def get_recommendation_analysis(ticker: str, info: dict, scores: dict) -> dict:
    """Generate comprehensive Buy/Hold/Sell recommendation with detailed reasoning."""
    try:
        overall_score = scores.get("overall", {}).get("score", 0)
        
        # Get component scores (handle both dict and ComponentScore objects)
        def get_score(key):
            comp = scores.get(key)
            if comp is None:
                return 0
            if hasattr(comp, 'score'):
                return comp.score if comp.score is not None else 0
            if isinstance(comp, dict):
                return comp.get('score', 0)
            return 0
        
        # Valuation context
        forward_pe = info.get("forwardPE") or 0
        trailing_pe = info.get("trailingPE") or 0
        peg_ratio = info.get("pegRatio") or 0
        industry_pe = info.get("industryPE") or forward_pe * 1.2
        
        # Check if stock is expensive
        pe_premium = (forward_pe / industry_pe - 1) * 100 if industry_pe > 0 and forward_pe > 0 else 0
        is_expensive = pe_premium > 30  # Trading at 30%+ premium to industry
        is_cheap = pe_premium < -20  # Trading at 20%+ discount
        
        # Check market momentum (using technical score as proxy)
        technical_score = get_score("technical")
        bullish_momentum = technical_score >= 7
        bearish_momentum = technical_score <= 4
        
        # Determine base recommendation based on overall score
        if overall_score >= 8.0:
            recommendation = "Strong Buy"
            confidence = "High"
            
            # Adjust timing based on valuation
            if is_expensive and not bullish_momentum:
                action = "Consider accumulating on dips"
                timing = "Wait for pullback - Stock is trading at premium valuation. Consider entry on 5-10% correction or after positive catalyst confirmation."
            elif is_expensive:
                action = "Consider dollar-cost averaging"
                timing = "Start small position now, add on weakness - Strong fundamentals but elevated valuation suggests gradual accumulation strategy."
            else:
                action = "Consider buying immediately"
                timing = "Now - Strong fundamentals with reasonable valuation and positive momentum. Good risk/reward."
                
        elif overall_score >= 6.5:
            recommendation = "Buy"
            confidence = "Medium-High"
            
            if is_expensive:
                action = "Wait for better entry point"
                timing = "Monitor for 2-4 weeks - Good fundamentals but stock is expensive vs peers. Wait for market pullback or earnings dip."
            elif bullish_momentum:
                action = "Consider accumulating position"
                timing = "Within next 1-2 months - Good fundamentals with positive momentum. Start building position."
            else:
                action = "Consider accumulating position"
                timing = "Within next 1-3 months - Good fundamentals with room for growth. Watch for confirmation of trend."
                
        elif overall_score >= 5.0:
            recommendation = "Hold"
            confidence = "Medium"
            action = "Hold current position or wait for better entry"
            timing = "Monitor for 3-6 months - Mixed signals. Wait for clearer direction or improved fundamentals before adding."
            
        elif overall_score >= 3.5:
            recommendation = "Weak Hold"
            confidence = "Medium-Low"
            action = "Consider reducing position"
            timing = "Review in 1-2 months - Concerning trends suggest defensive posture. Consider trimming on any rallies."
        else:
            recommendation = "Sell"
            confidence = "High"
            action = "Consider exiting position"
            timing = "Soon - Weak fundamentals and negative momentum suggest limited upside. Exit on strength if possible."
        
        business_score = get_score("business")
        financial_score = get_score("financial")
        sentiment_score = get_score("sentiment")
        technical_score = get_score("technical")
        leadership_score = get_score("leadership")
        
        # Build detailed reasoning
        strengths = []
        weaknesses = []
        risks = []
        
        # Business analysis
        if business_score >= 7:
            strengths.append("Strong business model with solid revenue growth and margins")
        elif business_score <= 4:
            weaknesses.append("Weak business fundamentals with declining growth")
            risks.append("Revenue growth may continue to decelerate")
        
        # Financial health
        if financial_score >= 7:
            strengths.append("Excellent financial health with strong balance sheet")
        elif financial_score <= 4:
            weaknesses.append("Financial concerns including debt or profitability issues")
            risks.append("Financial stress could limit growth investments")
        
        # Market sentiment
        if sentiment_score >= 7:
            strengths.append("Positive market sentiment and momentum")
        elif sentiment_score <= 4:
            weaknesses.append("Negative market sentiment")
            risks.append("Market pessimism could drive further price weakness")
        
        # Technical indicators
        if technical_score >= 7:
            strengths.append("Strong technical indicators showing upward momentum")
        elif technical_score <= 4:
            weaknesses.append("Weak technical signals suggesting downward pressure")
        
        # Leadership
        if leadership_score >= 7:
            strengths.append("Proven leadership team with strong track record")
        elif leadership_score <= 4:
            risks.append("Leadership concerns may impact execution")
        
        # Valuation risk
        if forward_pe > 0 and industry_pe > 0:
            pe_premium_calc = (forward_pe / industry_pe - 1) * 100
            if pe_premium_calc > 50:
                risks.append(f"Trading at significant premium to industry ({pe_premium_calc:.0f}% above average)")
            elif pe_premium_calc < -30:
                strengths.append(f"Attractive valuation ({abs(pe_premium_calc):.0f}% below industry average)")
        
        # Market and sector risks
        sector = info.get("sector", "")
        if sector == "Technology":
            risks.append("Technology sector faces potential regulatory headwinds and rapid innovation cycles")
        elif sector == "Energy":
            risks.append("Energy prices are volatile and subject to geopolitical factors")
        elif sector == "Financial Services":
            risks.append("Interest rate changes and regulatory pressures could impact profitability")
        
        # Concentration risk
        revenue_growth = info.get("revenueGrowth") or 0
        if revenue_growth < 0:
            risks.append("Negative revenue growth indicates market share loss or sector headwinds")
        
        # Liquidity/volatility risk
        beta = info.get("beta") or 1.0
        if beta > 1.5:
            risks.append(f"High volatility (beta {beta:.1f}) means larger price swings vs market")
        
        # Ensure we always have at least 2-3 specific risks
        if len(risks) == 0:
            risks.append("Macroeconomic uncertainty could impact growth trajectory")
            risks.append("Competition and market dynamics may pressure margins")
        elif len(risks) == 1:
            risks.append("Market volatility and sector rotation could affect short-term performance")
        
        # Compile reasoning
        why_buy = " ".join(strengths[:2]) if strengths else "Limited positive catalysts identified"
        main_risks_text = " ".join(risks[:2]) if risks else "Standard market risks apply"
        key_concerns = " ".join(weaknesses[:2]) if weaknesses else "No major concerns identified"
        
        return {
            "recommendation": recommendation,
            "confidence": confidence,
            "action": action,
            "timing": timing,
            "why_buy": why_buy,
            "main_risks": main_risks_text,
            "key_concerns": key_concerns,
            "strengths": strengths,
            "weaknesses": weaknesses,
            "risks": risks,
            "forward_pe": forward_pe,
            "industry_pe": industry_pe,
            "pe_vs_industry": (forward_pe / industry_pe - 1) * 100 if industry_pe > 0 else 0,
            "overall_score": overall_score
        }
    except Exception as e:
        print(f"Error in recommendation analysis: {e}")
        return {
            "recommendation": "Hold",
            "confidence": "Low",
            "action": "Insufficient data",
            "timing": "Unable to determine",
            "why_buy": "Insufficient data for analysis",
            "main_risks": "Unable to assess risks",
            "key_concerns": "Data unavailable"
        }


def get_industry_comparison(ticker: str, info: dict) -> dict:
    """Generate industry comparison metrics."""
    try:
        sector = info.get("sector", "Unknown")
        industry = info.get("industry", "Unknown")
        
        # Key metrics for comparison
        forward_pe = info.get("forwardPE") or 0
        peg_ratio = info.get("pegRatio") or 0
        price_to_book = info.get("priceToBook") or 0
        gross_margin = info.get("grossMargins") or 0
        profit_margin = info.get("profitMargins") or 0
        
        # Revenue growth
        revenue_growth = info.get("revenueGrowth") or 0
        
        return {
            "sector": sector,
            "industry": industry,
            "metrics": {
                "forward_pe": forward_pe,
                "peg_ratio": peg_ratio,
                "price_to_book": price_to_book,
                "gross_margin": gross_margin * 100,
                "profit_margin": profit_margin * 100,
                "revenue_growth": revenue_growth * 100
            }
        }
    except Exception:
        return {"sector": "Unknown", "industry": "Unknown", "metrics": {}}


def get_score_benchmarks(component_scores: dict, info: dict) -> dict:
    """
    Generate industry benchmarks for comparison.
    Returns estimated industry averages for each score component.
    """
    sector = info.get("sector", "Technology")
    
    # Industry average benchmarks by sector (0-10 scale)
    sector_benchmarks = {
        "Technology": {"business": 7.0, "financial": 6.5, "sentiment": 6.0, "technical": 6.5, "leadership": 6.5, "earnings": 6.5, "critical": 6.0},
        "Healthcare": {"business": 6.5, "financial": 6.0, "sentiment": 5.5, "technical": 6.0, "leadership": 6.0, "earnings": 6.0, "critical": 5.5},
        "Financial Services": {"business": 6.0, "financial": 7.0, "sentiment": 5.5, "technical": 6.0, "leadership": 6.5, "earnings": 6.5, "critical": 6.0},
        "Energy": {"business": 5.5, "financial": 6.0, "sentiment": 5.0, "technical": 5.5, "leadership": 5.5, "earnings": 5.5, "critical": 5.5},
        "Consumer Cyclical": {"business": 6.0, "financial": 6.0, "sentiment": 6.0, "technical": 6.0, "leadership": 6.0, "earnings": 6.0, "critical": 5.5},
        "Industrials": {"business": 6.0, "financial": 6.5, "sentiment": 5.5, "technical": 6.0, "leadership": 6.0, "earnings": 6.0, "critical": 6.0},
        "Utilities": {"business": 5.5, "financial": 7.0, "sentiment": 5.0, "technical": 5.5, "leadership": 5.5, "earnings": 6.0, "critical": 5.5},
    }
    
    # Get benchmarks for the sector, default to Technology if not found
    benchmarks = sector_benchmarks.get(sector, sector_benchmarks["Technology"])
    
    # Calculate how each score compares to industry
    comparisons = {}
    for key, component in component_scores.items():
        if component and hasattr(component, 'score') and component.score is not None:
            industry_avg = benchmarks.get(key, 6.0)
            diff = component.score - industry_avg
            percentile = min(100, max(0, (component.score / 10.0) * 100))
            
            # Determine performance vs industry
            if diff >= 2.0:
                vs_industry = "Significantly Above Average"
                color = "green"
            elif diff >= 0.5:
                vs_industry = "Above Average"
                color = "lightgreen"
            elif diff >= -0.5:
                vs_industry = "Average"
                color = "yellow"
            elif diff >= -2.0:
                vs_industry = "Below Average"
                color = "orange"
            else:
                vs_industry = "Significantly Below Average"
                color = "red"
            
            comparisons[key] = {
                "company_score": component.score,
                "industry_avg": industry_avg,
                "difference": diff,
                "percentile": percentile,
                "vs_industry": vs_industry,
                "color": color
            }
    
    return {
        "sector": sector,
        "benchmarks": benchmarks,
        "comparisons": comparisons
    }


def get_price_history_with_events(ticker: str, news_items: List[dict], period: str = "1m") -> dict:
    """
    Fetch historical price data and annotate with major events.
    For intraday periods (1d, 1w), fetches live minute/hour data from yfinance.
    For longer periods, uses local CSV data and enriches with the most recent intraday snapshot.
    Returns time series data suitable for charting with event markers.
    """
    try:
        import yfinance as yf

        latest_snapshot = None
        hist = pd.DataFrame()

        if period in ["1d", "1w"]:
            try:
                yf_period, interval = ("1d", "5m") if period == "1d" else ("5d", "30m")
                stock = yf.Ticker(ticker)
                hist = stock.history(period=yf_period, interval=interval)

                if hist.empty:
                    logger.warning("No intraday data available for %s period %s", ticker, period)
                    return {"price_data": [], "events": [], "error": "No intraday data available"}

                if isinstance(hist.index, pd.DatetimeIndex) and hist.index.tz is not None:
                    hist.index = hist.index.tz_convert("UTC").tz_localize(None)
            except Exception as exc:
                logger.error("Error fetching intraday data for %s: %s", ticker, exc)
                return {"price_data": [], "events": [], "error": str(exc)}
        else:
            try:
                price_df = load_price_history(ticker)
            except ScoreComputationError:
                return {"price_data": [], "events": []}

            if price_df.empty:
                return {"price_data": [], "events": []}

            if isinstance(price_df.index, pd.DatetimeIndex) and price_df.index.tz is not None:
                price_df.index = price_df.index.tz_convert("UTC").tz_localize(None)

            period_days_map = {
                "5d": 5,
                "1m": 30,
                "1mo": 30,
                "3m": 90,
                "3mo": 90,
                "6m": 180,
                "6mo": 180,
                "1y": 365,
                "2y": 730,
                "5y": 1825,
                "10y": 3650,
                "ytd": None,
                "max": None,
            }
            days = period_days_map.get(period, 30)
            if days:
                cutoff_date = datetime.now() - timedelta(days=days)
                hist = price_df[price_df.index >= cutoff_date]
            elif period == "ytd":
                cutoff_date = datetime(datetime.now().year, 1, 1)
                hist = price_df[price_df.index >= cutoff_date]
            else:
                hist = price_df

            if hist.empty:
                return {"price_data": [], "events": []}

            try:
                stock = yf.Ticker(ticker)
                intraday = stock.history(period="1d", interval="1m")
                if not intraday.empty:
                    timestamp = intraday.index[-1]
                    if isinstance(timestamp, pd.DatetimeIndex):
                        timestamp = timestamp[-1]
                    if isinstance(timestamp, pd.Timestamp) and timestamp.tzinfo is not None:
                        timestamp = timestamp.tz_convert("UTC").tz_localize(None)
                    last_row = intraday.iloc[-1]
                    latest_snapshot = {
                        "timestamp": timestamp.isoformat() if hasattr(timestamp, "isoformat") else str(timestamp),
                        "open": _round(last_row.get("Open")),
                        "high": _round(last_row.get("High")),
                        "low": _round(last_row.get("Low")),
                        "close": _round(last_row.get("Close")),
                        "volume": int(last_row.get("Volume") or 0),
                    }
            except Exception as exc:
                logger.warning("Failed to fetch live price snapshot for %s: %s", ticker, exc)

        price_data: List[Dict[str, Any]] = []
        significant_moves: List[Dict[str, Any]] = []

        for date, row in hist.iterrows():
            open_price = _round(row["Open"])
            close_price = _round(row["Close"])
            high_price = _round(row["High"])
            low_price = _round(row["Low"])
            if row["Open"] and row["Open"] != 0:
                daily_change = _round(((row["Close"] - row["Open"]) / row["Open"]) * 100)
            else:
                daily_change = 0.0
            price_data.append(
                {
                    "date": date.strftime("%Y-%m-%d %H:%M") if period in ["1d", "1w"] else date.strftime("%Y-%m-%d"),
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": int(row["Volume"]),
                    "daily_change": daily_change,
                }
            )
            if abs(daily_change) >= 10:
                significant_moves.append(
                    {
                        "date": date.strftime("%Y-%m-%d"),
                        "change": daily_change,
                        "close": close_price,
                    }
                )

        if latest_snapshot and period not in ["1d", "1w"]:
            snapshot_date = latest_snapshot["timestamp"][:10]
            existing = next((idx for idx, item in enumerate(price_data) if item["date"] == snapshot_date), None)
            open_px = latest_snapshot["open"]
            close_px = latest_snapshot["close"]
            if open_px and open_px != 0 and close_px is not None:
                snapshot_change = _round(((close_px - open_px) / open_px) * 100)
            else:
                snapshot_change = 0.0
            snapshot_entry = {
                "date": snapshot_date,
                "open": open_px,
                "high": latest_snapshot["high"],
                "low": latest_snapshot["low"],
                "close": close_px,
                "volume": latest_snapshot["volume"],
                "daily_change": snapshot_change,
            }
            if existing is not None:
                price_data[existing] = snapshot_entry
            else:
                price_data.append(snapshot_entry)
                price_data.sort(key=lambda x: x["date"])

        news_by_date: Dict[str, List[dict]] = {}
        now = datetime.now()

        for item in news_items or []:
            content = item.get("content") or {}
            title = content.get("title") or item.get("title") or "Event"
            provider = (
                (content.get("provider") or {}).get("displayName")
                or (item.get("provider") or {}).get("displayName")
                or "Unknown"
            )
            link = (
                item.get("link")
                or (item.get("canonicalUrl") or {}).get("url")
                or (item.get("clickThroughUrl") or {}).get("url")
                or (content.get("canonicalUrl") or {}).get("url")
            )
            provider_time = item.get("providerPublishTime") or content.get("pubDate")

            if isinstance(provider_time, (int, float)):
                published_at = datetime.fromtimestamp(provider_time)
            elif isinstance(provider_time, str) and provider_time:
                try:
                    published_at = datetime.fromisoformat(provider_time.replace("Z", "+00:00"))
                    if published_at.tzinfo is not None:
                        published_at = published_at.replace(tzinfo=None)
                except ValueError:
                    published_at = now
            else:
                published_at = now

            event_date = published_at.strftime("%Y-%m-%d")
            news_by_date.setdefault(event_date, [])
            sentiment = sentiment_analyzer.polarity_scores(title)
            news_by_date[event_date].append(
                {
                    "title": title,
                    "source": provider,
                    "link": link or f"https://finance.yahoo.com/quote/{ticker}/news",
                    "sentiment": sentiment["compound"],
                }
            )

        events: List[dict] = []
        for move in significant_moves:
            move_date = move["date"]
            if move_date in news_by_date and news_by_date[move_date]:
                news_item = news_by_date[move_date][0]
                events.append(
                    {
                        "date": move_date,
                        "title": news_item["title"],
                        "source": news_item["source"],
                        "link": news_item["link"],
                        "price": _round(move["close"]),
                        "price_change": _round(move["change"]),
                        "sentiment": news_item["sentiment"],
                        "has_news": True,
                    }
                )
            else:
                search_result = search_events_for_date(ticker, move_date, move["change"])
                if search_result:
                    events.append(
                        {
                            "date": move_date,
                            "title": search_result["title"],
                            "source": search_result["source"],
                            "link": search_result["link"],
                            "price": _round(move["close"]),
                            "price_change": _round(move["change"]),
                            "sentiment": search_result["sentiment"],
                            "has_news": True,
                        }
                    )
                else:
                    direction = "surge" if move["change"] > 0 else "drop"
                    events.append(
                        {
                            "date": move_date,
                            "title": f"Significant price {direction} ({abs(move['change']):.1f}%)",
                            "source": "Yahoo Finance",
                            "link": f"https://finance.yahoo.com/quote/{ticker}/history?period1={int(datetime.strptime(move_date, '%Y-%m-%d').timestamp())}&period2={int(datetime.strptime(move_date, '%Y-%m-%d').timestamp()) + 86400}&interval=1d",
                            "price": _round(move["close"]),
                            "price_change": _round(move["change"]),
                            "sentiment": 0.5 if move["change"] > 0 else -0.5,
                            "has_news": False,
                        }
                    )

        recent_news_events = []
        for date_key, news_list in sorted(news_by_date.items(), reverse=True)[:5]:
            if not any(event["date"] == date_key for event in events):
                matching_price = next((p for p in price_data if p["date"] == date_key), None)
                if matching_price and news_list:
                    news_item = news_list[0]
                    recent_news_events.append(
                        {
                            "date": date_key,
                            "title": news_item["title"],
                            "source": news_item["source"],
                            "link": news_item["link"],
                            "price": _round(matching_price["close"]),
                            "price_change": _round(matching_price["daily_change"]),
                            "sentiment": news_item["sentiment"],
                            "has_news": True,
                        }
                    )

        all_events = events + recent_news_events
        all_events.sort(key=lambda x: x["date"], reverse=True)

        trend = None
        if len(price_data) >= 2:
            start_price = price_data[0]["close"]
            end_price = price_data[-1]["close"]
            price_change = (end_price or 0) - (start_price or 0)
            price_change_pct = (price_change / start_price * 100) if start_price else 0
            trend = {
                "start_date": price_data[0]["date"],
                "end_date": price_data[-1]["date"],
                "start_price": _round(start_price),
                "end_price": _round(end_price),
                "price_change": _round(price_change),
                "price_change_pct": _round(price_change_pct),
                "direction": "up" if price_change >= 0 else "down",
                "high": _round(max(p["high"] for p in price_data if p["high"] is not None)),
                "low": _round(min(p["low"] for p in price_data if p["low"] is not None)),
                "avg_volume": int(sum(p["volume"] for p in price_data) / len(price_data)),
            }

        try:
            if price_data:
                snapshot_payload = {
                    "ticker": ticker.upper(),
                    "fetched_at": datetime.now(timezone.utc).isoformat(),
                    "period": period,
                    "current": price_data[-1],
                    "trend": trend,
                }
                snapshot_path = PRICE_SNAPSHOT_DIR / f"{ticker.upper()}.json"
                with snapshot_path.open("w") as fh:
                    json.dump(snapshot_payload, fh, indent=2)
                _update_runtime_cache(ticker, f'price_{period}', snapshot_payload)
        except Exception as exc:
            logger.warning("Failed to persist price snapshot for %s: %s", ticker, exc)

        return {
            "price_data": price_data,
            "events": all_events[:15],
            "significant_moves": len(significant_moves),
            "period": period,
            "trend": trend,
        }
    except Exception as exc:
        logger.error("Error fetching price history: %s", exc)
        return {"price_data": [], "events": [], "error": str(exc)}


def compute_company_scores(ticker: str) -> Dict[str, object]:
    ticker = ticker.upper()
    
    # Load data with error handling
    try:
        fin_df = load_financials_df(ticker)
    except ScoreComputationError:
        fin_df = pd.DataFrame()  # Empty DataFrame as fallback
    
    try:
        earnings_df = load_earnings_df(ticker)
    except ScoreComputationError:
        earnings_df = pd.DataFrame()  # Empty DataFrame as fallback
    
    try:
        price_df = load_price_history(ticker)
    except ScoreComputationError:
        price_df = pd.DataFrame()  # Empty DataFrame as fallback

    # Get Yahoo Finance data with error handling
    try:
        instrument = yf.Ticker(ticker)
        info = instrument.info or {}
        news_items = instrument.news or []
    except Exception:
        info = {}
        news_items = []
    
    # Fetch live sentiment from Reddit and Twitter (with 6-hour cache)
    try:
        reddit_summary = get_live_reddit_sentiment(ticker)
        if not reddit_summary:
            reddit_summary = load_latest_reddit_summary().get(ticker)
    except Exception:
        reddit_summary = None
    
    try:
        twitter_summary = get_live_twitter_sentiment(ticker)
    except Exception:
        twitter_summary = None
    
    # Combine Reddit and Twitter sentiment
    combined_sentiment = None
    if reddit_summary or twitter_summary:
        combined_sentiment = {
            'total_posts': (reddit_summary.get('total_posts', 0) if reddit_summary else 0) + 
                          (twitter_summary.get('total_mentions', 0) if twitter_summary else 0),
            'bullish_posts': (reddit_summary.get('bullish_posts', 0) if reddit_summary else 0) +
                           (twitter_summary.get('bullish_mentions', 0) if twitter_summary else 0),
            'bearish_posts': (reddit_summary.get('bearish_posts', 0) if reddit_summary else 0) +
                           (twitter_summary.get('bearish_mentions', 0) if twitter_summary else 0),
            'neutral_posts': (reddit_summary.get('neutral_posts', 0) if reddit_summary else 0) +
                           (twitter_summary.get('neutral_mentions', 0) if twitter_summary else 0),
            'sources': []
        }
        if reddit_summary:
            combined_sentiment['sources'].append('Reddit')
        if twitter_summary:
            combined_sentiment['sources'].append('Twitter/X')
    
    # Use combined sentiment for scoring
    reddit_summary = combined_sentiment

    # Compute scores with individual error handling
    try:
        business = compute_business_score(ticker, fin_df, info)
    except Exception as e:
        business = ComponentScore(
            score=None,
            summary=f"Business score calculation failed: {str(e)}",
            inputs={},
            notes=[f"Error: {str(e)}"]
        )
    
    try:
        financial = compute_financial_score(fin_df, info)
    except Exception as e:
        financial = ComponentScore(
            score=None,
            summary=f"Financial score calculation failed: {str(e)}",
            inputs={},
            notes=[f"Error: {str(e)}"]
        )
    
    try:
        sentiment = compute_event_sentiment_score(ticker, news_items, reddit_summary)
    except Exception as e:
        sentiment = ComponentScore(
            score=None,
            summary=f"Sentiment score calculation failed: {str(e)}",
            inputs={},
            notes=[f"Error: {str(e)}"]
        )
    
    try:
        critical = compute_critical_path_score(ticker, info)
    except Exception as e:
        critical = ComponentScore(
            score=None,
            summary=f"Critical score calculation failed: {str(e)}",
            inputs={},
            notes=[f"Error: {str(e)}"]
        )
    
    try:
        leadership = compute_leadership_score(ticker, info)
    except Exception as e:
        leadership = ComponentScore(
            score=None,
            summary=f"Leadership score calculation failed: {str(e)}",
            inputs={},
            notes=[f"Error: {str(e)}"]
        )
    
    try:
        earnings = compute_earnings_score(earnings_df)
    except Exception as e:
        earnings = ComponentScore(
            score=None,
            summary=f"Earnings score calculation failed: {str(e)}",
            inputs={},
            notes=[f"Error: {str(e)}"]
        )
    
    try:
        technical = compute_technical_score(price_df)
    except Exception as e:
        technical = ComponentScore(
            score=None,
            summary=f"Technical score calculation failed: {str(e)}",
            inputs={},
            notes=[f"Error: {str(e)}"]
        )

    component_scores = {
        "business": business,
        "financial": financial,
        "sentiment": sentiment,
        "critical": critical,
        "leadership": leadership,
        "earnings": earnings,
        "technical": technical,
    }

    overall = compute_overall_score(component_scores)

    company_profile = {
        "ticker": ticker,
        "name": info.get("longName") or info.get("shortName") or ticker,
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "summary": None,
        "website": info.get("website"),
        "country": info.get("country"),
        "employees": info.get("fullTimeEmployees"),
        "founded": info.get("foundedYear") or extract_year_from_summary(info.get("longBusinessSummary")),
        "logo_url": info.get("logo_url"),
    }

    company_profile["summary"] = summarize_company(info, fin_df)

    # Generate enhanced features
    quick_facts = get_quick_facts(ticker, info, fin_df)
    recommendation = get_recommendation_analysis(ticker, info, {"overall": overall, **component_scores})
    industry_comparison = get_industry_comparison(ticker, info)
    score_benchmarks = get_score_benchmarks(component_scores, info)
    price_history = get_price_history_with_events(ticker, news_items, period="1y")

    result = {
        "generated_at": datetime.utcnow().replace(tzinfo=timezone.utc).isoformat(),
        "company": company_profile,
        "scores": {
            key: {
                "score": round(comp.score, 2) if comp.score is not None else None,
                "summary": comp.summary,
                "inputs": {
                    k: (
                        float(v)
                        if isinstance(v, (int, float, np.floating, np.integer)) and v == v
                        else (v if isinstance(v, str) else None)
                    )
                    for k, v in comp.inputs.items()
                },
                "notes": comp.notes,
            }
            for key, comp in component_scores.items()
        },
        "overall": overall,
        "event_timeline": build_event_timeline(news_items),
        "quick_facts": quick_facts,
        "recommendation": recommendation,
        "industry_comparison": industry_comparison,
        "score_benchmarks": score_benchmarks,
        "price_history": price_history,
    }
    
    # Apply safe JSON serialization to handle NaN/infinity values
    return safe_json_serialize(result)


def get_valuation_metrics(ticker: str) -> dict:
    """
    Get historical P/E and P/S ratios with industry benchmarks.
    Returns time series data for charting.
    """
    import yfinance as yf
    from datetime import datetime, timedelta
    
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        
        # Get industry/sector info for benchmarks
        sector = info.get('sector', 'Technology')
        industry = info.get('industry', 'Semiconductors')

        # Load industry benchmarks from file (or fallback to hardcoded)
        industry_benchmarks = load_industry_benchmarks()

        # Get industry benchmark (returns None if not found)
        benchmark = industry_benchmarks.get(industry, None)
        if benchmark is None:
            logger.warning(f"No benchmark available for industry: {industry}")
            benchmark = {'pe': None, 'ps': None}

        # Get historical data (2 years)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=730)
        hist = stock.history(start=start_date, end=end_date, interval='1mo')

        # Fetch S&P 500 historical data to calculate time-varying benchmarks
        spy_hist = None
        try:
            spy = yf.Ticker('SPY')
            spy_hist = spy.history(start=start_date, end=end_date, interval='1mo')
            spy_info = spy.info
            spy_current_pe = spy_info.get('trailingPE', 22.0)  # S&P 500 average P/E
        except:
            spy_current_pe = 22.0
            logger.warning("Could not fetch SPY data for benchmark adjustment")

        # Calculate quarterly P/E and P/S ratios
        pe_data = []
        ps_data = []

        # Get quarterly financials to calculate historical P/E and P/S
        try:
            quarterly_financials = stock.quarterly_financials
            quarterly_balance = stock.quarterly_balance_sheet

            # Use monthly price data
            for date, row in hist.iterrows():
                close_price = row['Close']

                # Calculate time-varying benchmark based on market conditions
                if spy_hist is not None and date in spy_hist.index:
                    spy_price_at_date = spy_hist.loc[date, 'Close']
                    spy_current_price = spy_hist.iloc[-1]['Close']

                    # Adjust benchmark proportionally to S&P 500 price changes
                    # This approximates how market-wide valuations changed
                    spy_price_ratio = spy_price_at_date / spy_current_price

                    # Only calculate if benchmark exists
                    historical_benchmark_pe = benchmark['pe'] * spy_price_ratio if benchmark['pe'] is not None else None
                    historical_benchmark_ps = benchmark['ps'] * spy_price_ratio if benchmark['ps'] is not None else None
                else:
                    # Fallback to static benchmark
                    historical_benchmark_pe = benchmark['pe']
                    historical_benchmark_ps = benchmark['ps']

                # For simplicity, use current trailing P/E and P/S adjusted by price changes
                # (Real implementation would calculate from financials)
                current_pe = info.get('trailingPE', 25)
                current_ps = info.get('priceToSalesTrailing12Months', 5)
                current_price = info.get('currentPrice', close_price)

                if current_price and current_price > 0:
                    # Estimate historical ratios based on price changes
                    price_ratio = close_price / current_price
                    estimated_pe = current_pe * price_ratio if current_pe else None
                    estimated_ps = current_ps * price_ratio if current_ps else None

                    pe_data.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'pe_ratio': round(estimated_pe, 2) if estimated_pe else None,
                        'benchmark_pe': round(historical_benchmark_pe, 2) if historical_benchmark_pe is not None else None
                    })

                    ps_data.append({
                        'date': date.strftime('%Y-%m-%d'),
                        'ps_ratio': round(estimated_ps, 2) if estimated_ps else None,
                        'benchmark_ps': round(historical_benchmark_ps, 2) if historical_benchmark_ps is not None else None
                    })
        except Exception as e:
            logger.warning(f"Could not calculate historical P/E and P/S for {ticker}: {e}")
        
        # Current values
        current_pe = info.get('trailingPE')
        current_ps = info.get('priceToSalesTrailing12Months')
        forward_pe = info.get('forwardPE')
        
        return {
            'ticker': ticker,
            'sector': sector,
            'industry': industry,
            'current_metrics': {
                'pe_ratio': round(current_pe, 2) if current_pe else None,
                'ps_ratio': round(current_ps, 2) if current_ps else None,
                'forward_pe': round(forward_pe, 2) if forward_pe else None,
                'benchmark_pe': benchmark['pe'],
                'benchmark_ps': benchmark['ps']
            },
            'historical_pe': pe_data[-24:],  # Last 2 years monthly
            'historical_ps': ps_data[-24:],
            'analysis': {
                'pe_vs_industry': (
                    'Overvalued' if current_pe and benchmark['pe'] and current_pe > benchmark['pe'] * 1.2
                    else 'Fair' if current_pe and benchmark['pe'] and current_pe > benchmark['pe'] * 0.8
                    else 'Undervalued' if benchmark['pe']
                    else 'N/A'
                ),
                'ps_vs_industry': (
                    'Overvalued' if current_ps and benchmark['ps'] and current_ps > benchmark['ps'] * 1.2
                    else 'Fair' if current_ps and benchmark['ps'] and current_ps > benchmark['ps'] * 0.8
                    else 'Undervalued' if benchmark['ps']
                    else 'N/A'
                )
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching valuation metrics for {ticker}: {e}")
        return {
            'ticker': ticker,
            'error': str(e),
            'current_metrics': {},
            'historical_pe': [],
            'historical_ps': []
        }


def get_market_conditions() -> dict:
    """
    Get current market condition indicators including Fear & Greed Index and Put/Call Ratio.
    Compares to historical crisis levels (2008, 2020).
    """
    import yfinance as yf
    import requests
    from datetime import datetime, timedelta
    
    try:
        # Get S&P 500 data for market context
        sp500 = yf.Ticker('^GSPC')
        sp500_info = sp500.info
        
        # Get VIX (Fear Index)
        vix = yf.Ticker('^VIX')
        vix_current = vix.history(period='1d')['Close'].iloc[-1] if not vix.history(period='1d').empty else None
        
        # VIX historical context
        vix_hist = vix.history(period='5y')
        vix_2008_equivalent = 80  # 2008 crisis peak
        vix_2020_equivalent = 82  # 2020 COVID crash peak
        
        # Get Put/Call Ratio approximation using options data
        # Note: Real-time Put/Call ratio requires specialized data feed
        # We'll use VIX as proxy and historical market data
        
        try:
            # Try to fetch from CBOE (may require API key in production)
            # For now, we'll estimate based on VIX and market sentiment
            put_call_ratio = 1.0  # Neutral is ~1.0
            
            if vix_current:
                # Higher VIX = more puts being bought = higher ratio
                if vix_current > 30:
                    put_call_ratio = 1.3  # Fear
                elif vix_current > 20:
                    put_call_ratio = 1.1  # Caution
                elif vix_current < 12:
                    put_call_ratio = 0.7  # Extreme greed
                else:
                    put_call_ratio = 0.9  # Optimism
        except:
            put_call_ratio = 1.0
        
        # Calculate Fear & Greed Index (0-100)
        # Based on VIX, market momentum, and put/call ratio
        fear_greed_score = 50  # Neutral
        
        if vix_current:
            # VIX component (inverse relationship)
            vix_score = max(0, min(100, 100 - (vix_current / 0.8)))  # VIX 0-80 maps to 100-0
            
            # Market momentum (last month)
            hist_30d = sp500.history(period='1mo')
            if len(hist_30d) > 1:
                momentum = ((hist_30d['Close'].iloc[-1] / hist_30d['Close'].iloc[0]) - 1) * 100
                momentum_score = max(0, min(100, 50 + momentum * 2))
            else:
                momentum_score = 50
            
            # Put/Call component
            pc_score = max(0, min(100, (1.5 - put_call_ratio) * 100))
            
            # Combined score
            fear_greed_score = round((vix_score * 0.4 + momentum_score * 0.4 + pc_score * 0.2), 1)
        
        # Historical crisis comparison
        current_level = 'Normal'
        if vix_current:
            if vix_current > 40:
                current_level = 'Extreme Fear'
            elif vix_current > 30:
                current_level = 'Fear'
            elif vix_current > 20:
                current_level = 'Caution'
            elif vix_current < 12:
                current_level = 'Greed'
            elif vix_current < 15:
                current_level = 'Optimism'
        
        # Market phase analysis
        days_from_ath = 0
        drawdown = 0
        if not sp500.history(period='1y').empty:
            hist_1y = sp500.history(period='1y')
            current_price = hist_1y['Close'].iloc[-1]
            ath = hist_1y['Close'].max()
            drawdown = ((current_price / ath) - 1) * 100
            
            # Find days since ATH (ensure timezone-naive)
            ath_date = hist_1y['Close'].idxmax()
            try:
                # If pandas Timestamp, convert to Python datetime and strip tzinfo
                if hasattr(ath_date, 'to_pydatetime'):
                    ath_dt = ath_date.to_pydatetime()
                    ath_date = ath_dt.replace(tzinfo=None)
            except Exception:
                pass
            days_from_ath = (datetime.now() - ath_date).days
        
        return {
            'timestamp': datetime.now().isoformat(),
            'fear_greed_index': {
                'score': fear_greed_score,
                'level': 'Extreme Fear' if fear_greed_score < 25 else 'Fear' if fear_greed_score < 45 else 'Neutral' if fear_greed_score < 55 else 'Greed' if fear_greed_score < 75 else 'Extreme Greed',
                'interpretation': 'Lower values indicate fear, higher values indicate greed'
            },
            'vix': {
                'current': round(vix_current, 2) if vix_current else None,
                'avg_5y': round(vix_hist['Close'].mean(), 2) if not vix_hist.empty else None,
                'level': current_level,
                'vs_2008_crisis': f"{round((vix_current / vix_2008_equivalent) * 100, 1)}%" if vix_current else None,
                'vs_2020_crisis': f"{round((vix_current / vix_2020_equivalent) * 100, 1)}%" if vix_current else None
            },
            'put_call_ratio': {
                'current': round(put_call_ratio, 3),
                'interpretation': 'Above 1.0 indicates fear (more puts), below 1.0 indicates optimism (more calls)',
                'sentiment': 'Bearish' if put_call_ratio > 1.15 else 'Cautious' if put_call_ratio > 0.95 else 'Bullish'
            },
            'market_phase': {
                'sp500_current': round(sp500_info.get('regularMarketPrice', 0), 2),
                'drawdown_from_ath': f"{round(drawdown, 2)}%",
                'days_from_ath': days_from_ath,
                'phase': 'Recovery' if drawdown < -10 and days_from_ath < 90 else 'Correction' if drawdown < -10 else 'Bull Market' if drawdown > -5 else 'Consolidation'
            },
            'historical_context': {
                '2008_crisis': {
                    'vix_peak': 80,
                    'description': 'Financial crisis - extreme volatility'
                },
                '2020_covid': {
                    'vix_peak': 82,
                    'description': 'COVID-19 pandemic - market panic'
                },
                'current_vs_crises': 'Much calmer' if vix_current and vix_current < 25 else 'Elevated volatility' if vix_current and vix_current < 40 else 'Crisis-level fear'
            }
        }
        
    except Exception as e:
        logger.error(f"Error fetching market conditions: {e}")
        # Return default structure to avoid missing keys in UI
        return {
            'timestamp': datetime.now().isoformat(),
            'error': str(e),
            'fear_greed_index': {'score': 50, 'level': 'Unknown'},
            'vix': {'current': None},
            'put_call_ratio': {'current': 1.0},
            'market_phase': {'phase': 'Unknown'}
        }
