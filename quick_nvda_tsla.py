#!/usr/bin/env python3
"""Quick analysis of NVDA and TSLA."""

import os
import json
import pandas as pd
import yfinance as yf
from datetime import datetime
from fetch_data import (
    get_company_metrics,
    compare_company_to_sector,
    calculate_sector_quality_score,
    calculate_sector_momentum_with_sentiment,
    calculate_sector_correlations_and_strength,
    aggregate_sector_sentiment,
    SECTOR_METRICS_DIR,
)

print("=" * 80)
print("NVDA & TSLA SECTOR ANALYSIS")
print("=" * 80)
print()

# Fetch market benchmark
print("Fetching SPY benchmark...")
spy = yf.Ticker("SPY")
spy_hist = spy.history(period="1y")
market_prices = spy_hist['Close']
print("✅\n")

# Fetch metrics - include peer companies for meaningful sector comparisons
print("Fetching company metrics (including sector peers for comparison)...")
target_tickers = ['NVDA', 'TSLA']
peer_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMD', 'F', 'GM']  # Tech and auto peers

all_metrics = []
for ticker in target_tickers + peer_tickers:
    print(f"  {ticker}...", end=' ')
    metrics = get_company_metrics(ticker, market_prices)
    all_metrics.append(metrics)
    metrics['is_target'] = ticker in target_tickers
    print(f"✅ {metrics['sector']}")

metrics_df = pd.DataFrame(all_metrics)

# Calculate sector stats
sector_stats = {}
for sector in metrics_df['sector'].unique():
    if pd.isna(sector) or sector == 'Unknown':
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
        'avg_momentum_3m': safe_mean(sector_data['momentum_3m']),
        'avg_pe_ratio': safe_mean(sector_data['pe_ratio']),
        'avg_volatility': safe_mean(sector_data['volatility']),
        'avg_beta': safe_mean(sector_data['beta']),
        'avg_sharpe_ratio': safe_mean(sector_data['sharpe_ratio']),
        'avg_debt_to_equity': safe_mean(sector_data['debt_to_equity']),
        'avg_current_ratio': safe_mean(sector_data['current_ratio']),
        'quality_score': calculate_sector_quality_score(sector_data)
    }

print(f"\n✅ Loaded {len(all_metrics)} companies\n")

# Display results for target companies only
for metrics in all_metrics:
    if not metrics.get('is_target'):
        continue
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
    print(f"  CAGR (1Y):    {metrics['cagr']:.2f}%" if metrics['cagr'] else "  CAGR (1Y):    N/A")
    print(f"  1M Momentum:  {metrics['momentum_1m']:.2f}%" if metrics['momentum_1m'] else "  1M Momentum:  N/A")
    print(f"  3M Momentum:  {metrics['momentum_3m']:.2f}%" if metrics['momentum_3m'] else "  3M Momentum:  N/A")
    print(f"  6M Momentum:  {metrics['momentum_6m']:.2f}%" if metrics['momentum_6m'] else "  6M Momentum:  N/A")

    print("\n💰 VALUATION:")
    print(f"  P/E Ratio:    {metrics['pe_ratio']:.2f}" if metrics['pe_ratio'] else "  P/E Ratio:    N/A")
    print(f"  P/S Ratio:    {metrics['ps_ratio']:.2f}" if metrics['ps_ratio'] else "  P/S Ratio:    N/A")
    print(f"  P/B Ratio:    {metrics['pb_ratio']:.2f}" if metrics['pb_ratio'] else "  P/B Ratio:    N/A")

    print("\n⚠️  RISK:")
    print(f"  Beta:         {metrics['beta']:.2f}" if metrics['beta'] else "  Beta:         N/A")
    print(f"  Volatility:   {metrics['volatility']:.2f}%" if metrics['volatility'] else "  Volatility:   N/A")
    print(f"  Sharpe Ratio: {metrics['sharpe_ratio']:.2f}" if metrics['sharpe_ratio'] else "  Sharpe Ratio: N/A")

    print("\n💪 FINANCIAL HEALTH:")
    print(f"  Debt/Equity:  {metrics['debt_to_equity']:.2f}" if metrics['debt_to_equity'] else "  Debt/Equity:  N/A")
    print(f"  Current:      {metrics['current_ratio']:.2f}" if metrics['current_ratio'] else "  Current:      N/A")
    print(f"  Quick Ratio:  {metrics['quick_ratio']:.2f}" if metrics['quick_ratio'] else "  Quick Ratio:  N/A")

# Comparisons
print("\n\n" + "=" * 80)
print("COMPANY VS SECTOR COMPARISON")
print("=" * 80)

for metrics in all_metrics:
    if not metrics.get('is_target'):
        continue

    ticker = metrics['ticker']
    sector = metrics['sector']

    if sector in sector_stats:
        # Show sector peer companies
        peer_companies = [m['ticker'] for m in all_metrics if m['sector'] == sector and m['ticker'] != ticker]
        if peer_companies:
            print(f"\n  📊 {sector} Sector Peers: {', '.join(peer_companies)}")
            print(f"     (Comparison based on {len(peer_companies) + 1} companies)")
            print()
        comparison = compare_company_to_sector(metrics, sector_stats[sector])

        print(f"\n{'─' * 80}")
        print(f"{ticker} vs {sector} Sector")
        print(f"{'─' * 80}")
        print(f"  Classification:      {comparison['classification']}")
        print(f"  Performance Score:   {comparison['relative_performance_score']:.1f}/100")

        if comparison['strengths']:
            print(f"\n  ✅ STRENGTHS (>20% above sector):")
            for strength in comparison['strengths'][:5]:
                if strength in comparison['comparisons']:
                    comp = comparison['comparisons'][strength]
                    print(f"     {strength:20s}: {comp['company_value']:>10.2f} vs sector {comp['sector_avg']:>10.2f} ({comp['pct_difference']:>+6.1f}%)")

        if comparison['weaknesses']:
            print(f"\n  ❌ WEAKNESSES (>20% below sector):")
            for weakness in comparison['weaknesses'][:5]:
                if weakness in comparison['comparisons']:
                    comp = comparison['comparisons'][weakness]
                    print(f"     {weakness:20s}: {comp['company_value']:>10.2f} vs sector {comp['sector_avg']:>10.2f} ({comp['pct_difference']:>+6.1f}%)")

