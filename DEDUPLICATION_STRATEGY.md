# BigQuery Deduplication Strategy

This document explains the deduplication logic implemented in `bigquery_uploader.py` to ensure all data is unique.

## Summary

Different data types use different deduplication strategies based on their characteristics:

| Data Type | Strategy | Key Fields | Behavior |
|-----------|----------|------------|----------|
| CEO Profiles | Skip Duplicates | ticker | Only insert if ticker doesn't exist |
| Quarterly Earnings | Skip Duplicates (Time Series) | ticker + period | Only insert periods not already in database |
| Financial Statements | Skip Duplicates (Time Series) | ticker + fiscal_date | Only insert fiscal dates not already in database |
| Stock Prices | Skip Duplicates (Time Series) | ticker + date | Only insert dates not already in database |
| Reddit Posts | Skip Duplicates | ticker + post_id | Only insert posts with new post_ids |
| X/Twitter Posts | Skip Duplicates | ticker + post_id | Only insert posts with new post_ids |
| Sector Metrics | Append Snapshot | sector + fetch_timestamp | Append new snapshots for time series analysis |
| Company Metrics | Append Snapshot | ticker + fetch_timestamp | Append new snapshots for time series analysis |

## Detailed Strategies

### 1. Skip Duplicates (CEO Profiles)

**Why**: CEO information rarely changes and should only be inserted once. Avoid streaming buffer issues.

**Implementation**:
```python
# Check if profile already exists
query = f"SELECT ticker FROM `{table_ref}` WHERE ticker = '{ticker}' LIMIT 1"
result = list(self.client.query(query).result())
if result:
    logger.info(f"CEO profile for {ticker} already exists, skipping")
    return

# Insert new data if not exists
self.client.insert_rows_json(table_ref, rows)
```

**Tables**:
- `ceo_profiles` - CEO information changes infrequently, only insert if doesn't exist

### 2. Skip Duplicates (Time Series Data)

**Why**: These are time series data where new entries are added over time, but historical data doesn't change.

**Implementation for Quarterly Earnings**:
```python
# Get existing periods for this ticker
query = f"SELECT DISTINCT TIMESTAMP(period) as period FROM `{table_ref}` WHERE ticker = '{ticker}'"
existing_periods = set(row.period for row in self.client.query(query).result())

# Only insert new periods
for earning in earnings_list:
    period_dt = pd.to_datetime(earning['period'])
    if period_dt not in existing_periods:
        rows.append(earning)

self.client.insert_rows_json(table_ref, rows)
```

**Implementation for Financial Statements**:
```python
# Get existing fiscal dates for this ticker
query = f"SELECT DISTINCT TIMESTAMP(fiscal_date) as fiscal_date FROM `{table_ref}` WHERE ticker = '{ticker}'"
existing_fiscal_dates = set(row.fiscal_date for row in self.client.query(query).result())

# Only insert metrics for new fiscal dates
for fiscal_date, metrics in statement_data.items():
    fiscal_date_dt = pd.to_datetime(fiscal_date)
    if fiscal_date_dt not in existing_fiscal_dates:
        for metric_name, metric_value in metrics.items():
            rows.append({
                'ticker': ticker,
                'fiscal_date': fiscal_date,
                'metric_name': metric_name,
                'metric_value': metric_value
            })

self.client.insert_rows_json(table_ref, rows)
```

**Implementation for Stock Prices**:
```python
# Get existing dates for this ticker
query = f"SELECT DISTINCT DATE(date) as date FROM `{table_ref}` WHERE ticker = '{ticker}'"
existing_dates = set(row.date for row in self.client.query(query).result())

# Filter DataFrame to only include new dates
prices_df = prices_df[~prices_df['date'].isin(existing_dates)]

# Upload only new dates
self.client.load_table_from_dataframe(prices_df, table_ref)
```

**Implementation for Social Media Posts**:
```python
# Get existing post IDs
query = f"SELECT DISTINCT post_id FROM `{table_ref}` WHERE ticker = '{ticker}'"
existing_post_ids = set(row.post_id for row in self.client.query(query).result())

# Only insert posts not in existing_post_ids
for post in posts_data:
    if post['id'] not in existing_post_ids:
        rows.append(post)

self.client.insert_rows_json(table_ref, rows)
```

