# Comprehensive Sector Analysis Features

## Overview
This document describes all the enhanced sector metrics and analysis features available in the financial agent system.

## Features Implemented

### 1. Enhanced Technical Indicators (fetch_data.py:1467-1561)

#### New Functions:
- **`calculate_volatility(prices)`** - Annualized volatility (standard deviation of returns)
- **`calculate_beta(prices, market_prices)`** - Systematic risk relative to market (SPY)
- **`calculate_sharpe_ratio(prices)`** - Risk-adjusted returns
- **`calculate_momentum_score(prices)`** - Multi-period momentum (1M, 3M, 6M, 1Y)

### 2. Enhanced Company Metrics (fetch_data.py:1564-1748)

The `get_company_metrics()` function now includes:

#### Efficiency Ratios:
- **ROE** (Return on Equity) - Profitability relative to shareholder equity
- **ROA** (Return on Assets) - Profitability relative to total assets
- **ROIC** (Return on Invested Capital) - Return on total invested capital

#### Debt & Liquidity Metrics:
- **Debt-to-Equity Ratio** - Financial leverage
- **Current Ratio** - Short-term liquidity
- **Quick Ratio** - Immediate liquidity (excluding inventory)
- **Interest Coverage Ratio** - Ability to service debt

#### Additional Valuations:
- **P/B Ratio** (Price-to-Book) - Market value vs book value

### 3. Sector Sentiment Analysis (fetch_data.py:1751-1872)

**Function:** `aggregate_sector_sentiment()`

Aggregates social media sentiment from X/Twitter data by sector:
- Total posts by sector
- Bullish/bearish/neutral percentages
- Net sentiment score (bullish % - bearish %)
- Average compound sentiment score
- Number of companies tracked per sector

**Output:**
```json
{
  "Technology": {
    "total_posts": 150,
    "bullish_pct": 45.5,
    "bearish_pct": 25.3,
    "neutral_pct": 29.2,
    "net_sentiment": 20.2,
    "avg_compound_score": 0.234,
    "num_companies": 4
  }
}
```

### 4. Company-to-Sector Comparison (fetch_data.py:1875-2007)

**Function:** `compare_company_to_sector(company_metrics, sector_stats)`

Compares individual companies against their sector benchmarks:

#### Outputs:
- **Relative Performance Score** (0-100) - Overall performance vs sector
- **Classification** - Sector Leader, Above Average, Average, Below Average, or Sector Laggard
- **Strengths** - Metrics where company outperforms sector by >20%
- **Weaknesses** - Metrics where company underperforms sector by >20%
- **Outliers** - Metrics with >30% deviation from sector average

#### Metrics Compared:
- Profitability: ROE, ROA, ROIC, margins
- Growth: CAGR, momentum
- Valuation: P/E, P/S, P/B ratios
- Financial Health: Debt ratios, liquidity
- Risk: Beta, volatility, Sharpe ratio

**Example Output:**
```json
{
  "ticker": "AAPL",
  "classification": "Sector Leader",
  "relative_performance_score": 78.5,
  "strengths": ["roe", "net_margin", "sharpe_ratio"],
  "weaknesses": ["pe_ratio"],
  "outliers": [{"metric": "roe", "pct_difference": 125.3}]
}
```

### 5. Sector Momentum Tracking (fetch_data.py:2010-2106)

**Function:** `calculate_sector_momentum_with_sentiment(sector_stats, sector_sentiment)`

Combines price momentum with social media sentiment:

#### Features:
- **Weighted Price Momentum** - 40% 1M, 30% 3M, 20% 6M, 10% 1Y
- **Combined Score** - 70% price momentum + 30% sentiment
- **Momentum Trend** - Accelerating, Decelerating, or Stable
- **Trading Signals** - Strong Buy, Buy, Hold, Sell, Strong Sell

**Example Output:**
```json
{
  "Technology": {
    "combined_momentum_score": 15.8,
    "signal": "Strong Buy",
    "momentum_trend": "Accelerating",
    "price_momentum_3m": 18.5,
    "sentiment_score": 0.234,
    "net_sentiment": 20.2
  }
}
```

### 6. Sector Correlations & Relative Strength (fetch_data.py:2109-2242)

**Function:** `calculate_sector_correlations_and_strength(metrics_df, market_prices)`

Calculates inter-sector relationships and market outperformance:

#### Correlation Matrix:
- Identifies sectors that move together
- Highlights high correlation pairs (|r| > 0.7)
- Distinguishes positive vs negative correlations

#### Relative Strength Analysis:
- **RS Score** = Sector Return - Market (SPY) Return
- **Composite RS** - Weighted average (50% 3M, 30% 6M, 20% 1Y)
- **Classification**:
  - Strong Outperformer (RS > 5%)
  - Outperformer (RS > 2%)
  - Market Performer (-2% < RS < 2%)
  - Underperformer (RS < -2%)
  - Strong Underperformer (RS < -5%)

