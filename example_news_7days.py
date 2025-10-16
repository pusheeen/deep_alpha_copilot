#!/usr/bin/env python3
"""
Example: Fetch ALL available news from the past 7 days for multiple companies.
Fetches as many articles as possible (no limits) within the 7-day window.
"""

import json
from datetime import datetime
from fetch_data import get_company_news

print("=" * 80)
print("FETCHING ALL NEWS FROM THE PAST 7 DAYS (UNLIMITED)")
print("=" * 80)
print()

# Fetch ALL news from past 7 days for multiple companies (no article limit)
tickers = ['NVDA', 'TSLA', 'AAPL', 'MSFT']
all_news = {}

for ticker in tickers:
    print(f"Fetching ALL {ticker} news from the past 7 days...")
    news = get_company_news(ticker, days=7)
    all_news[ticker] = news
    print(f"  ✅ Found {len(news)} articles\n")

# Save to JSON file
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = f"data/structured/news_7days_{timestamp}.json"

with open(output_file, 'w') as f:
    json.dump(all_news, f, indent=2)

print("=" * 80)
print(f"✅ News saved to: {output_file}")
print("=" * 80)
print()

# Display summary with dates
print("SUMMARY - NEWS FROM THE PAST 7 DAYS:")
print("-" * 80)
for ticker, news_list in all_news.items():
    print(f"\n{ticker} ({len(news_list)} articles):")
    for i, article in enumerate(news_list[:3], 1):  # Show first 3
        print(f"  {i}. {article['title'][:70]}...")
        print(f"     Published: {article['publish_time']}")
        print(f"     Publisher: {article['publisher']}")

print("\n" + "=" * 80)
print("✅ Complete!")
print("=" * 80)
