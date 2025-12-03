#!/usr/bin/env python3
"""
Comprehensive verification script for all tickers.
Checks data completeness, API functionality, calculations, and score sanity.
"""

import sys
from pathlib import Path
import json
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import traceback

sys.path.insert(0, str(Path(__file__).parent))

from app.scoring.engine import (
    compute_company_scores, load_financials_df, load_price_history,
    safe_series, calculate_cagr, ScoreComputationError
)
import yfinance as yf

# Find all tickers
def get_all_tickers() -> List[str]:
    tickers = set()
    
    # From financial files
    fin_dir = Path("data/structured/financials")
    if fin_dir.exists():
        for f in fin_dir.glob("*_financials.json"):
            ticker = f.stem.replace("_financials", "").upper()
            tickers.add(ticker)
    
    # From price files
    price_dir = Path("data/structured/prices")
    if price_dir.exists():
        for f in price_dir.glob("*.csv"):
            ticker = f.stem.replace("_prices", "").upper()
            tickers.add(ticker)
    
    return sorted(tickers)

def verify_ticker_data(ticker: str) -> Dict:
    """Verify data completeness and quality for a ticker."""
    result = {
        'ticker': ticker,
        'data_status': {},
        'calculation_status': {},
        'score': None,
        'issues': [],
        'warnings': []
    }
    
    # 1. Check file existence
    fin_file = Path(f"data/structured/financials/{ticker}_financials.json")
    price_file = Path(f"data/structured/prices/{ticker}_prices.csv")
    earnings_file = Path(f"data/structured/earnings/{ticker}_quarterly_earnings.json")
    
    result['data_status']['financials'] = fin_file.exists()
    result['data_status']['prices'] = price_file.exists()
    result['data_status']['earnings'] = earnings_file.exists()
    
    # 2. Verify financial data
    if fin_file.exists():
        try:
            with open(fin_file) as f:
                data = json.load(f)
            
            # Check structure
            has_income = 'income_statement' in data and bool(data['income_statement'])
            has_balance = 'balance_sheet' in data and bool(data['balance_sheet'])
            has_cashflow = 'cash_flow' in data and bool(data['cash_flow'])
            
            result['data_status']['has_income'] = has_income
            result['data_status']['has_balance'] = has_balance
            result['data_status']['has_cashflow'] = has_cashflow
            
            # Check for key metrics
            if has_income:
                income = data['income_statement']
                periods = len(income) if isinstance(income, dict) else 0
                result['data_status']['income_periods'] = periods
                
                # Check for revenue
                has_revenue = False
                if periods > 0:
                    first_period = list(income.values())[0] if isinstance(income, dict) else {}
                    has_revenue = 'Total Revenue' in first_period
                result['data_status']['has_revenue'] = has_revenue
            
        except Exception as e:
            result['issues'].append(f"Error reading financials: {e}")
    
    # 3. Verify price data
    if price_file.exists():
        try:
            df = pd.read_csv(price_file, nrows=5)
            result['data_status']['price_columns'] = list(df.columns)
            result['data_status']['has_close'] = 'Close' in df.columns
        except Exception as e:
            result['issues'].append(f"Error reading prices: {e}")
    
    # 4. Test calculations
    try:
        fin_df = load_financials_df(ticker)
        revenue_series = safe_series(fin_df, "Total Revenue")
        
        if not revenue_series.empty:
            # Check CAGR calculation
            annual_revenue = revenue_series[
                (revenue_series.index.month == 12) & (revenue_series.index.day == 31)
            ].sort_index()
            
            if len(annual_revenue) >= 2:
                cagr = calculate_cagr(annual_revenue)
                result['calculation_status']['cagr'] = cagr
                result['calculation_status']['cagr_valid'] = cagr is not None and not np.isnan(cagr)
                
                # Check for negative CAGR that might indicate data issues
                if cagr and cagr < -0.5:  # More than 50% decline
                    result['warnings'].append(f"Very negative CAGR: {cagr*100:.1f}%")
            
            # Check for quarterly/annual mixing
            total_periods = len(revenue_series)
            annual_periods = len(annual_revenue)
            if total_periods > annual_periods * 1.5:  # More than 50% extra suggests mixing
                result['warnings'].append(f"Possible quarterly/annual mixing: {total_periods} total, {annual_periods} annual")
        
        result['calculation_status']['financials_loadable'] = True
    except ScoreComputationError as e:
        result['calculation_status']['financials_loadable'] = False
        result['issues'].append(f"Cannot load financials: {e}")
    except Exception as e:
        result['calculation_status']['financials_loadable'] = False
        result['issues'].append(f"Calculation error: {e}")
    
    # 5. Test API (yfinance)
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        if info:
            result['calculation_status']['yfinance_works'] = True
            result['calculation_status']['has_market_cap'] = 'marketCap' in info
        else:
            result['calculation_status']['yfinance_works'] = False
            result['warnings'].append("yfinance returned empty info")
    except Exception as e:
        result['calculation_status']['yfinance_works'] = False
        result['issues'].append(f"yfinance API error: {e}")
    
    # 6. Compute score
    try:
        scores = compute_company_scores(ticker)
        if scores and 'overall' in scores:
            result['score'] = scores['overall'].get('score')
            result['calculation_status']['score_computed'] = True
            
            # Get component scores for analysis
            if 'scores' in scores:
                comp_scores = {}
                for key, comp in scores['scores'].items():
                    comp_scores[key] = comp.get('score')
                result['component_scores'] = comp_scores
        else:
            result['calculation_status']['score_computed'] = False
            result['issues'].append("Score computation returned no overall score")
    except Exception as e:
        result['calculation_status']['score_computed'] = False
        result['issues'].append(f"Score computation error: {e}")
        result['issues'].append(traceback.format_exc())
    
    return result

