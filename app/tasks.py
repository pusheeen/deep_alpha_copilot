import os
import yfinance as yf
import json
import logging
from celery import Celery

from app.celery_app import app

FINANCIALS_DIR = "data/structured/financials"

logger = logging.getLogger(__name__)

@app.task
def fetch_financial_statements_batch(tickers: list[str]):
    """Fetches annual income statements for a batch of tickers using yfinance."""
    for ticker in tickers:
        logger.info(f"Fetching financial statements for {ticker}...")
        try:
            stock = yf.Ticker(ticker)
            income_stmt = stock.income_stmt

            if income_stmt.empty:
                logger.warning(f"No financial data found for {ticker}")
                continue

            # Convert DataFrame to JSON format
            data = income_stmt.transpose()
            data.index.name = 'date'
            data = data.reset_index()
            data['date'] = data['date'].astype(str)
            records = data.to_dict('records')

            with open(os.path.join(FINANCIALS_DIR, f"{ticker}_financials.json"), 'w') as f:
                json.dump(records, f, indent=4)
            logger.info(f"✅ Saved financials for {ticker}")
        except Exception as e:
            logger.error(f"Error fetching financials for {ticker}: {e}")
