# Flow Data Integration - Enhanced Version

This document describes the institutional and retail flow data functionality with **daily tracking** and **institutional inflow/outflow analysis**.

## Overview

The flow data module fetches and analyzes institutional ownership and retail trading flow patterns for stock tickers. This provides insights into:

- **Institutional Holdings**: Who owns the stock and how much
- **Institutional Changes**: Which institutions bought or sold shares (inflow/outflow)
- **Retail Participation**: Estimated retail investor activity
- **Flow Direction**: Whether money is flowing in or out of the stock
- **Historical Tracking**: Daily snapshots with date-based file naming

## Key Features

### 🆕 Daily Tracking with Date Suffixes
All flow data files now include date suffixes (YYYYMMDD format) for historical tracking:
- `NVDA_institutional_flow_20251107.json`
- `NVDA_retail_flow_20251107.json`
- `NVDA_combined_flow_20251107.json`

### 🆕 Institutional Inflow/Outflow Tracking
Automatically compares current institutional holdings with previous data to identify:
- Which institutions increased their positions (buyers)
- Which institutions decreased their positions (sellers)
- Net institutional flow (total inflow or outflow)
- Percentage changes for each holder
- Top 5 buyers and top 5 sellers

## Files Created

### 1. `fetch_data/flow_data.py`
Enhanced data fetching module with institutional change tracking:

- **`get_date_suffix()`**
  - Returns today's date in YYYYMMDD format for file naming

- **`load_previous_institutional_data(ticker, flow_dir)`**
  - Loads the most recent previous institutional data file
  - Searches for files from past 90 days
  - Skips today's file to get true previous data

- **`calculate_institutional_changes(current_data, previous_data)`**
  - Compares current vs previous institutional holdings
  - Calculates share and value changes for each holder
  - Identifies buyers and sellers
  - Returns net institutional flow metrics

- **`fetch_institutional_flow(ticker, flow_dir)`**
  - Fetches institutional holder data from Yahoo Finance
  - Returns top 10 institutional holders with share counts and values
  - Calculates institutional and insider ownership percentages
  - Saves data to `{ticker}_institutional_flow_{YYYYMMDD}.json`

- **`fetch_retail_flow(ticker, flow_dir, period='3mo')`**
  - Estimates retail participation based on volume patterns
  - Analyzes 60-day trading history
  - Calculates inflow/outflow indicators
  - Provides daily flow metrics with retail participation estimates
  - Saves data to `{ticker}_retail_flow_{YYYYMMDD}.json`

- **`fetch_combined_flow_data(ticker, flow_dir)`**
  - Combines institutional, retail, and change tracking data
  - Automatically loads previous data for comparison
  - Saves comprehensive data to `{ticker}_combined_flow_{YYYYMMDD}.json`

### 2. Data Directory Structure
```
data/structured/flow_data/
├── {TICKER}_institutional_flow_{YYYYMMDD}.json
├── {TICKER}_retail_flow_{YYYYMMDD}.json
└── {TICKER}_combined_flow_{YYYYMMDD}.json
```

Example:
```
data/structured/flow_data/
├── NVDA_institutional_flow_20251107.json
├── NVDA_institutional_flow_20251031.json  (previous week)
├── NVDA_retail_flow_20251107.json
└── NVDA_combined_flow_20251107.json
```

### 3. Integration Points

**`fetch_data/utils.py`**
- Added `FLOW_DATA_DIR` constant pointing to `data/structured/flow_data`

**`fetch_data.py`**
- Added import for `fetch_combined_flow_data`
- Integrated flow data fetching into main data collection workflow
- Fetches flow data for each company ticker daily

**`app/agents/agents.py`**
- Enhanced `get_flow_data(ticker, flow_type, date)` tool function
  - Supports `flow_type='changes'` for institutional change tracking
  - Supports `date='latest'` or specific date (YYYYMMDD)
  - Uses glob pattern matching to find dated files
  - Returns available dates for historical analysis
- Created `flow_data_subagent` agent with change tracking capabilities
- Added flow agent to root agent's sub_agents list
- Updated root agent instructions to include institutional inflow/outflow queries

## Data Structure

### Institutional Flow Data
```json
{
  "ticker": "NVDA",
  "timestamp": "2025-11-07T23:42:02.081479",
  "institutional_ownership_pct": 76.5,
  "insider_ownership_pct": 4.2,
  "total_institutional_shares": 8478662514,
  "total_institutional_value": 1595260300254,
  "number_of_institutions": 10,
  "top_10_holders": [
    {
      "holder": "Vanguard Group Inc",
      "shares": 2232444958,
      "date_reported": "2025-06-30",
      "pct_out": 8.9,
      "value": 420034505221
    }
  ],
  "data_source": "Yahoo Finance"
}
```

