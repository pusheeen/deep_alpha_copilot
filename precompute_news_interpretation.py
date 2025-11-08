#!/usr/bin/env python3
"""Script to precompute news fetch and AI interpretation for target tickers."""
import os

from target_tickers import TARGET_TICKERS
from fetch_data.news import fetch_news_for_ticker, interpret_news_with_gemini
from fetch_data.utils import NEWS_DATA_DIR, NEWS_INTERPRETATION_DIR

def main():
    os.makedirs(NEWS_DATA_DIR, exist_ok=True)
    os.makedirs(NEWS_INTERPRETATION_DIR, exist_ok=True)
    for ticker in TARGET_TICKERS:
        ticker = ticker.upper()
        print(f"--- Precomputing news for {ticker} ---")
        try:
            # Fetch and cache news articles
            articles = fetch_news_for_ticker(ticker, ticker)
            if not articles:
                print(f"No articles returned for {ticker}")
                continue
            # Interpret with Gemini and cache
            result = interpret_news_with_gemini(ticker, ticker, articles)
            if result:
                print(f"✅ AI interpretation cached for {ticker}")
            else:
                print(f"⚠️ No interpretation result for {ticker}")
        except Exception as e:
            print(f"Error processing {ticker}: {e}")

if __name__ == "__main__":
    main()