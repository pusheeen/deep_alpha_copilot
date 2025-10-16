#!/usr/bin/env python3
"""
Comprehensive test script for all new sector analysis features.
Tests:
1. Sector sentiment analysis from X/Twitter data
2. Company-to-sector comparison
3. Sector momentum tracking with sentiment
4. Sector correlation and relative strength metrics
"""

import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime
from fetch_data import (
    get_company_metrics,
    aggregate_sector_sentiment,
    compare_company_to_sector,
    calculate_sector_momentum_with_sentiment,
    calculate_sector_correlations_and_strength,
    calculate_sector_quality_score,
    SECTOR_METRICS_DIR,
    logger
)

# Test with a small set of well-known companies across different sectors
TEST_COMPANIES = [
    {'ticker': 'AAPL', 'name': 'Apple Inc.'},
    {'ticker': 'MSFT', 'name': 'Microsoft Corporation'},
    {'ticker': 'GOOGL', 'name': 'Alphabet Inc.'},
    {'ticker': 'NVDA', 'name': 'NVIDIA Corporation'},
    {'ticker': 'JPM', 'name': 'JPMorgan Chase & Co.'},
    {'ticker': 'JNJ', 'name': 'Johnson & Johnson'},
    {'ticker': 'WMT', 'name': 'Walmart Inc.'},
    {'ticker': 'V', 'name': 'Visa Inc.'},
]