### 🆕 Institutional Changes Data
```json
{
  "has_comparison": true,
  "comparison_date": "2025-10-31T23:42:02.276408",
  "current_date": "2025-11-07T23:42:02.696386",
  "net_institutional_flow": {
    "shares_change": 254359876,
    "value_change": 47857809008,
    "direction": "inflow",
    "current_total_shares": 8478662514,
    "previous_total_shares": 8224302638,
    "current_total_value": 1595260300254,
    "previous_total_value": 1547402491246
  },
  "holder_changes": [
    {
      "holder": "Vanguard Group Inc",
      "current_shares": 2232444958,
      "previous_shares": 2120822710,
      "shares_change": 111622248,
      "pct_change": 5.26,
      "value_change": 21001725261,
      "action": "bought",
      "current_date": "2025-06-30",
      "previous_date": "2025-06-30"
    }
  ],
  "summary": {
    "total_holders_tracked": 10,
    "holders_increased": 2,
    "holders_decreased": 1,
    "top_5_buyers": [
      {
        "holder": "Vanguard Group Inc",
        "shares_change": 111622248,
        "pct_change": 5.26
      }
    ],
    "top_5_sellers": [
      {
        "holder": "Blackrock Inc.",
        "shares_change": -57293669,
        "pct_change": -2.91
      }
    ]
  }
}
```

### Retail Flow Data
```json
{
  "ticker": "NVDA",
  "timestamp": "2025-11-07T23:42:02.235351",
  "period_analyzed": "3mo",
  "metrics": {
    "average_daily_volume": 180902124,
    "recent_30d_avg_volume": 182915932,
    "volume_trend_pct": 1.11,
    "estimated_avg_retail_participation_pct": 48.5,
    "net_flow_indicator_pct": -1.47,
    "inflow_days_count": 13,
    "outflow_days_count": 17
  },
  "daily_flows": [
    {
      "date": "2025-11-07",
      "volume": 175234567,
      "price_change_pct": 2.3,
      "estimated_retail_participation_pct": 55.0,
      "estimated_institutional_participation_pct": 45.0,
      "volume_vs_average": 0.97
    }
  ],
  "interpretation": {
    "retail_trend": "stable",
    "flow_direction": "balanced",
    "volume_pattern": "stable"
  },
  "disclaimer": "Retail flow estimates are based on volume patterns and heuristics.",
  "data_source": "Yahoo Finance with algorithmic estimation"
}
```

### Combined Flow Data
The combined file includes all three sections:
- `institutional`: Current institutional holdings
- `retail`: Retail flow estimates
- `institutional_changes`: 🆕 Change tracking vs previous period

## Agent Usage

The FlowData_Agent can answer questions like:

### 1. **Institutional Ownership**
   - "What's the institutional ownership of NVDA?"
   - "Who are the top holders of AVGO?"
   - "Show me institutional data for TSLA"

### 2. **🆕 Institutional Changes (Inflow/Outflow)**
   - "Did institutions buy or sell NVDA recently?"
   - "Show me institutional changes for AMD"
   - "Which institutions are buying AVGO?"
   - "Are institutions selling ORCL?"
   - "What are the top institutional buyers of NVDA?"

### 3. **Retail Flow**
   - "What's the retail flow for NVDA?"
   - "Is retail buying or selling AMD?"
   - "Show me retail participation trends for ORCL"

### 4. **Combined Analysis**
   - "Analyze flow data for NVDA"
   - "What are the ownership patterns for AVGO?"
   - "Show me institutional and retail flows for TSLA"

### 5. **🆕 Historical Data**
   - "Show me flow data from 20251031"
   - "Compare NVDA flow data across dates"

## Usage Examples

### Fetching Flow Data
```python
from fetch_data.flow_data import fetch_combined_flow_data
from fetch_data.utils import FLOW_DATA_DIR

# Fetch all flow data for a ticker (includes change tracking)
result = fetch_combined_flow_data("NVDA", FLOW_DATA_DIR)

# Access institutional changes
changes = result['institutional_changes']
if changes['has_comparison']:
    print(f"Net flow direction: {changes['net_institutional_flow']['direction']}")
    print(f"Top buyers: {changes['summary']['top_5_buyers']}")
    print(f"Top sellers: {changes['summary']['top_5_sellers']}")
```

### Querying via Agent
```python
from app.agents.agents import get_flow_data

# Get institutional data only
inst_data = get_flow_data("NVDA", flow_type="institutional")

# Get retail flow only
retail_data = get_flow_data("NVDA", flow_type="retail")

# Get combined data (includes changes)
combined = get_flow_data("NVDA", flow_type="combined")

# 🆕 Get institutional changes only
changes = get_flow_data("NVDA", flow_type="changes")

# 🆕 Get data from specific date
historical = get_flow_data("NVDA", flow_type="combined", date="20251031")

# Get latest data (default)
latest = get_flow_data("NVDA", flow_type="combined", date="latest")
```

## Data Collection

Flow data is automatically collected when running the main data fetching workflow:

```bash
python fetch_data.py
```