**Example Output:**
```json
{
  "correlation_matrix": {
    "Technology": {
      "Healthcare": 0.65,
      "Financials": 0.42
    }
  },
  "relative_strength": {
    "Technology": {
      "composite_rs": 7.3,
      "classification": "Strong Outperformer",
      "rs_3m": 8.5,
      "rs_6m": 6.8,
      "rs_1y": 6.5
    }
  },
  "sector_pairs": [
    {
      "sector1": "Technology",
      "sector2": "Communication Services",
      "correlation": 0.85,
      "relationship": "Positive"
    }
  ]
}
```

### 7. Sector Quality Score (fetch_data.py:2245-2316)

**Function:** `calculate_sector_quality_score(sector_data)`

Composite 0-100 score evaluating sector quality:

#### Scoring Components:
- **Profitability** (30 points) - ROE, margins, ROIC
- **Growth** (25 points) - CAGR, momentum
- **Financial Health** (25 points) - Debt ratios, liquidity, interest coverage
- **Risk-Adjusted Returns** (20 points) - Sharpe ratio, volatility

## Usage

### Running Complete Sector Analysis:

```bash
# Run full analysis on all companies
python calculate_sector_metrics.py

# Or use the main pipeline
python fetch_data.py
```

### Running Tests:

```bash
# Test with sample companies
python test_sector_metrics.py

# Comprehensive feature test
python test_comprehensive_sector_analysis.py
```

### Accessing Results:

Results are saved to `data/structured/sector_metrics/` with timestamp:

1. **`company_metrics_YYYYMMDD_HHMMSS.json`** - Individual company metrics
2. **`sector_metrics_YYYYMMDD_HHMMSS.json`** - Complete sector analysis including:
   - Sector aggregates
   - Sentiment analysis
   - Momentum signals
   - Correlation matrix
   - Relative strength rankings

### Programmatic Usage:

```python
from fetch_data import (
    get_company_metrics,
    aggregate_sector_sentiment,
    compare_company_to_sector,
    calculate_sector_momentum_with_sentiment,
    calculate_sector_correlations_and_strength
)

# Get company metrics with all new indicators
metrics = get_company_metrics('AAPL', market_prices)

# Compare company to sector
comparison = compare_company_to_sector(company_metrics, sector_stats)
print(f"Classification: {comparison['classification']}")
print(f"Performance Score: {comparison['relative_performance_score']}")

# Get sector sentiment
sentiment = aggregate_sector_sentiment()
print(f"Tech Sector Net Sentiment: {sentiment['Technology']['net_sentiment']}")

# Calculate momentum signals
momentum = calculate_sector_momentum_with_sentiment(sector_stats, sentiment)
print(f"Tech Sector Signal: {momentum['Technology']['signal']}")

# Analyze correlations
correlations = calculate_sector_correlations_and_strength(metrics_df, spy_prices)
print(f"Tech Relative Strength: {correlations['relative_strength']['Technology']['composite_rs']}")
```

## Output Reports

### Console Output:
The enhanced `calculate_sector_metrics()` function displays:
1. Sector metrics ranked by quality score
2. Sentiment analysis (top 5 by net sentiment)
3. Momentum signals (top 5 by combined score)
4. High correlation pairs
5. Relative strength leaders (vs SPY)

### JSON Output Structure:
```json
{
  "fetch_timestamp": "2025-10-10T22:44:44",
  "total_companies_analyzed": 17,
  "total_sectors": 5,
  "sectors": {
    "Technology": {
      "num_companies": 4,
      "quality_score": 75.2,
      "avg_roe": 45.3,
      "avg_momentum_3m": 18.5,
      // ... all sector metrics
    }
  },
  "sentiment_analysis": {
    "Technology": {
      "net_sentiment": 20.2,
      "total_posts": 150
    }
  },
  "momentum_analysis": {
    "Technology": {
      "combined_momentum_score": 15.8,
      "signal": "Strong Buy"
    }
  },
  "correlation_analysis": {
    "correlation_matrix": {},
    "relative_strength": {},
    "sector_pairs": []
  }
}
```

## Key Insights Provided

1. **Investment Opportunities** - Identify sector leaders and undervalued companies
2. **Risk Management** - Understand sector correlations for diversification
3. **Momentum Trading** - Combined price and sentiment signals
4. **Sector Rotation** - Relative strength analysis for timing shifts
5. **Quality Assessment** - Comprehensive quality scores for sector evaluation
6. **Social Sentiment** - Real-time market sentiment from X/Twitter

## Dependencies

All features work with existing dependencies:
- `pandas` - Data manipulation
- `numpy` - Numerical calculations
- `yfinance` - Market data
- `json` - Data storage

## Notes

- Sentiment analysis requires X/Twitter data files in `data/unstructured/x/`
- Beta and relative strength require SPY market benchmark
- ROIC calculation uses approximated corporate tax rate of 21%
- Momentum periods: 1M=21 days, 3M=63 days, 6M=126 days, 1Y=252 days