def sanity_check_scores(results: List[Dict]) -> List[Dict]:
    """Play devil's advocate - check if scores make intuitive sense."""
    sanity_checks = []
    
    # Get scores
    scored_tickers = [(r['ticker'], r['score']) for r in results if r['score'] is not None]
    scored_tickers.sort(key=lambda x: x[1] or 0, reverse=True)
    
    # Known high-quality companies (should score well)
    high_quality = ['NVDA', 'MSFT', 'AAPL', 'GOOGL', 'TSM', 'AVGO', 'AMD']
    
    # Known risky/small companies (should score lower)
    risky = ['NAK', 'NVA', 'PPTA', 'UAMY', 'CRML']
    
    for ticker, score in scored_tickers:
        checks = []
        
        # Check 1: High-quality companies should score well
        if ticker in high_quality:
            if score and score < 6.0:
                checks.append(f"⚠️  {ticker} scores {score:.2f} but is a high-quality company (expected 7+)")
            elif score and score >= 7.0:
                checks.append(f"✅ {ticker} scores {score:.2f} - appropriate for high-quality company")
        
        # Check 2: Risky companies should score lower
        if ticker in risky:
            if score and score > 7.0:
                checks.append(f"⚠️  {ticker} scores {score:.2f} but is a risky/small company (expected <6)")
            elif score and score < 6.0:
                checks.append(f"✅ {ticker} scores {score:.2f} - appropriate for risky company")
        
        # Check 3: Score distribution
        if score:
            if score > 9.0:
                checks.append(f"⚠️  {ticker} scores {score:.2f} - very high, verify components")
            elif score < 3.0:
                checks.append(f"⚠️  {ticker} scores {score:.2f} - very low, verify data quality")
        
        if checks:
            sanity_checks.append({
                'ticker': ticker,
                'score': score,
                'checks': checks
            })
    
    return sanity_checks