This will:
1. Fetch current institutional holdings
2. Load previous institutional data (if available)
3. Calculate institutional changes (buyers/sellers)
4. Fetch retail flow estimates
5. Save all data with today's date suffix
6. Build historical tracking database

Run daily to maintain institutional change tracking!

## Methodology

### Institutional Flow
- Data sourced from Yahoo Finance institutional holders
- Provides actual reported holdings from SEC filings
- Includes top institutional holders and their positions
- Updates based on quarterly 13F filings

### 🆕 Institutional Change Tracking
Compares current holdings with most recent previous data:

1. **Match holders** across current and previous periods
2. **Calculate differences** in share counts and values
3. **Identify actions**:
   - `bought`: Share count increased
   - `sold`: Share count decreased
   - `no change`: No position change
4. **Aggregate metrics**:
   - Net institutional flow (total inflow/outflow)
   - Number of buyers vs sellers
   - Top 5 buyers and sellers by magnitude
5. **Track changes** over time with date-stamped files

### Retail Flow Estimation
Retail participation is estimated using volume pattern analysis:

1. **Volume Analysis**: Compare daily volume to historical averages
2. **Price-Volume Correlation**: High volume on up-days suggests retail buying
3. **Volume Volatility**: Large spikes indicate institutional activity
4. **Heuristic Adjustments**:
   - +15% retail on momentum days (>2% price increase)
   - -15% retail on down days (<-2% price decrease)
   - -20% retail on high-volume spike days (>2x average volume)

### Limitations
- Retail participation percentages are **estimates** based on heuristics
- Actual retail participation may vary significantly
- Data is delayed and based on publicly available information
- Yahoo Finance data may have inconsistencies or gaps
- Institutional holdings are reported quarterly (13F filings)
- Changes detected may span weeks or months between filings
- First run has no comparison data (subsequent runs will track changes)

## Testing

Two test scripts are provided:

### Basic Flow Data Test
```bash
python test_flow_data.py
```
Tests basic flow data fetching and file creation.

### 🆕 Institutional Change Tracking Test
```bash
python test_institutional_changes.py
```
This will:
1. Create simulated previous institutional data
2. Fetch current flow data
3. Calculate and display institutional changes
4. Show top buyers and sellers
5. Display net institutional flow direction

Sample output:
```
📊 NET INSTITUTIONAL FLOW:
   Direction: INFLOW
   Shares Change: 254,359,876
   Value Change: $47,857,809,008

🟢 TOP 5 BUYERS (Increased Positions):
   1. Vanguard Group Inc
      • Bought: 111,622,248 shares (+5.26%)
   2. FMR, LLC
      • Bought: 99,797,784 shares (+11.11%)

🔴 TOP 5 SELLERS (Decreased Positions):
   1. Blackrock Inc.
      • Sold: 57,293,669 shares (-2.91%)
```

## Future Enhancements

Potential improvements:
1. Integration with additional data sources (Bloomberg, FactSet)
2. More sophisticated retail flow algorithms using order flow data
3. Historical trend analysis of institutional ownership changes
4. Alerts for significant institutional position changes (>10%)
5. Correlation analysis between flows and price movements
6. Sentiment analysis from institutional buying/selling patterns
7. Automated detection of 13F filing dates for fresh data
8. Machine learning models to predict institutional moves

## Important Notes

### Daily Data Collection
- **Run daily** to maintain continuous institutional change tracking
- Each day creates new files with date suffixes
- Previous data automatically loaded for comparison
- Historical database builds over time

### First Run Behavior
On the first run for a ticker:
```json
{
  "institutional_changes": {
    "has_comparison": false,
    "message": "No previous data available for comparison"
  }
}
```

On subsequent runs (with previous data):
```json
{
  "institutional_changes": {
    "has_comparison": true,
    "net_institutional_flow": { ... },
    "holder_changes": [ ... ],
    "summary": { ... }
  }
}
```

### File Management
- Old files are kept for historical analysis
- File naming pattern: `{TICKER}_{type}_flow_{YYYYMMDD}.json`
- Glob pattern matching finds all historical files
- Can query specific dates or latest data

## Support

For questions or issues:
- Check the test script outputs for debugging
- Review log files for detailed error messages
- Ensure Yahoo Finance API is accessible
- Verify ticker symbols are valid and supported
- Run `test_institutional_changes.py` to verify change tracking works

## Summary of Enhancements

✅ **Date-suffixed filenames** for daily tracking
✅ **Institutional inflow/outflow tracking** with buyer/seller identification
✅ **Historical data support** with date-based queries
✅ **Automatic comparison** with previous period
✅ **Net institutional flow** metrics and direction
✅ **Top 5 buyers and sellers** identification
✅ **Enhanced agent capabilities** for change queries
✅ **Comprehensive test suite** with simulated data

The flow data system now provides complete tracking of institutional money movement with historical analysis capabilities!
