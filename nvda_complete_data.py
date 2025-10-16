#!/usr/bin/env python3
"""
Complete data fetch demonstration for NVDA.
Shows all available data including the new news function.
"""

import json
import yfinance as yf
from datetime import datetime
from fetch_data import get_company_metrics, get_company_news

print("=" * 80)
print("COMPLETE DATA FETCH FOR NVDA")
print("=" * 80)
print()

ticker = "NVDA"

# 1. Fetch market benchmark (SPY) for metrics calculation
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

# 4. Compile complete data
complete_data = {
    'timestamp': datetime.now().isoformat(),
    'ticker': ticker,

    'company_info': {
        'sector': metrics.get('sector'),
        'industry': metrics.get('industry'),
        'market_cap': metrics.get('market_cap')
    },

    'metrics': {
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

    'news_past_7_days': news
}

# 5. Save to file
output_file = f"data/structured/nvda_complete_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, 'w') as f:
    json.dump(complete_data, f, indent=2)

print("=" * 80)
print("NVDA DATA SUMMARY")
print("=" * 80)
print()

print(f"Company: {metrics.get('sector')} - {metrics.get('industry')}")
print(f"Market Cap: ${metrics.get('market_cap'):,.0f}" if metrics.get('market_cap') else "Market Cap: N/A")
print()

print("PROFITABILITY:")
print(f"  ROE:          {metrics.get('roe'):.2f}%" if metrics.get('roe') else "  ROE: N/A")
print(f"  ROA:          {metrics.get('roa'):.2f}%" if metrics.get('roa') else "  ROA: N/A")
print(f"  Net Margin:   {metrics.get('net_margin'):.2f}%" if metrics.get('net_margin') else "  Net Margin: N/A")
print(f"  Gross Margin: {metrics.get('gross_margin'):.2f}%" if metrics.get('gross_margin') else "  Gross Margin: N/A")
print()

print("GROWTH:")
print(f"  CAGR (1Y):    {metrics.get('cagr'):.2f}%" if metrics.get('cagr') else "  CAGR: N/A")
print(f"  1M Momentum:  {metrics.get('momentum_1m'):.2f}%" if metrics.get('momentum_1m') else "  1M Momentum: N/A")
print(f"  3M Momentum:  {metrics.get('momentum_3m'):.2f}%" if metrics.get('momentum_3m') else "  3M Momentum: N/A")
print(f"  6M Momentum:  {metrics.get('momentum_6m'):.2f}%" if metrics.get('momentum_6m') else "  6M Momentum: N/A")
print()

print("VALUATION:")
print(f"  P/E Ratio:    {metrics.get('pe_ratio'):.2f}" if metrics.get('pe_ratio') else "  P/E Ratio: N/A")
print(f"  P/S Ratio:    {metrics.get('ps_ratio'):.2f}" if metrics.get('ps_ratio') else "  P/S Ratio: N/A")
print(f"  P/B Ratio:    {metrics.get('pb_ratio'):.2f}" if metrics.get('pb_ratio') else "  P/B Ratio: N/A")
print()

print("RISK:")
print(f"  Beta:         {metrics.get('beta'):.2f}" if metrics.get('beta') else "  Beta: N/A")
print(f"  Volatility:   {metrics.get('volatility'):.2f}%" if metrics.get('volatility') else "  Volatility: N/A")
print(f"  Sharpe Ratio: {metrics.get('sharpe_ratio'):.2f}" if metrics.get('sharpe_ratio') else "  Sharpe Ratio: N/A")
print()

print("FINANCIAL HEALTH:")
print(f"  Debt/Equity:  {metrics.get('debt_to_equity'):.2f}" if metrics.get('debt_to_equity') else "  Debt/Equity: N/A")
print(f"  Current:      {metrics.get('current_ratio'):.2f}" if metrics.get('current_ratio') else "  Current: N/A")
print(f"  Quick Ratio:  {metrics.get('quick_ratio'):.2f}" if metrics.get('quick_ratio') else "  Quick Ratio: N/A")
print()

print("=" * 80)
print(f"NEWS FROM PAST 7 DAYS ({len(news)} articles)")
print("=" * 80)
print()

for i, article in enumerate(news, 1):
    print(f"{i}. {article['title']}")
    print(f"   Publisher: {article['publisher']}")
    print(f"   Published: {article['publish_time']}")
    print(f"   Type: {article['content_type']}")
    print(f"   Link: {article['link']}")

    # Show summary if available
    if article.get('summary'):
        summary = article['summary'][:150] + "..." if len(article['summary']) > 150 else article['summary']
        print(f"   Summary: {summary}")
    print()

print("=" * 80)
print("DATA SAVED")
print("=" * 80)
print(f"✅ Complete data saved to: {output_file}")
print()
print("File contains:")
print("  - Company information")
print("  - Complete financial metrics")
print("  - News from past 7 days")
print()
print("=" * 80)
