#!/usr/bin/env python3
"""Quick script to update news data for key tickers."""

from dotenv import load_dotenv
load_dotenv()

import sys
sys.path.insert(0, '.')

from fetch_data import fetch_all_news, TARGET_TICKERS
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

print("=" * 60)
print("Fetching latest news for all tickers")
print("=" * 60)
print(f"Tickers: {', '.join(TARGET_TICKERS)}")
print()

# Fetch news for the last 7 days
result = fetch_all_news(tickers=TARGET_TICKERS, days=7, filter_with_llm=True)

print()
print("=" * 60)
print("News fetch complete!")
print("=" * 60)
print(f"Success: {result['success_count']}/{result['total_tickers']}")
print()

if result['errors']:
    print("Errors encountered:")
    for error in result['errors']:
        print(f"  - {error}")