**Tables**:
- `quarterly_earnings` - Check period uniqueness (fiscal quarters)
- `financial_statements` - Check fiscal_date uniqueness (annual/quarterly filings)
- `stock_prices` - Check date uniqueness (daily prices)
- `reddit_posts` - Check post_id uniqueness
- `x_posts` - Check post_id uniqueness

**Benefits**:
- Avoids duplicate data
- Preserves historical time series
- Only adds new content
- Efficient for daily incremental updates
- Logs how many duplicates were skipped

### 3. Append Snapshot (Sector/Company Metrics)

**Why**: These are calculated aggregates that change over time. We want to track trends.

**Implementation**:
```python
# Simply insert new rows with current timestamp
rows.append({
    "sector": sector_name,
    "fetch_timestamp": datetime.now(),
    ...
})

self.client.insert_rows_json(table_ref, rows)
```

**Tables**:
- `sector_metrics` - Track how sector averages change over time
- `company_metrics` - Track how company metrics evolve

**Benefits**:
- Time series analysis
- Trend detection
- Historical comparison

## Query Examples

### Get Latest CEO Profile
```sql
SELECT *
FROM `project.deep_alpha_copilot.ceo_profiles`
WHERE ticker = 'NVDA'
ORDER BY fetch_timestamp DESC
LIMIT 1
```

### Get Stock Prices for Last 30 Days
```sql
SELECT
  date,
  close,
  volume
FROM `project.deep_alpha_copilot.stock_prices`
WHERE ticker = 'NVDA'
  AND date >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY date DESC
```

### Get New Reddit Posts Today
```sql
SELECT *
FROM `project.deep_alpha_copilot.reddit_posts`
WHERE ticker = 'NVDA'
  AND DATE(fetch_timestamp) = CURRENT_DATE()
ORDER BY created_utc DESC
```

### Track Sector Metrics Over Time
```sql
SELECT
  DATE(fetch_timestamp) as date,
  sector,
  avg_pe_ratio,
  quality_score
FROM `project.deep_alpha_copilot.sector_metrics`
WHERE sector = 'Technology'
ORDER BY date DESC
LIMIT 30
```

### Deduplicate Query (if needed)
```sql
-- Get unique Reddit posts (in case of duplicates)
SELECT * FROM (
  SELECT *,
    ROW_NUMBER() OVER (
      PARTITION BY ticker, post_id
      ORDER BY fetch_timestamp DESC
    ) as row_num
  FROM `project.deep_alpha_copilot.reddit_posts`
)
WHERE row_num = 1
```

## Cost Optimization

### DELETE Operations
- Delete queries cost based on bytes scanned
- Partitioned tables can reduce costs
- Current implementation: ~$0.005 per GB scanned

### Query Operations
- Checking existing post_ids costs ~$0.005 per GB scanned
- Optimized with `SELECT DISTINCT post_id WHERE ticker = ...`
- Uses partition pruning when available

### Storage Costs
- BigQuery storage: $0.02 per GB/month
- Active storage (modified in last 90 days): $0.02 per GB/month
- Long-term storage (untouched for 90 days): $0.01 per GB/month

## Monitoring Deduplication

All upload methods log detailed information:

```
✅ Uploaded CEO profile for NVDA
Found 20 existing earnings periods for NVDA
✅ Uploaded 1 new quarterly earnings for NVDA (skipped 19 existing periods)
Found 5 existing fiscal dates for NVDA
✅ Uploaded 2000 financial statement rows for NVDA (1 new fiscal dates)
Found 1256 existing price dates for NVDA
✅ Uploaded 5 new price rows for NVDA (skipped 1256 existing dates)
No new price data to upload for TSM (all 1261 dates already exist)
✅ Uploaded 15 new Reddit posts for NVDA (skipped 5 duplicates)
✅ Uploaded 8 new X posts for NVDA (skipped 2 duplicates)
No new X posts to upload for TSM (all 10 posts already exist)
✅ Uploaded 1 sector metrics
✅ Uploaded 5 company metrics
```

## Best Practices

1. **Daily Runs**: The deduplication logic is optimized for daily runs
2. **Error Handling**: All operations wrapped in try-catch blocks
3. **Logging**: Detailed logs for tracking duplicates and errors
4. **Efficiency**: Queries use indexes and partitions when available
5. **Time Series**: Metrics tables preserve historical trends

## Future Enhancements

Potential improvements:
- Use MERGE statements for true upsert operations
- Add data validation before upload
- Implement incremental updates for large datasets
- Add data quality checks
- Implement retention policies (delete old data)
