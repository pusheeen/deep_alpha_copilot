#!/usr/bin/env python3
"""
Test script to calculate sector metrics for a small subset of companies.
"""

import os
import json
import pandas as pd
from datetime import datetime
from fetch_data import (
    get_company_metrics,
    calculate_rsi,
    calculate_macd,
    calculate_cagr,
    calculate_volatility,
    calculate_beta,
    calculate_sharpe_ratio,
    calculate_momentum_score,
    calculate_sector_quality_score,
    SECTOR_METRICS_DIR,
    logger
)
import yfinance as yf

# Test with a small set of well-known companies
TEST_COMPANIES = [
    {'ticker': 'AAPL', 'name': 'Apple Inc.'},
    {'ticker': 'MSFT', 'name': 'Microsoft Corporation'},
    {'ticker': 'GOOGL', 'name': 'Alphabet Inc.'},
    {'ticker': 'NVDA', 'name': 'NVIDIA Corporation'},
    {'ticker': 'TSLA', 'name': 'Tesla, Inc.'},
    {'ticker': 'JPM', 'name': 'JPMorgan Chase & Co.'},
    {'ticker': 'JNJ', 'name': 'Johnson & Johnson'},
    {'ticker': 'WMT', 'name': 'Walmart Inc.'},
    {'ticker': 'PG', 'name': 'Procter & Gamble Company'},
    {'ticker': 'V', 'name': 'Visa Inc.'}
]

