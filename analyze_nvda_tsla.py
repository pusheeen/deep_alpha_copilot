#!/usr/bin/env python3
"""
Focused analysis of NVDA and TSLA with comprehensive sector metrics.
"""

import pandas as pd
import yfinance as yf
from fetch_data import (
    get_company_metrics,
    aggregate_sector_sentiment,
    compare_company_to_sector,
    calculate_sector_momentum_with_sentiment,
    calculate_sector_correlations_and_strength,
    calculate_sector_quality_score,
)

def analyze_nvda_tsla():
    print("=" * 80)
    print("NVDA & TSLA COMPREHENSIVE SECTOR ANALYSIS")
    print("=" * 80)
    print()

    # Fetch market benchmark
    print("Fetching market benchmark (SPY)...")
    spy = yf.Ticker("SPY")
    spy_hist = spy.history(period="1y")
    market_prices = spy_hist['Close']
    print("✅ Market benchmark loaded\n")

    # Fetch metrics for NVDA and TSLA
    tickers = ['NVDA', 'TSLA']
    all_metrics = []

    for ticker in tickers:
        print(f"Fetching comprehensive metrics for {ticker}...")
        metrics = get_company_metrics(ticker, market_prices)
        all_metrics.append(metrics)
        print(f"✅ {ticker} - Sector: {metrics['sector']}\n")

    # Create DataFrame
    metrics_df = pd.DataFrame(all_metrics)

    # Calculate sector aggregates
    print("=" * 80)
    print("CALCULATING SECTOR METRICS")
    print("=" * 80)
    print()

    sector_stats = {}
    for sector in metrics_df['sector'].unique():
        if sector == 'Unknown' or pd.isna(sector):
            continue

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
            'avg_gross_margin': safe_mean(sector_data['gross_margin']),
            'avg_cagr': safe_mean(sector_data['cagr']),
            'avg_momentum_1m': safe_mean(sector_data['momentum_1m']),
            'avg_momentum_3m': safe_mean(sector_data['momentum_3m']),
            'avg_momentum_6m': safe_mean(sector_data['momentum_6m']),
            'avg_momentum_1y': safe_mean(sector_data['momentum_1y']),
            'avg_pe_ratio': safe_mean(sector_data['pe_ratio']),
            'avg_ps_ratio': safe_mean(sector_data['ps_ratio']),
            'avg_pb_ratio': safe_mean(sector_data['pb_ratio']),
            'avg_volatility': safe_mean(sector_data['volatility']),
            'avg_beta': safe_mean(sector_data['beta']),
            'avg_sharpe_ratio': safe_mean(sector_data['sharpe_ratio']),
            'avg_debt_to_equity': safe_mean(sector_data['debt_to_equity']),
            'avg_current_ratio': safe_mean(sector_data['current_ratio']),
            'quality_score': calculate_sector_quality_score(sector_data)
        }

    # Display individual company metrics
    for metrics in all_metrics:
        ticker = metrics['ticker']
        sector = metrics['sector']

        print(f"\n{'=' * 80}")
        print(f"{ticker} - {metrics.get('industry', 'N/A')}")
        print(f"Sector: {sector}")
        print("=" * 80)

        print("\n📊 PROFITABILITY:")
        print(f"  ROE:          {metrics['roe']:.2f}%" if metrics['roe'] else "  ROE:          N/A")
        print(f"  ROA:          {metrics['roa']:.2f}%" if metrics['roa'] else "  ROA:          N/A")
        print(f"  ROIC:         {metrics['roic']:.2f}%" if metrics['roic'] else "  ROIC:         N/A")
        print(f"  Net Margin:   {metrics['net_margin']:.2f}%" if metrics['net_margin'] else "  Net Margin:   N/A")
        print(f"  Gross Margin: {metrics['gross_margin']:.2f}%" if metrics['gross_margin'] else "  Gross Margin: N/A")

        print("\n📈 GROWTH & MOMENTUM:")
        print(f"  CAGR:         {metrics['cagr']:.2f}%" if metrics['cagr'] else "  CAGR:         N/A")
        print(f"  1M Momentum:  {metrics['momentum_1m']:.2f}%" if metrics['momentum_1m'] else "  1M Momentum:  N/A")
        print(f"  3M Momentum:  {metrics['momentum_3m']:.2f}%" if metrics['momentum_3m'] else "  3M Momentum:  N/A")
        print(f"  6M Momentum:  {metrics['momentum_6m']:.2f}%" if metrics['momentum_6m'] else "  6M Momentum:  N/A")
        print(f"  1Y Momentum:  {metrics['momentum_1y']:.2f}%" if metrics['momentum_1y'] else "  1Y Momentum:  N/A")

        print("\n💰 VALUATION:")
        print(f"  P/E Ratio:    {metrics['pe_ratio']:.2f}" if metrics['pe_ratio'] else "  P/E Ratio:    N/A")
        print(f"  P/S Ratio:    {metrics['ps_ratio']:.2f}" if metrics['ps_ratio'] else "  P/S Ratio:    N/A")
        print(f"  P/B Ratio:    {metrics['pb_ratio']:.2f}" if metrics['pb_ratio'] else "  P/B Ratio:    N/A")

        print("\n⚠️  RISK METRICS:")
        print(f"  Beta:         {metrics['beta']:.2f}" if metrics['beta'] else "  Beta:         N/A")
        print(f"  Volatility:   {metrics['volatility']:.2f}%" if metrics['volatility'] else "  Volatility:   N/A")
        print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}" if metrics['sharpe_ratio'] else "  Sharpe Ratio: N/A")

        print("\n💪 FINANCIAL HEALTH:")
        print(f"  Debt/Equity:  {metrics['debt_to_equity']:.2f}" if metrics['debt_to_equity'] else "  Debt/Equity:  N/A")
        print(f"  Current:      {metrics['current_ratio']:.2f}" if metrics['current_ratio'] else "  Current:      N/A")
        print(f"  Quick Ratio:  {metrics['quick_ratio']:.2f}" if metrics['quick_ratio'] else "  Quick Ratio:  N/A")

    # Sector sentiment analysis
    print("\n\n" + "=" * 80)
    print("SECTOR SENTIMENT ANALYSIS (from X/Twitter)")
    print("=" * 80)
    sector_sentiment = aggregate_sector_sentiment()

    if sector_sentiment:
        for sector in metrics_df['sector'].unique():
            if sector in sector_sentiment:
                sent = sector_sentiment[sector]
                print(f"\n{sector}:")
                print(f"  Total Posts:      {sent['total_posts']}")
                print(f"  Net Sentiment:    {sent['net_sentiment']:.1f}%")
                print(f"  Bullish:          {sent['bullish_pct']:.1f}%")
                print(f"  Bearish:          {sent['bearish_pct']:.1f}%")
                print(f"  Neutral:          {sent['neutral_pct']:.1f}%")
                print(f"  Compound Score:   {sent['avg_compound_score']:.3f}")
    else:
        print("\n⚠️  No X/Twitter sentiment data available")

    # Company-to-sector comparisons
    print("\n\n" + "=" * 80)
    print("COMPANY VS SECTOR COMPARISON")
    print("=" * 80)

    for metrics in all_metrics:
        ticker = metrics['ticker']
        sector = metrics['sector']

        if sector in sector_stats:
            comparison = compare_company_to_sector(metrics, sector_stats[sector])

            print(f"\n{'─' * 80}")
            print(f"{ticker} vs {sector} Sector")
            print(f"{'─' * 80}")
            print(f"  Classification:      {comparison['classification']}")
            print(f"  Performance Score:   {comparison['relative_performance_score']:.1f}/100")

            if comparison['strengths']:
                print(f"\n  ✅ STRENGTHS (>20% above sector):")
                for strength in comparison['strengths'][:5]:
                    comp = comparison['comparisons'][strength]
                    print(f"     {strength:20s}: {comp['company_value']:>10.2f} vs {comp['sector_avg']:>10.2f} ({comp['pct_difference']:>+6.1f}%)")

            if comparison['weaknesses']:
                print(f"\n  ❌ WEAKNESSES (>20% below sector):")
                for weakness in comparison['weaknesses'][:5]:
                    comp = comparison['comparisons'][weakness]
                    print(f"     {weakness:20s}: {comp['company_value']:>10.2f} vs {comp['sector_avg']:>10.2f} ({comp['pct_difference']:>+6.1f}%)")

    # Sector momentum analysis
    print("\n\n" + "=" * 80)
    print("SECTOR MOMENTUM SIGNALS")
    print("=" * 80)

    sector_momentum = calculate_sector_momentum_with_sentiment(sector_stats, sector_sentiment)

    for sector, mom in sector_momentum.items():
        print(f"\n{sector}:")
        print(f"  Combined Momentum:   {mom['combined_momentum_score']:.2f}%")
        print(f"  Signal:              {mom['signal']}")
        print(f"  Trend:               {mom['momentum_trend']}")
        print(f"  3M Price Momentum:   {mom['price_momentum_3m']:.2f}%" if mom['price_momentum_3m'] else "  3M Price Momentum:   N/A")
        if mom['sentiment_score'] is not None:
            print(f"  Sentiment:           {mom['sentiment_score']:.3f}")

    # Correlation and relative strength
    print("\n\n" + "=" * 80)
    print("SECTOR RELATIVE STRENGTH (vs SPY)")
    print("=" * 80)

    correlation_analysis = calculate_sector_correlations_and_strength(metrics_df, market_prices)

    if correlation_analysis['relative_strength']:
        for sector, rs in correlation_analysis['relative_strength'].items():
            print(f"\n{sector}:")
            print(f"  Composite RS:        {rs['composite_rs']:.2f}%")
            print(f"  Classification:      {rs['classification']}")
            if 'rs_3m' in rs:
                print(f"  3M RS:               {rs['rs_3m']:.2f}%")
            if 'rs_6m' in rs:
                print(f"  6M RS:               {rs['rs_6m']:.2f}%")
            if 'rs_1y' in rs:
                print(f"  1Y RS:               {rs['rs_1y']:.2f}%")

    # Sector quality scores
    print("\n\n" + "=" * 80)
    print("SECTOR QUALITY SCORES")
    print("=" * 80)

    for sector, stats in sector_stats.items():
        print(f"\n{sector}:")
        print(f"  Quality Score:       {stats['quality_score']:.1f}/100")
        print(f"  Companies Analyzed:  {stats['num_companies']}")

    print("\n\n" + "=" * 80)
    print("ANALYSIS COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    analyze_nvda_tsla()
