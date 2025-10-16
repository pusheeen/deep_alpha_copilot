#!/usr/bin/env python3
"""
Example: Fetch and save ALL available company news using the get_company_news function.
"""

import json
from datetime import datetime
from fetch_data import get_company_news

print("=" * 80)
print("EXAMPLE: FETCHING ALL AVAILABLE COMPANY NEWS")
print("=" * 80)
print()

# Fetch ALL available news for multiple companies
tickers = ['NVDA', 'TSLA', 'AAPL']
all_news = {}

for ticker in tickers:
    print(f"Fetching all available news for {ticker}...")
    news = get_company_news(ticker)
    all_news[ticker] = news
    print(f"  ✅ Found {len(news)} articles\n")

# Save to JSON file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"data/structured/company_news_{timestamp}.json"

with open(output_file, 'w') as f:
    json.dump(all_news, f, indent=2)

print("=" * 80)
print(f"✅ News saved to: {output_file}")
print("=" * 80)
print()

# Display summary
print("SUMMARY:")
print("-" * 80)
for ticker, news_list in all_news.items():
    print(f"\n{ticker}:")
    for i, article in enumerate(news_list[:3], 1):  # Show first 3
        print(f"  {i}. {article['title']}")
        print(f"     Publisher: {article['publisher']} | {article['content_type']}")

print("\n" + "=" * 80)
