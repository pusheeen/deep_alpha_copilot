# Company News Fetching Function

## Overview

Added `get_company_news()` function to `fetch_data.py` for fetching recent news articles for any ticker using yfinance.

## Location

**File**: `fetch_data.py`
**Lines**: 1751-1815

## Function Signature

```python
def get_company_news(ticker: str, days: Optional[int] = None) -> List[Dict[str, Any]]
```

## Parameters

- `ticker` (str): Stock ticker symbol (e.g., 'NVDA', 'TSLA', 'AAPL')
- `days` (int, optional): Only return articles from the past N days. Default: None (returns all available)

**Note**: The function fetches ALL available articles from yfinance (no limits) and then filters by date if specified.

## Returns

List of dictionaries, each containing:
- `title` (str): Article headline
- `publisher` (str): News source (e.g., 'Bloomberg', 'Yahoo Finance')
- `link` (str): Direct URL to the article
- `publish_time` (str): Publication timestamp in ISO format
- `content_type` (str): Article type ('STORY', 'VIDEO', etc.)
- `summary` (str): Brief article summary/description
- `thumbnail` (str): URL to article thumbnail image (if available)

## Usage Examples

### Basic Usage

```python
from fetch_data import get_company_news

# Fetch ALL available news articles for NVDA (no limits)
news = get_company_news('NVDA')

for article in news:
    print(f"{article['title']}")
    print(f"Publisher: {article['publisher']}")
    print(f"Link: {article['link']}\n")
```

### Fetch News from the Past 7 Days

```python
# Fetch news from the past 7 days only
news = get_company_news('NVDA', days=7)

# Result: Only articles published within the last 7 days
```

### Fetch News from Different Time Ranges

```python
# Past 1 day
news_1d = get_company_news('TSLA', days=1)

# Past 3 days
news_3d = get_company_news('TSLA', days=3)

# Past 30 days
news_30d = get_company_news('TSLA', days=30)

print(f"Past 1 day: {len(news_1d)} articles")
print(f"Past 3 days: {len(news_3d)} articles")
print(f"Past 30 days: {len(news_30d)} articles")
```

### Save News from Past 7 Days to File

```python
import json
from datetime import datetime

tickers = ['NVDA', 'TSLA', 'AAPL']
all_news = {}

# Fetch only news from the past 7 days for each ticker
for ticker in tickers:
    all_news[ticker] = get_company_news(ticker, days=7)

# Save to JSON
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
with open(f'news_7days_{timestamp}.json', 'w') as f:
    json.dump(all_news, f, indent=2)
```

### Filter by Content Type

```python
news = get_company_news('NVDA', num_articles=20)

# Get only video content
videos = [article for article in news if article['content_type'] == 'VIDEO']

# Get only written stories
stories = [article for article in news if article['content_type'] == 'STORY']
```

## Example Output

```json
[
  {
    "title": "Q3 earnings will be 'validation moment' for AI spend: Dan Ives",
    "publisher": "Yahoo Finance Video",
    "link": "https://finance.yahoo.com/video/q3-earnings-validation-moment-ai-173000184.html",
    "publish_time": "2025-10-10T17:30:00Z",
    "content_type": "VIDEO",
    "summary": "Big Tech heavy hitters will report their third quarter earnings...",
    "thumbnail": "https://s.yimg.com/uu/api/res/1.2/NYBCq8PNOcTRVJ0ZQHvmNA--..."
  }
]
```

## Error Handling

The function includes comprehensive error handling:
- Returns empty list `[]` if no news is found
- Logs warnings for missing data
- Handles API errors gracefully
- Compatible with yfinance's nested content structure

## Integration with Existing Code

This function complements the existing analytics functions:
- `get_company_metrics()`: Financial metrics and performance data
- `aggregate_sector_sentiment()`: Social media sentiment analysis
- `compare_company_to_sector()`: Peer comparisons
- **`get_company_news()`**: Recent news articles (NEW)

## Example Scripts

### Basic News Fetching
See `example_fetch_news.py` for a complete working example that:
- Fetches news for multiple tickers
- Saves results to JSON file
- Displays formatted summary

```bash
python example_fetch_news.py
```

Output: `data/structured/company_news_TIMESTAMP.json`

### 7-Day News Filter
See `example_news_7days.py` for fetching news from the past 7 days:
- Fetches only recent news (past 7 days) for multiple tickers
- Shows publish dates for verification
- Saves filtered results to JSON

```bash
python example_news_7days.py
```

Output: `data/structured/news_7days_TIMESTAMP.json`

## Notes

- Uses yfinance's built-in `.news` property
- News data is fetched in real-time from Yahoo Finance
- No API key required
- Typical response includes 10+ articles per company
- Articles are sorted by recency (newest first)
- Supports all tickers available on Yahoo Finance

### Date Filtering

- When `days` parameter is specified, only articles from the past N days are returned
- Date comparison is timezone-aware (handles UTC timestamps correctly)
- If an article's publish date cannot be parsed, it's included anyway (failsafe behavior)
- The function fetches ALL available articles from yfinance (no limits), then filters by date

### Important Note: yfinance API Limitation

**yfinance typically returns approximately 10 articles per ticker**, regardless of the time range requested. This is a limitation of the Yahoo Finance API that yfinance uses, not our code.

The articles returned are usually very recent (typically from the past 24-48 hours), so:
- For a 7-day filter, you'll likely get all 10 available articles
- For shorter time ranges (1-2 days), you may get fewer after filtering
- The function is working correctly - it fetches everything available and filters appropriately

Example output:
```
NVDA: Fetched 10 news articles from the past 7 days (out of 10 total available)
```

This means all 10 available articles were within the 7-day window.
