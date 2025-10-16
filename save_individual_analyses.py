#!/usr/bin/env python3
"""
Save individual company vs sector analysis files for NVDA and TSLA.
"""

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
    SECTOR_METRICS_DIR,
)

print("=" * 80)
print("GENERATING INDIVIDUAL COMPANY ANALYSIS FILES")
print("=" * 80)
print()

# Fetch market benchmark
print("Fetching SPY benchmark...")
spy = yf.Ticker("SPY")
spy_hist = spy.history(period="1y")
market_prices = spy_hist['Close']
print("✅\n")

# Fetch metrics - include peer companies for sector context
print("Fetching company metrics...")
target_tickers = ['NVDA', 'TSLA']
peer_tickers = ['AAPL', 'MSFT', 'GOOGL', 'AMD', 'F', 'GM']

all_metrics = []
for ticker in target_tickers + peer_tickers:
    print(f"  {ticker}...", end=' ')
    metrics = get_company_metrics(ticker, market_prices)
    all_metrics.append(metrics)
    metrics['is_target'] = ticker in target_tickers
    print(f"✅")

metrics_df = pd.DataFrame(all_metrics)
print(f"\n✅ Loaded {len(all_metrics)} companies\n")

# Calculate sector stats
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
        'companies_in_sector': [m['ticker'] for m in all_metrics if m['sector'] == sector],
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

# Calculate momentum and correlation
print("Calculating sector analytics...")
sector_sentiment = {}  # Skip for speed
sector_momentum = calculate_sector_momentum_with_sentiment(sector_stats, sector_sentiment)
correlation_analysis = calculate_sector_correlations_and_strength(metrics_df, market_prices)
print("✅\n")

# Generate individual files for each target company
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

for target_ticker in target_tickers:
    # Find the company metrics
    company_metrics = next((m for m in all_metrics if m['ticker'] == target_ticker), None)

    if not company_metrics:
        print(f"⚠️  Could not find metrics for {target_ticker}")
        continue

    sector = company_metrics['sector']

    if sector not in sector_stats:
        print(f"⚠️  Sector not found for {target_ticker}")
        continue

    # Get comparison
    comparison = compare_company_to_sector(company_metrics, sector_stats[sector])

    # Build individual company file
    company_file = {
        'analysis_timestamp': datetime.now().isoformat(),
        'company': {
            'ticker': target_ticker,
            'sector': sector,
            'industry': company_metrics.get('industry'),

            'metrics': {
                'profitability': {
                    'roe': company_metrics.get('roe'),
                    'roa': company_metrics.get('roa'),
                    'roic': company_metrics.get('roic'),
                    'net_margin': company_metrics.get('net_margin'),
                    'gross_margin': company_metrics.get('gross_margin')
                },
                'growth': {
                    'cagr': company_metrics.get('cagr'),
                    'momentum_1m': company_metrics.get('momentum_1m'),
                    'momentum_3m': company_metrics.get('momentum_3m'),
                    'momentum_6m': company_metrics.get('momentum_6m'),
                    'momentum_1y': company_metrics.get('momentum_1y')
                },
                'valuation': {
                    'pe_ratio': company_metrics.get('pe_ratio'),
                    'ps_ratio': company_metrics.get('ps_ratio'),
                    'pb_ratio': company_metrics.get('pb_ratio'),
                    'market_cap': company_metrics.get('market_cap')
                },
                'risk': {
                    'beta': company_metrics.get('beta'),
                    'volatility': company_metrics.get('volatility'),
                    'sharpe_ratio': company_metrics.get('sharpe_ratio')
                },
                'financial_health': {
                    'debt_to_equity': company_metrics.get('debt_to_equity'),
                    'current_ratio': company_metrics.get('current_ratio'),
                    'quick_ratio': company_metrics.get('quick_ratio'),
                    'interest_coverage': company_metrics.get('interest_coverage')
                }
            }
        },

        'sector_benchmarks': {
            'sector_name': sector,
            'num_companies': sector_stats[sector]['num_companies'],
            'companies': sector_stats[sector]['companies_in_sector'],
            'quality_score': sector_stats[sector]['quality_score'],

            'averages': {
                'profitability': {
                    'avg_roe': sector_stats[sector]['avg_roe'],
                    'avg_roa': sector_stats[sector]['avg_roa'],
                    'avg_roic': sector_stats[sector]['avg_roic'],
                    'avg_net_margin': sector_stats[sector]['avg_net_margin'],
                    'avg_gross_margin': sector_stats[sector]['avg_gross_margin']
                },
                'growth': {
                    'avg_cagr': sector_stats[sector]['avg_cagr'],
                    'avg_momentum_1m': sector_stats[sector]['avg_momentum_1m'],
                    'avg_momentum_3m': sector_stats[sector]['avg_momentum_3m'],
                    'avg_momentum_6m': sector_stats[sector]['avg_momentum_6m'],
                    'avg_momentum_1y': sector_stats[sector]['avg_momentum_1y']
                },
                'valuation': {
                    'avg_pe_ratio': sector_stats[sector]['avg_pe_ratio'],
                    'avg_ps_ratio': sector_stats[sector]['avg_ps_ratio'],
                    'avg_pb_ratio': sector_stats[sector]['avg_pb_ratio']
                },
                'risk': {
                    'avg_beta': sector_stats[sector]['avg_beta'],
                    'avg_volatility': sector_stats[sector]['avg_volatility'],
                    'avg_sharpe_ratio': sector_stats[sector]['avg_sharpe_ratio']
                },
                'financial_health': {
                    'avg_debt_to_equity': sector_stats[sector]['avg_debt_to_equity'],
                    'avg_current_ratio': sector_stats[sector]['avg_current_ratio']
                }
            }
        },

        'company_vs_sector': {
            'classification': comparison['classification'],
            'relative_performance_score': comparison['relative_performance_score'],

            'detailed_comparisons': comparison['comparisons'],

            'strengths': comparison['strengths'],
            'weaknesses': comparison['weaknesses'],
            'outliers': comparison['outliers'],

            'summary': {
                'total_metrics_compared': len(comparison['comparisons']),
                'num_strengths': len(comparison['strengths']),
                'num_weaknesses': len(comparison['weaknesses']),
                'num_outliers': len(comparison['outliers'])
            }
        },

        'sector_momentum': sector_momentum.get(sector, {}),

        'sector_relative_strength': correlation_analysis['relative_strength'].get(sector, {})
    }

    # Save file
    output_file = os.path.join(SECTOR_METRICS_DIR, f"{target_ticker}_vs_sector_{timestamp}.json")

    with open(output_file, 'w') as f:
        json.dump(company_file, f, indent=2)

    print(f"✅ {target_ticker} analysis saved to:")
    print(f"   {output_file}")
    print(f"   Classification: {comparison['classification']}")
    print(f"   Performance Score: {comparison['relative_performance_score']:.1f}/100")
    print(f"   Strengths: {len(comparison['strengths'])}, Weaknesses: {len(comparison['weaknesses'])}")
    print()

print("=" * 80)
print("COMPLETE - Individual analysis files saved")
print("=" * 80)