def test_sector_metrics():
    """Test sector metrics calculation with a small dataset."""

    print("=" * 80)
    print("TESTING ENHANCED SECTOR METRICS CALCULATION")
    print("=" * 80)
    print()
    print(f"Testing with {len(TEST_COMPANIES)} companies")
    print()

    # Fetch market benchmark for beta calculations
    print("Fetching market benchmark (SPY)...")
    market_prices = None
    try:
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1y")
        if not spy_hist.empty and 'Close' in spy_hist.columns:
            market_prices = spy_hist['Close']
            print("✅ Market benchmark loaded")
    except Exception as e:
        print(f"⚠️ Could not fetch market benchmark: {e}")
    print()

    # Collect metrics
    all_metrics = []

    for company in TEST_COMPANIES:
        ticker = company['ticker']
        print(f"Fetching metrics for {ticker} ({company['name']})...")

        metrics = get_company_metrics(ticker, market_prices)
        all_metrics.append(metrics)

        # Display sample with new metrics
        print(f"  Sector: {metrics.get('sector', 'N/A')}")
        print(f"  Industry: {metrics.get('industry', 'N/A')}")
        print()
        print("  Profitability:")
        print(f"    Revenue: ${metrics.get('revenue', 0):,.0f}" if metrics.get('revenue') else "    Revenue: N/A")
        print(f"    Gross Margin: {metrics.get('gross_margin', 0):.2f}%" if metrics.get('gross_margin') else "    Gross Margin: N/A")
        print(f"    Net Margin: {metrics.get('net_margin', 0):.2f}%" if metrics.get('net_margin') else "    Net Margin: N/A")
        print(f"    ROE: {metrics.get('roe', 0):.2f}%" if metrics.get('roe') else "    ROE: N/A")
        print(f"    ROA: {metrics.get('roa', 0):.2f}%" if metrics.get('roa') else "    ROA: N/A")
        print(f"    ROIC: {metrics.get('roic', 0):.2f}%" if metrics.get('roic') else "    ROIC: N/A")
        print()
        print("  Valuation:")
        print(f"    P/E Ratio: {metrics.get('pe_ratio', 0):.2f}" if metrics.get('pe_ratio') else "    P/E Ratio: N/A")
        print(f"    P/S Ratio: {metrics.get('ps_ratio', 0):.2f}" if metrics.get('ps_ratio') else "    P/S Ratio: N/A")
        print(f"    P/B Ratio: {metrics.get('pb_ratio', 0):.2f}" if metrics.get('pb_ratio') else "    P/B Ratio: N/A")
        print()
        print("  Performance:")
        print(f"    CAGR: {metrics.get('cagr', 0):.2f}%" if metrics.get('cagr') else "    CAGR: N/A")
        print(f"    1M Momentum: {metrics.get('momentum_1m', 0):.2f}%" if metrics.get('momentum_1m') else "    1M Momentum: N/A")
        print(f"    3M Momentum: {metrics.get('momentum_3m', 0):.2f}%" if metrics.get('momentum_3m') else "    3M Momentum: N/A")
        print()
        print("  Risk:")
        print(f"    Beta: {metrics.get('beta', 0):.2f}" if metrics.get('beta') else "    Beta: N/A")
        print(f"    Volatility: {metrics.get('volatility', 0):.2f}%" if metrics.get('volatility') else "    Volatility: N/A")
        print(f"    Sharpe Ratio: {metrics.get('sharpe_ratio', 0):.2f}" if metrics.get('sharpe_ratio') else "    Sharpe Ratio: N/A")
        print()
        print("  Financial Health:")
        print(f"    Debt/Equity: {metrics.get('debt_to_equity', 0):.2f}" if metrics.get('debt_to_equity') else "    Debt/Equity: N/A")
        print(f"    Current Ratio: {metrics.get('current_ratio', 0):.2f}" if metrics.get('current_ratio') else "    Current Ratio: N/A")
        print(f"    Quick Ratio: {metrics.get('quick_ratio', 0):.2f}" if metrics.get('quick_ratio') else "    Quick Ratio: N/A")
        print()

    # Convert to DataFrame
    metrics_df = pd.DataFrame(all_metrics)

    # Remove unknown sectors
    metrics_df = metrics_df[metrics_df['sector'] != 'Unknown']
    metrics_df = metrics_df[metrics_df['sector'].notna()]

    print("=" * 80)
    print("SECTOR AGGREGATION")
    print("=" * 80)
    print()

    # Group by sector
    sector_stats = {}

    for sector in metrics_df['sector'].unique():
        sector_data = metrics_df[metrics_df['sector'] == sector]

        # Helper functions
        def safe_mean(series):
            clean = series.dropna()
            return float(clean.mean()) if len(clean) > 0 else None

        def safe_sum(series):
            clean = series.dropna()
            return float(clean.sum()) if len(clean) > 0 else None

        sector_stats[sector] = {
            'num_companies': len(sector_data),
            'avg_cagr': safe_mean(sector_data['cagr']),
            'avg_gross_margin': safe_mean(sector_data['gross_margin']),
            'avg_net_margin': safe_mean(sector_data['net_margin']),
            'avg_roe': safe_mean(sector_data['roe']),
            'avg_roa': safe_mean(sector_data['roa']),
            'avg_roic': safe_mean(sector_data['roic']),
            'avg_eps': safe_mean(sector_data['eps']),
            'total_revenue': safe_sum(sector_data['revenue']),
            'avg_revenue': safe_mean(sector_data['revenue']),
            'avg_rsi': safe_mean(sector_data['rsi']),
            'avg_pe_ratio': safe_mean(sector_data['pe_ratio']),
            'avg_ps_ratio': safe_mean(sector_data['ps_ratio']),
            'avg_pb_ratio': safe_mean(sector_data['pb_ratio']),
            'avg_beta': safe_mean(sector_data['beta']),
            'avg_volatility': safe_mean(sector_data['volatility']),
            'avg_sharpe_ratio': safe_mean(sector_data['sharpe_ratio']),
            'avg_momentum_3m': safe_mean(sector_data['momentum_3m']),
            'avg_debt_to_equity': safe_mean(sector_data['debt_to_equity']),
            'avg_current_ratio': safe_mean(sector_data['current_ratio']),
            'total_market_cap': safe_sum(sector_data['market_cap']),
            'quality_score': calculate_sector_quality_score(sector_data)
        }

    # Display sector stats (sorted by quality score)
    for sector, stats in sorted(sector_stats.items(), key=lambda x: x[1].get('quality_score', 0), reverse=True):
        print(f"\n📊 {sector.upper()}")
        print(f"   Companies: {stats['num_companies']}")
        print(f"   Quality Score: {stats['quality_score']:.1f}/100" if stats['quality_score'] else "   Quality Score: N/A")
        print()
        print("   Profitability:")
        print(f"     ROE: {stats['avg_roe']:.2f}%" if stats['avg_roe'] else "     ROE: N/A")
        print(f"     ROA: {stats['avg_roa']:.2f}%" if stats['avg_roa'] else "     ROA: N/A")
        print(f"     ROIC: {stats['avg_roic']:.2f}%" if stats['avg_roic'] else "     ROIC: N/A")
        print(f"     Net Margin: {stats['avg_net_margin']:.2f}%" if stats['avg_net_margin'] else "     Net Margin: N/A")
        print()
        print("   Growth:")
        print(f"     CAGR: {stats['avg_cagr']:.2f}%" if stats['avg_cagr'] else "     CAGR: N/A")
        print(f"     3M Momentum: {stats['avg_momentum_3m']:.2f}%" if stats['avg_momentum_3m'] else "     3M Momentum: N/A")
        print()
        print("   Valuation:")
        print(f"     P/E: {stats['avg_pe_ratio']:.2f}" if stats['avg_pe_ratio'] else "     P/E: N/A")
        print(f"     P/S: {stats['avg_ps_ratio']:.2f}" if stats['avg_ps_ratio'] else "     P/S: N/A")
        print(f"     P/B: {stats['avg_pb_ratio']:.2f}" if stats['avg_pb_ratio'] else "     P/B: N/A")
        print()
        print("   Financial Health:")
        print(f"     Debt/Equity: {stats['avg_debt_to_equity']:.2f}" if stats['avg_debt_to_equity'] else "     Debt/Equity: N/A")
        print(f"     Current Ratio: {stats['avg_current_ratio']:.2f}" if stats['avg_current_ratio'] else "     Current Ratio: N/A")
        print()
        print("   Risk:")
        print(f"     Beta: {stats['avg_beta']:.2f}" if stats['avg_beta'] else "     Beta: N/A")
        print(f"     Volatility: {stats['avg_volatility']:.2f}%" if stats['avg_volatility'] else "     Volatility: N/A")
        print(f"     Sharpe Ratio: {stats['avg_sharpe_ratio']:.2f}" if stats['avg_sharpe_ratio'] else "     Sharpe Ratio: N/A")
        print()
        print(f"   Total Revenue: ${stats['total_revenue']:,.0f}" if stats['total_revenue'] else "   Total Revenue: N/A")
        print(f"   Total Market Cap: ${stats['total_market_cap']:,.0f}" if stats['total_market_cap'] else "   Total Market Cap: N/A")

    # Save test results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_file = os.path.join(SECTOR_METRICS_DIR, f"test_sector_metrics_{timestamp}.json")

    test_summary = {
        'test_timestamp': datetime.now().isoformat(),
        'test_companies': TEST_COMPANIES,
        'company_metrics': all_metrics,
        'sector_stats': sector_stats
    }

    with open(test_file, 'w') as f:
        json.dump(test_summary, f, indent=2)

    print()
    print("=" * 80)
    print("TEST COMPLETED")
    print("=" * 80)
    print(f"✅ Results saved to: {test_file}")
    print()

if __name__ == "__main__":
    test_sector_metrics()