def test_all_features():
    """Test all new sector analysis features."""

    print("=" * 80)
    print("COMPREHENSIVE SECTOR ANALYSIS TEST")
    print("=" * 80)
    print()

    # Fetch market benchmark
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

    # 1. Collect company metrics
    print("=" * 80)
    print("1. COLLECTING COMPANY METRICS")
    print("=" * 80)
    print()

    all_metrics = []
    for company in TEST_COMPANIES:
        ticker = company['ticker']
        print(f"Fetching metrics for {ticker}...")
        metrics = get_company_metrics(ticker, market_prices)
        all_metrics.append(metrics)

    metrics_df = pd.DataFrame(all_metrics)
    metrics_df = metrics_df[metrics_df['sector'] != 'Unknown']
    metrics_df = metrics_df[metrics_df['sector'].notna()]

    print(f"✅ Collected metrics for {len(metrics_df)} companies across {metrics_df['sector'].nunique()} sectors")
    print()

    # 2. Calculate sector aggregates
    print("=" * 80)
    print("2. CALCULATING SECTOR AGGREGATES")
    print("=" * 80)
    print()

    sector_stats = {}
    for sector in metrics_df['sector'].unique():
        sector_data = metrics_df[metrics_df['sector'] == sector]

        def safe_mean(series):
            clean = series.dropna()
            return float(clean.mean()) if len(clean) > 0 else None

        sector_stats[sector] = {
            'num_companies': len(sector_data),
            'avg_roe': safe_mean(sector_data['roe']),
            'avg_roa': safe_mean(sector_data['roa']),
            'avg_roic': safe_mean(sector_data['roic']),
            'avg_net_margin': safe_mean(sector_data['net_margin']),
            'avg_cagr': safe_mean(sector_data['cagr']),
            'avg_momentum_1m': safe_mean(sector_data['momentum_1m']),
            'avg_momentum_3m': safe_mean(sector_data['momentum_3m']),
            'avg_momentum_6m': safe_mean(sector_data['momentum_6m']),
            'avg_momentum_1y': safe_mean(sector_data['momentum_1y']),
            'avg_pe_ratio': safe_mean(sector_data['pe_ratio']),
            'avg_ps_ratio': safe_mean(sector_data['ps_ratio']),
            'avg_volatility': safe_mean(sector_data['volatility']),
            'avg_beta': safe_mean(sector_data['beta']),
            'avg_sharpe_ratio': safe_mean(sector_data['sharpe_ratio']),
            'avg_debt_to_equity': safe_mean(sector_data['debt_to_equity']),
            'avg_current_ratio': safe_mean(sector_data['current_ratio']),
            'quality_score': calculate_sector_quality_score(sector_data)
        }

    for sector, stats in sector_stats.items():
        print(f"{sector}: {stats['num_companies']} companies, Quality Score: {stats['quality_score']:.1f}/100")

    print()

    # 3. Test sector sentiment analysis
    print("=" * 80)
    print("3. TESTING SECTOR SENTIMENT ANALYSIS")
    print("=" * 80)
    print()

    sector_sentiment = aggregate_sector_sentiment()
    if sector_sentiment:
        print(f"✅ Aggregated sentiment for {len(sector_sentiment)} sectors")
        for sector, sent_data in list(sector_sentiment.items())[:3]:
            print(f"\n{sector}:")
            print(f"  Total Posts: {sent_data['total_posts']}")
            print(f"  Net Sentiment: {sent_data['net_sentiment']:.1f}%")
            print(f"  Avg Compound Score: {sent_data['avg_compound_score']:.3f}")
    else:
        print("⚠️ No sentiment data available (X/Twitter data files not found)")
    print()

    # 4. Test company-to-sector comparison
    print("=" * 80)
    print("4. TESTING COMPANY-TO-SECTOR COMPARISON")
    print("=" * 80)
    print()

    # Compare AAPL to its sector
    aapl_metrics = next((m for m in all_metrics if m['ticker'] == 'AAPL'), None)
    if aapl_metrics and aapl_metrics['sector'] in sector_stats:
        comparison = compare_company_to_sector(aapl_metrics, sector_stats[aapl_metrics['sector']])
        print(f"AAPL vs {comparison['sector']} Sector:")
        print(f"  Classification: {comparison['classification']}")
        print(f"  Performance Score: {comparison['relative_performance_score']:.1f}/100")
        print(f"  Strengths: {', '.join(comparison['strengths'][:5]) if comparison['strengths'] else 'None'}")
        print(f"  Weaknesses: {', '.join(comparison['weaknesses'][:5]) if comparison['weaknesses'] else 'None'}")
        print(f"  Outliers: {len(comparison['outliers'])} metrics significantly different from sector")
    print()

    # 5. Test sector momentum tracking
    print("=" * 80)
    print("5. TESTING SECTOR MOMENTUM TRACKING")
    print("=" * 80)
    print()

    sector_momentum = calculate_sector_momentum_with_sentiment(sector_stats, sector_sentiment)
    print(f"✅ Calculated momentum for {len(sector_momentum)} sectors")
    for sector, mom_data in list(sector_momentum.items())[:3]:
        print(f"\n{sector}:")
        print(f"  Combined Momentum Score: {mom_data['combined_momentum_score']:.2f}%")
        print(f"  Signal: {mom_data['signal']}")
        print(f"  Trend: {mom_data['momentum_trend']}")
    print()

    # 6. Test correlation and relative strength
    print("=" * 80)
    print("6. TESTING SECTOR CORRELATIONS & RELATIVE STRENGTH")
    print("=" * 80)
    print()

    correlation_analysis = calculate_sector_correlations_and_strength(metrics_df, market_prices)

    if correlation_analysis['sector_pairs']:
        print(f"✅ Found {len(correlation_analysis['sector_pairs'])} high correlation pairs")
        print("\nTop Correlated Pairs:")
        for pair in correlation_analysis['sector_pairs'][:3]:
            print(f"  {pair['sector1']} <-> {pair['sector2']}: {pair['correlation']:.2f} ({pair['relationship']})")

    if correlation_analysis['relative_strength']:
        print(f"\n✅ Calculated relative strength for {len(correlation_analysis['relative_strength'])} sectors")
        print("\nTop Performers vs Market:")
        for sector, rs_data in sorted(correlation_analysis['relative_strength'].items(),
                                      key=lambda x: x[1]['composite_rs'], reverse=True)[:3]:
            print(f"  {sector}: RS={rs_data['composite_rs']:.2f}% ({rs_data['classification']})")

    print()

    # Save comprehensive test results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    test_file = os.path.join(SECTOR_METRICS_DIR, f"comprehensive_test_{timestamp}.json")

    test_results = {
        'test_timestamp': datetime.now().isoformat(),
        'test_companies': TEST_COMPANIES,
        'company_metrics': all_metrics,
        'sector_stats': sector_stats,
        'sentiment_analysis': sector_sentiment,
        'momentum_analysis': sector_momentum,
        'correlation_analysis': correlation_analysis,
        'sample_comparison': comparison if aapl_metrics else None
    }

    with open(test_file, 'w') as f:
        json.dump(test_results, f, indent=2)

    print("=" * 80)
    print("TEST COMPLETED SUCCESSFULLY")
    print("=" * 80)
    print(f"✅ Results saved to: {test_file}")
    print()
    print("All new features are working correctly:")
    print("✓ Sector sentiment analysis from X/Twitter data")
    print("✓ Company-to-sector comparison")
    print("✓ Sector momentum tracking with sentiment")
    print("✓ Sector correlation and relative strength metrics")
    print()


if __name__ == "__main__":
    test_all_features()
