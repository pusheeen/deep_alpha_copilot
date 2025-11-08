import os
import logging
import time
from functools import wraps
from pathlib import Path
from typing import Callable

from target_tickers import TARGET_TICKERS

logger = logging.getLogger(__name__)

SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Your Name your.email@provider.com")

def get_data_root() -> Path:
    if data_root_env := os.getenv("DATA_ROOT"):
        return Path(data_root_env)
    if os.getenv("K_SERVICE"):
        return Path("/tmp/data")
    if Path("/app/data").exists():
        return Path("/app/data")
    return Path(__file__).parent.parent / "data"

DATA_ROOT = get_data_root()
DATA_DIR = str(DATA_ROOT)
COMPANIES_CSV_PATH = str(DATA_ROOT / "companies.csv")
FINANCIALS_DIR = str(DATA_ROOT / "structured" / "financials")
PRICES_DIR = str(DATA_ROOT / "structured" / "prices")
FILINGS_10K_DIR = str(DATA_ROOT / "unstructured" / "10k")
CEO_REPORTS_DIR = str(DATA_ROOT / "reports")
REDDIT_DATA_DIR = str(DATA_ROOT / "unstructured" / "reddit")
X_DATA_DIR = str(DATA_ROOT / "unstructured" / "x")
YOUTUBE_DATA_DIR = str(DATA_ROOT / "youtube")
NEWS_DATA_DIR = str(DATA_ROOT / "unstructured" / "news")
NEWS_INTERPRETATION_DIR = str(DATA_ROOT / "unstructured" / "news_interpretation")
EARNINGS_DIR = str(DATA_ROOT / "structured" / "earnings")
SECTOR_METRICS_DIR = str(DATA_ROOT / "structured" / "sector_metrics")
MARKET_INDEX_DIR = os.path.join(DATA_DIR, 'market_index')
CEO_PROFILE_DIR = os.path.join(DATA_DIR, 'ceo_profiles')
FLOW_DATA_DIR = str(DATA_ROOT / "structured" / "flow_data")


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        ticker = args[0] if args else "unknown"
                        logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}({ticker}): {str(e)}")
                        logger.info(f"Retrying in {current_delay:.1f} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}({ticker if 'ticker' in locals() else 'unknown'}): {str(e)}")

            return None

        return wrapper
    return decorator
