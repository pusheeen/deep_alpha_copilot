import os
import json
import logging
import re
import requests
import yfinance as yf
from datetime import datetime
from typing import Dict, Any
from .utils import retry_on_failure, MARKET_INDEX_DIR

logger = logging.getLogger(__name__)

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_cboe_put_call_ratio() -> Any:
    """Fetches the CBOE total put/call ratio."""
    logger.info("Fetching CBOE put/call ratio...")
    fmp_key = os.getenv("FMP_API_KEY")
    if fmp_key:
        url = f"https://financialmodelingprep.com/api/v3/put-call-ratio?apikey={fmp_key}"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            output_path = os.path.join(MARKET_INDEX_DIR, "put_call_ratio.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved put/call ratio to {output_path}")
            return data
        except Exception as e:
            logger.error(f"Error fetching put/call ratio from FMP: {e}")

    fred_key = os.getenv("FRED_API_KEY")
    if fred_key:
        series_id = "PC1"
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_key}&file_type=json"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            output_path = os.path.join(MARKET_INDEX_DIR, "put_call_ratio.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved put/call ratio to {output_path}")
            return data
        except Exception as e:
            logger.error(f"Error fetching put/call ratio from FRED: {e}")

    try:
        logger.info("Falling back to scraping Yahoo Finance for ^PCR")
        y_url = "https://finance.yahoo.com/quote/%5EPCR"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(y_url, headers=headers, timeout=10)
        resp.raise_for_status()
        match = re.search(r'"regularMarketPrice":{"raw":([0-9\.]+)}', resp.text)
        if match:
            price = float(match.group(1))
            data = {
                "symbol": "^PCR",
                "put_call_ratio": price,
                "fetch_timestamp": datetime.now().isoformat()
            }
            output_path = os.path.join(MARKET_INDEX_DIR, "put_call_ratio.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved put/call ratio (scraped) to {output_path}")
            return data
        else:
            logger.error("Could not parse put/call ratio from Yahoo Finance HTML.")
    except Exception as e:
        logger.error(f"Error scraping Yahoo Finance for put/call ratio: {e}")

    logger.error("Unable to fetch put/call ratio via FMP, FRED, or Yahoo Finance.")
    return None

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_market_indices() -> Dict[str, Any]:
    """Fetches major market indices."""
    indices = {
        "vix": "^VIX",
        "nasdaq": "^IXIC",
        "dowjones": "^DJI",
        "russell2000": "^RUT",
    }
    results: Dict[str, Any] = {}
    for name, ticker in indices.items():
        logger.info(f"Fetching market index {name} ({ticker})...")
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5y")
            data = []
            if hist is not None and not hist.empty:
                df = hist.reset_index()
                df['Date'] = df['Date'].dt.strftime("%Y-%m-%d")
                data = df.to_dict(orient="records")
            output_path = os.path.join(MARKET_INDEX_DIR, f"{name}.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved {name} data to {output_path}")
            results[name] = data
        except Exception as e:
            logger.error(f"Error fetching {name} ({ticker}): {e}")
            results[name] = None

    put_call_data = fetch_cboe_put_call_ratio()
    results["put_call_ratio"] = put_call_data
    return results
