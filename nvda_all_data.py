#!/usr/bin/env python3
"""
Complete comprehensive data for NVDA including:
- Company metrics
- News (past 7 days)
- X/Twitter data (example)
"""

import json
import os
import yfinance as yf
from datetime import datetime
from fetch_data import get_company_metrics, get_company_news

print("=" * 80)
print("COMPREHENSIVE DATA FETCH FOR NVDA")
print("=" * 80)
print()

ticker = "NVDA"

# 1. Fetch market benchmark
print("Fetching market data (SPY)...")
spy = yf.Ticker("SPY")
spy_hist = spy.history(period="1y")
market_prices = spy_hist['Close']
print("✅ Market data loaded\n")

# 2. Fetch company metrics
print("Fetching NVDA company metrics...")
metrics = get_company_metrics(ticker, market_prices)
print("✅ Company metrics loaded\n")

# 3. Fetch news from past 7 days
print("Fetching NVDA news from past 7 days...")
news = get_company_news(ticker, days=7)
print(f"✅ Found {len(news)} news articles\n")

# 4. Load X/Twitter data (if available)
x_data = None
x_file = "data/unstructured/x/NVDA_x_posts_EXAMPLE.json"
if os.path.exists(x_file):
    print("Loading X/Twitter data...")
    with open(x_file, 'r') as f:
        x_data = json.load(f)
    print(f"✅ Loaded {x_data['total_company_posts']} company posts and {x_data['total_ceo_posts']} CEO posts\n")

# 5. Compile comprehensive data
comprehensive_data = {
    'timestamp': datetime.now().isoformat(),
    'ticker': ticker,

    'company_info': {
        'sector': metrics.get('sector'),
        'industry': metrics.get('industry'),
        'market_cap': metrics.get('market_cap')
    },

    'financial_metrics': {
        'profitability': {
            'roe': metrics.get('roe'),
            'roa': metrics.get('roa'),
            'roic': metrics.get('roic'),
            'net_margin': metrics.get('net_margin'),
            'gross_margin': metrics.get('gross_margin')
        },
        'growth': {
            'cagr': metrics.get('cagr'),
            'momentum_1m': metrics.get('momentum_1m'),
            'momentum_3m': metrics.get('momentum_3m'),
            'momentum_6m': metrics.get('momentum_6m'),
            'momentum_1y': metrics.get('momentum_1y')
        },
        'valuation': {
            'pe_ratio': metrics.get('pe_ratio'),
            'ps_ratio': metrics.get('ps_ratio'),
            'pb_ratio': metrics.get('pb_ratio')
        },
        'risk': {
            'beta': metrics.get('beta'),
            'volatility': metrics.get('volatility'),
            'sharpe_ratio': metrics.get('sharpe_ratio')
        },
        'financial_health': {
            'debt_to_equity': metrics.get('debt_to_equity'),
            'current_ratio': metrics.get('current_ratio'),
            'quick_ratio': metrics.get('quick_ratio'),
            'interest_coverage': metrics.get('interest_coverage')
        }
    },

    'news_past_7_days': news,

    'x_twitter_data': x_data if x_data else {
        'note': 'X/Twitter API credentials required for live data. See .env-example'
    }
}

# 6. Save to file
output_file = f"data/structured/nvda_comprehensive_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, 'w') as f:
    json.dump(comprehensive_data, f, indent=2)

print("=" * 80)
print("COMPREHENSIVE DATA SUMMARY FOR NVDA")
print("=" * 80)
print()

print(f"Company: {metrics.get('sector')} - {metrics.get('industry')}")
print(f"Market Cap: ${metrics.get('market_cap'):,.0f}" if metrics.get('market_cap') else "Market Cap: N/A")
print()

print("📊 FINANCIAL METRICS")
print("-" * 80)
print(f"ROE:          {metrics.get('roe'):.2f}%" if metrics.get('roe') else "ROE: N/A")
print(f"Net Margin:   {metrics.get('net_margin'):.2f}%" if metrics.get('net_margin') else "Net Margin: N/A")
print(f"CAGR (1Y):    {metrics.get('cagr'):.2f}%" if metrics.get('cagr') else "CAGR: N/A")
print(f"P/E Ratio:    {metrics.get('pe_ratio'):.2f}" if metrics.get('pe_ratio') else "P/E Ratio: N/A")
print(f"Beta:         {metrics.get('beta'):.2f}" if metrics.get('beta') else "Beta: N/A")
print()

print(f"📰 NEWS (Past 7 Days): {len(news)} articles")
print("-" * 80)
for i, article in enumerate(news[:3], 1):
    print(f"{i}. {article['title'][:70]}...")
    print(f"   {article['publisher']} | {article['publish_time']}")
if len(news) > 3:
    print(f"   ... and {len(news) - 3} more articles")
print()

if x_data:
    print(f"🐦 X/TWITTER DATA: {x_data['total_company_posts'] + x_data['total_ceo_posts']} posts")
    print("-" * 80)

    # Sentiment analysis
    all_posts = x_data['company_posts'] + x_data['ceo_posts']
    bullish = sum(1 for p in all_posts if p['sentiment'] == 'bullish')
    bearish = sum(1 for p in all_posts if p['sentiment'] == 'bearish')

    print(f"Sentiment: {bullish} bullish, {bearish} bearish")
    print(f"Average Score: {sum(p['compound_score'] for p in all_posts) / len(all_posts):.2f}")
    print(f"Total Engagement: {sum(p['like_count'] for p in all_posts):,} likes, {sum(p['retweet_count'] for p in all_posts):,} retweets")
    print()

    print("Top posts:")
    for i, post in enumerate(sorted(x_data['company_posts'], key=lambda x: x['like_count'], reverse=True)[:2], 1):
        print(f"{i}. {post['text'][:70]}...")
        print(f"   Sentiment: {post['sentiment']} | {post['like_count']} likes")
    print()

print("=" * 80)
print("DATA SAVED")
print("=" * 80)
print(f"✅ Comprehensive data saved to: {output_file}")
print()
print("File contains:")
print("  ✓ Company information (sector, industry, market cap)")
print("  ✓ Complete financial metrics (profitability, growth, valuation, risk, health)")
print(f"  ✓ News articles from past 7 days ({len(news)} articles)")
if x_data:
    print(f"  ✓ X/Twitter data ({x_data['total_company_posts']} company posts, {x_data['total_ceo_posts']} CEO posts)")
    print("    - Post text and engagement metrics")
    print("    - Sentiment analysis (bullish/bearish/neutral)")
    print("    - Topics extracted (AI, earnings, news, etc.)")
else:
    print("  ⚠ X/Twitter data: Example data only (configure API for live data)")
print()
print("=" * 80)