# Sector summary
print("\n\n" + "=" * 80)
print("SECTOR METRICS SUMMARY")
print("=" * 80)

for sector, stats in sector_stats.items():
    companies_in_sector = [m['ticker'] for m in all_metrics if m['sector'] == sector]
    print(f"\n{sector} Sector ({stats['num_companies']} companies):")
    print(f"  Companies: {', '.join(companies_in_sector)}")
    print(f"  Quality Score:       {stats['quality_score']:.1f}/100")
    print(f"  Avg ROE:             {stats['avg_roe']:.2f}%" if stats['avg_roe'] else "  Avg ROE:             N/A")
    print(f"  Avg Net Margin:      {stats['avg_net_margin']:.2f}%" if stats['avg_net_margin'] else "  Avg Net Margin:      N/A")
    print(f"  Avg 3M Momentum:     {stats['avg_momentum_3m']:.2f}%" if stats['avg_momentum_3m'] else "  Avg 3M Momentum:     N/A")
    print(f"  Avg Beta:            {stats['avg_beta']:.2f}" if stats['avg_beta'] else "  Avg Beta:            N/A")
    print(f"  Avg Volatility:      {stats['avg_volatility']:.2f}%" if stats['avg_volatility'] else "  Avg Volatility:      N/A")
    print(f"  Avg P/E Ratio:       {stats['avg_pe_ratio']:.2f}" if stats['avg_pe_ratio'] else "  Avg P/E Ratio:       N/A")

# Calculate additional analytics (skip slow sentiment aggregation for now)
print("\nCalculating momentum and correlation analysis...")
sector_sentiment = {}  # Skip sentiment for speed
sector_momentum = calculate_sector_momentum_with_sentiment(sector_stats, sector_sentiment)
correlation_analysis = calculate_sector_correlations_and_strength(metrics_df, market_prices)
print("✅ Analytics complete\n")

# Prepare comparisons for both target companies
comparisons = {}
for metrics in all_metrics:
    if metrics.get('is_target') and metrics['sector'] in sector_stats:
        ticker = metrics['ticker']
        comparisons[ticker] = compare_company_to_sector(metrics, sector_stats[metrics['sector']])

# Save comprehensive results
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
output_file = os.path.join(SECTOR_METRICS_DIR, f"nvda_tsla_analysis_{timestamp}.json")

results = {
    'analysis_timestamp': datetime.now().isoformat(),
    'target_companies': target_tickers,
    'peer_companies': peer_tickers,
    'total_companies_analyzed': len(all_metrics),

    'company_metrics': {
        m['ticker']: {
            'ticker': m['ticker'],
            'sector': m['sector'],
            'industry': m.get('industry'),
            'is_target': m.get('is_target', False),
            'profitability': {
                'roe': m.get('roe'),
                'roa': m.get('roa'),
                'roic': m.get('roic'),
                'net_margin': m.get('net_margin'),
                'gross_margin': m.get('gross_margin')
            },
            'growth': {
                'cagr': m.get('cagr'),
                'momentum_1m': m.get('momentum_1m'),
                'momentum_3m': m.get('momentum_3m'),
                'momentum_6m': m.get('momentum_6m'),
                'momentum_1y': m.get('momentum_1y')
            },
            'valuation': {
                'pe_ratio': m.get('pe_ratio'),
                'ps_ratio': m.get('ps_ratio'),
                'pb_ratio': m.get('pb_ratio')
            },
            'risk': {
                'beta': m.get('beta'),
                'volatility': m.get('volatility'),
                'sharpe_ratio': m.get('sharpe_ratio')
            },
            'financial_health': {
                'debt_to_equity': m.get('debt_to_equity'),
                'current_ratio': m.get('current_ratio'),
                'quick_ratio': m.get('quick_ratio'),
                'interest_coverage': m.get('interest_coverage')
            }
        } for m in all_metrics
    },

    'sector_stats': sector_stats,

    'company_vs_sector_comparisons': comparisons,

    'sentiment_analysis': sector_sentiment,

    'momentum_analysis': sector_momentum,

    'correlation_analysis': correlation_analysis
}

with open(output_file, 'w') as f:
    json.dump(results, f, indent=2)

print("\n" + "=" * 80)
print("DATA SAVED")
print("=" * 80)
print(f"\n✅ Comprehensive analysis saved to:")
print(f"   {output_file}")
print(f"\n📊 File contains:")
print(f"   - Individual metrics for {len(all_metrics)} companies")
print(f"   - Sector statistics for {len(sector_stats)} sectors")
print(f"   - Company vs sector comparisons for {len(comparisons)} target companies")
print(f"   - Sentiment analysis for {len(sector_sentiment)} sectors")
print(f"   - Momentum signals for {len(sector_momentum)} sectors")
print(f"   - Correlation matrix and relative strength analysis")

print("\n" + "=" * 80)