def main():
    print("="*80)
    print("COMPREHENSIVE TICKER VERIFICATION")
    print("="*80)
    print()
    
    tickers = get_all_tickers()
    print(f"Found {len(tickers)} tickers to verify")
    print(f"Tickers: {', '.join(tickers)}")
    print()
    
    results = []
    for i, ticker in enumerate(tickers, 1):
        print(f"[{i}/{len(tickers)}] Verifying {ticker}...", end=" ", flush=True)
        try:
            result = verify_ticker_data(ticker)
            results.append(result)
            
            # Quick status
            if result['score'] is not None:
                print(f"✅ Score: {result['score']:.2f}")
            elif result['issues']:
                print(f"❌ {len(result['issues'])} issues")
            else:
                print(f"⚠️  No score")
        except Exception as e:
            print(f"❌ Error: {e}")
            results.append({
                'ticker': ticker,
                'error': str(e),
                'issues': [f"Verification failed: {e}"]
            })
    
    print()
    print("="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print()
    
    # Summary statistics
    total = len(results)
    with_scores = sum(1 for r in results if r.get('score') is not None)
    with_issues = sum(1 for r in results if r.get('issues'))
    with_warnings = sum(1 for r in results if r.get('warnings'))
    
    print(f"Total Tickers: {total}")
    print(f"✅ With Scores: {with_scores} ({with_scores/total*100:.1f}%)")
    print(f"❌ With Issues: {with_issues} ({with_issues/total*100:.1f}%)")
    print(f"⚠️  With Warnings: {with_warnings} ({with_warnings/total*100:.1f}%)")
    print()
    
    # Data completeness
    print("DATA COMPLETENESS:")
    print("-"*80)
    has_financials = sum(1 for r in results if r.get('data_status', {}).get('financials'))
    has_prices = sum(1 for r in results if r.get('data_status', {}).get('prices'))
    has_earnings = sum(1 for r in results if r.get('data_status', {}).get('earnings'))
    
    print(f"Financials: {has_financials}/{total} ({has_financials/total*100:.1f}%)")
    print(f"Prices: {has_prices}/{total} ({has_prices/total*100:.1f}%)")
    print(f"Earnings: {has_earnings}/{total} ({has_earnings/total*100:.1f}%)")
    print()
    
    # Issues breakdown
    if with_issues > 0:
        print("ISSUES FOUND:")
        print("-"*80)
        for r in results:
            if r.get('issues'):
                print(f"\n{r['ticker']}:")
                for issue in r['issues']:
                    print(f"  ❌ {issue}")
        print()
    
    # Warnings
    if with_warnings > 0:
        print("WARNINGS:")
        print("-"*80)
        for r in results:
            if r.get('warnings'):
                print(f"\n{r['ticker']}:")
                for warning in r['warnings']:
                    print(f"  ⚠️  {warning}")
        print()
    
    # Score distribution
    scores = [r['score'] for r in results if r.get('score') is not None]
    if scores:
        print("SCORE DISTRIBUTION:")
        print("-"*80)
        print(f"Mean: {np.mean(scores):.2f}")
        print(f"Median: {np.median(scores):.2f}")
        print(f"Min: {np.min(scores):.2f}")
        print(f"Max: {np.max(scores):.2f}")
        print(f"Std Dev: {np.std(scores):.2f}")
        print()
        
        # Top and bottom scores
        scored_results = [(r['ticker'], r['score']) for r in results if r.get('score') is not None]
        scored_results.sort(key=lambda x: x[1], reverse=True)
        
        print("TOP 10 SCORES:")
        for ticker, score in scored_results[:10]:
            print(f"  {ticker}: {score:.2f}")
        print()
        
        print("BOTTOM 10 SCORES:")
        for ticker, score in scored_results[-10:]:
            print(f"  {ticker}: {score:.2f}")
        print()
    
    # Sanity checks
    print("SANITY CHECKS (Devil's Advocate):")
    print("-"*80)
    sanity_results = sanity_check_scores(results)
    
    if sanity_results:
        for check in sanity_results:
            print(f"\n{check['ticker']} (Score: {check['score']:.2f}):")
            for c in check['checks']:
                print(f"  {c}")
    else:
        print("✅ No obvious sanity check failures")
    print()
    
    # Detailed results table
    print("DETAILED RESULTS:")
    print("-"*80)
    print(f"{'Ticker':<8} {'Score':<8} {'Financials':<12} {'Prices':<8} {'Issues':<8} {'Warnings':<8}")
    print("-"*80)
    
    for r in sorted(results, key=lambda x: x.get('score') or 0, reverse=True):
        ticker = r['ticker']
        score = f"{r['score']:.2f}" if r.get('score') is not None else "N/A"
        fin = "✅" if r.get('data_status', {}).get('financials') else "❌"
        prices = "✅" if r.get('data_status', {}).get('prices') else "❌"
        issues = len(r.get('issues', []))
        warnings = len(r.get('warnings', []))
        
        print(f"{ticker:<8} {score:<8} {fin:<12} {prices:<8} {issues:<8} {warnings:<8}")
    
    # Save detailed report
    report_file = Path("TICKER_VERIFICATION_REPORT.json")
    with open(report_file, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    
    print()
    print(f"✅ Detailed report saved to: {report_file}")
    print("="*80)

if __name__ == "__main__":
    main()

