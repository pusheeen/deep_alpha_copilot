import os
import logging
import yfinance as yf
from .utils import retry_on_failure, PRICES_DIR

logger = logging.getLogger(__name__)

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_stock_prices(ticker: str):
    """Fetches the maximum available daily stock prices using yfinance."""
    logger.info(f"Fetching stock prices for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="max")

        if hist.empty:
            logger.warning(f"No price data found for {ticker}")
            return

        hist.to_csv(os.path.join(PRICES_DIR, f"{ticker}_prices.csv"))
        logger.info(f"✅ Saved prices for {ticker}")
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")
