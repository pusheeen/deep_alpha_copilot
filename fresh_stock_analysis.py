#!/usr/bin/env python3
"""
Fetch fresh stock data and analyze entry strategies for MU, CLS, and GOOGL.
"""

import sys
import os
from pathlib import Path
from datetime import datetime, timedelta
import pandas as pd
import numpy as np

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

try:
    import yfinance as yf
except ImportError:
    print("❌ Error: yfinance not installed")
    print("   Install with: pip install yfinance")
    sys.exit(1)

try:
    from app.scoring.engine import compute_company_scores
    SCORING_AVAILABLE = True
except ImportError:
    SCORING_AVAILABLE = False
    print("⚠️  Warning: Could not import scoring engine")


def compute_rsi(series, period=14):
    """Calculate RSI."""
    delta = series.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def fetch_fresh_analysis(tickers):
    """Fetch fresh data and analyze stocks."""
    print("=" * 70)
    print("FRESH STOCK ANALYSIS - Entry Strategy for 5% Return Target")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
    
    results = []
    
    # Fetch data
    print("📥 Fetching fresh market data...")
    data = yf.download(tickers, period="2y", group_by='ticker', progress=False)
    
    for ticker in tickers:
        print(f"\n{'='*70}")
        print(f"Analyzing: {ticker}")
        print('='*70)
        
        try:
            # Extract ticker data
            if isinstance(data.columns, pd.MultiIndex):
                if ticker not in data.columns.levels[0]:
                    print(f"❌ No data available for {ticker}")
                    continue
                df = data[ticker].copy()
            else:
                df = data.copy()
            
            if df.empty:
                print(f"❌ Empty data for {ticker}")
                continue
            
            # Clean data
            closes = df['Close'].ffill()
            volumes = df['Volume'].fillna(0)
            
            # Current metrics
            current_price = closes.iloc[-1]
            current_date = df.index[-1]
            
            # Moving averages
            ma50 = closes.rolling(50).mean().iloc[-1] if len(closes) >= 50 else None
            ma200 = closes.rolling(200).mean().iloc[-1] if len(closes) >= 200 else None
            
            # Returns
            r6m = None
            r12m = None
            if len(closes) > 126:
                r6m = (current_price / closes.iloc[-126] - 1) * 100
            if len(closes) > 252:
                r12m = (current_price / closes.iloc[-252] - 1) * 100
            
            # RSI
            rsi_series = compute_rsi(closes)
            current_rsi = rsi_series.iloc[-1] if not rsi_series.empty else None
            
            # Volume metrics
            adv30 = volumes.rolling(30).mean().iloc[-1] if len(volumes) >= 30 else None
            current_vol = volumes.iloc[-1]
            rvol = (current_vol / adv30) if adv30 and adv30 > 0 else None
            
            # Trend analysis
            if ma50 and ma200:
                if current_price > ma50 > ma200:
                    trend = "Bullish (Price > 50MA > 200MA)"
                    trend_score = 2
                elif current_price > ma50:
                    trend = "Above 50MA (Mixed)"
                    trend_score = 1
                else:
                    trend = "Below 50MA (Bearish)"
                    trend_score = 0
            else:
                trend = "Insufficient data for trend"
                trend_score = 0
            
            # Get Deep Alpha score if available
            da_score = None
            da_summary = None
            if SCORING_AVAILABLE:
                try:
                    scores = compute_company_scores(ticker)
                    if scores and scores.get('scores'):
                        overall = scores.get('overall', {})
                        da_score = overall.get('score')
                        da_summary = scores.get('recommendation', {}).get('why_buy')
                except Exception as e:
                    print(f"   ⚠️  Could not get Deep Alpha score: {e}")
            
            # Calculate days until end of year
            today = datetime.now()
            end_of_year = datetime(today.year, 12, 31)
            days_remaining = (end_of_year - today).days
            
            # Target price for 5% return
            target_price_5pct = current_price * 1.05
            price_needed = target_price_5pct - current_price
            
            # Entry strategy recommendations
            entry_strategies = []
            
            # Strategy 1: Current entry
            if current_rsi and 30 <= current_rsi <= 70:
                entry_strategies.append({
                    'strategy': 'Enter Now',
                    'entry_price': current_price,
                    'target_price': target_price_5pct,
                    'gain_needed': price_needed,
                    'reasoning': f'RSI {current_rsi:.1f} is in healthy range (30-70)'
                })
            
            # Strategy 2: Wait for 10% dip
            dip_10_price = current_price * 0.90
            entry_strategies.append({
                'strategy': 'Wait for 10% Dip',
                'entry_price': dip_10_price,
                'target_price': dip_10_price * 1.05,
                'gain_needed': dip_10_price * 0.05,
                'reasoning': 'Buy on pullback for better entry'
            })
            
            # Strategy 3: Wait for 15% dip
            dip_15_price = current_price * 0.85
            entry_strategies.append({
                'strategy': 'Wait for 15% Dip',
                'entry_price': dip_15_price,
                'target_price': dip_15_price * 1.05,
                'gain_needed': dip_15_price * 0.05,
                'reasoning': 'Buy on deeper pullback (historical: 8%+ returns)'
            })
            
            # Strategy 4: RSI < 40 entry
            if current_rsi and current_rsi > 40:
                entry_strategies.append({
                    'strategy': 'Wait for RSI < 40',
                    'entry_price': 'Variable',
                    'target_price': 'Variable',
                    'gain_needed': '5% from entry',
                    'reasoning': 'Buy on oversold conditions (historical: 5.46% avg return)'
                })
            
            # Display results
            print(f"\n📊 CURRENT METRICS:")
            print(f"   Price: ${current_price:.2f}")
            print(f"   Date: {current_date.strftime('%Y-%m-%d')}")
            print(f"   RSI (14): {current_rsi:.1f}" if current_rsi else "   RSI: N/A")
            print(f"   6M Return: {r6m:.1f}%" if r6m else "   6M Return: N/A")
            print(f"   12M Return: {r12m:.1f}%" if r12m else "   12M Return: N/A")
            print(f"   MA50: ${ma50:.2f}" if ma50 else "   MA50: N/A")
            print(f"   MA200: ${ma200:.2f}" if ma200 else "   MA200: N/A")
            print(f"   Trend: {trend}")
            print(f"   Relative Volume: {rvol:.2f}x" if rvol else "   Relative Volume: N/A")
            print(f"   DeepAlpha Score: {da_score:.2f}/10" if da_score else "   DeepAlpha Score: N/A")
            
            print(f"\n🎯 5% RETURN TARGET:")
            print(f"   Target Price: ${target_price_5pct:.2f}")
            print(f"   Gain Needed: ${price_needed:.2f} ({price_needed/current_price*100:.1f}%)")
            print(f"   Days Remaining: {days_remaining} days")
            
            print(f"\n💡 ENTRY STRATEGIES:")
            for i, strat in enumerate(entry_strategies, 1):
                print(f"\n   Strategy {i}: {strat['strategy']}")
                if isinstance(strat['entry_price'], (int, float)):
                    print(f"      Entry: ${strat['entry_price']:.2f}")
                    print(f"      Target: ${strat['target_price']:.2f}")
                    print(f"      Gain Needed: ${strat['gain_needed']:.2f}")
                else:
                    print(f"      Entry: {strat['entry_price']}")
                    print(f"      Target: {strat['target_price']}")
                    print(f"      Gain Needed: {strat['gain_needed']}")
                print(f"      Reasoning: {strat['reasoning']}")
            
            # Overall recommendation
            print(f"\n✅ RECOMMENDATION:")
            points = 0
            reasons = []
            
            if trend_score >= 2:
                points += 2
                reasons.append("Strong bullish trend")
            elif trend_score == 1:
                points += 1
                reasons.append("Above 50MA")
            
            if r6m and r6m > 20:
                points += 1
                reasons.append(f"Strong 6M momentum ({r6m:.1f}%)")
            
            if current_rsi and 30 <= current_rsi <= 70:
                points += 1
                reasons.append(f"Healthy RSI ({current_rsi:.1f})")
            
            if da_score and da_score >= 6.5:
                points += 2
                reasons.append(f"Strong fundamentals (Score: {da_score:.2f})")
            elif da_score and da_score >= 5.0:
                points += 1
                reasons.append(f"Decent fundamentals (Score: {da_score:.2f})")
            
            if points >= 5:
                action = "BUY"
                confidence = "HIGH"
            elif points >= 3:
                action = "HOLD/CONSIDER"
                confidence = "MEDIUM"
            else:
                action = "WAIT"
                confidence = "LOW"
            
            print(f"   Action: {action}")
            print(f"   Confidence: {confidence}")
            print(f"   Score: {points}/6")
            print(f"   Reasons: {', '.join(reasons)}")
            
            # Store results
            results.append({
                'ticker': ticker,
                'price': current_price,
                'rsi': current_rsi,
                'r6m': r6m,
                'r12m': r12m,
                'ma50': ma50,
                'ma200': ma200,
                'trend': trend,
                'da_score': da_score,
                'target_5pct': target_price_5pct,
                'action': action,
                'confidence': confidence,
                'points': points,
                'entry_strategies': entry_strategies
            })
            
        except Exception as e:
            print(f"❌ Error analyzing {ticker}: {e}")
            import traceback
            traceback.print_exc()
    
    # Summary comparison
    print(f"\n\n{'='*70}")
    print("SUMMARY COMPARISON")
    print('='*70)
    print(f"\n{'Ticker':<8} {'Price':<12} {'RSI':<8} {'6M%':<10} {'Trend':<25} {'DA Score':<12} {'Action':<15}")
    print("-" * 70)
    
    for r in results:
        trend_short = r['trend'][:24] if len(r['trend']) > 24 else r['trend']
        da_str = f"{r['da_score']:.2f}" if r['da_score'] else "N/A"
        r6m_str = f"{r['r6m']:.1f}%" if r['r6m'] else "N/A"
        rsi_str = f"{r['rsi']:.1f}" if r['rsi'] else "N/A"
        
        print(f"{r['ticker']:<8} ${r['price']:<11.2f} {rsi_str:<8} {r6m_str:<10} {trend_short:<25} {da_str:<12} {r['action']:<15}")
    
    return results


if __name__ == "__main__":
    tickers = ['MU', 'CLS', 'GOOGL']
    results = fetch_fresh_analysis(tickers)
    
    print(f"\n\n{'='*70}")
    print("ANALYSIS COMPLETE")
    print('='*70)

