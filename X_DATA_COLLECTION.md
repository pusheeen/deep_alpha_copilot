# X/Twitter Data Collection

This module fetches X (Twitter) posts about companies and their CEOs from the past 6 months.

## Features

- **Company Posts**: Searches for posts mentioning the company ticker or company name
- **CEO Posts**: Searches for posts mentioning the CEO in relation to the company
- **Sentiment Analysis**: Uses VADER sentiment analyzer to classify posts as bullish/bearish/neutral
- **Topic Extraction**: Automatically tags posts with relevant topics (earnings, AI, crypto, etc.)
- **Engagement Metrics**: Captures retweets, likes, replies, and quote tweets
- **Rate Limiting**: Built-in retry mechanism and rate limit handling

## Setup

### 1. Install Dependencies

```bash
pip install tweepy
```

### 2. Get X API Credentials

You need X API v2 credentials. There are two options:

#### Option A: Bearer Token (Recommended)
1. Go to [X Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Create a new project and app (if you don't have one)
3. Generate a Bearer Token
4. Add to your `.env` file:
   ```
   X_BEARER_TOKEN="your_bearer_token_here"
   ```

#### Option B: OAuth Credentials
1. Go to [X Developer Portal](https://developer.twitter.com/en/portal/dashboard)
2. Navigate to your app settings
3. Get your API Key, API Secret, Access Token, and Access Token Secret
4. Add to your `.env` file:
   ```
   X_API_KEY="your_api_key"
   X_API_SECRET="your_api_secret"
   X_ACCESS_TOKEN="your_access_token"
   X_ACCESS_TOKEN_SECRET="your_access_token_secret"
   ```

### 3. Access Level Requirements

To use the search functionality, you need at least **Basic** access to the X API v2:
- Free tier allows 500k tweets/month
- Academic Research access provides higher limits

## Usage

### Standalone Script

Fetch X data for all companies:

```bash
python fetch_x_data.py
```

### As Part of Full Pipeline

X data collection is automatically included when running the full pipeline:

```bash
python fetch_data.py
```

### Programmatic Usage

```python
from fetch_data import fetch_x_data, fetch_x_data_for_company, initialize_x_client
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Fetch all companies
fetch_x_data()

# Or fetch for a single company
client = initialize_x_client()
analyzer = SentimentIntensityAnalyzer()
result = fetch_x_data_for_company(
    client=client,
    ticker="NVDA",
    company_name="NVIDIA CORP",
    ceo_name="Jensen Huang",
    analyzer=analyzer
)
```

## Output Structure

Data is saved to `data/unstructured/x/`:

### Individual Company Files
`{TICKER}_x_posts.json`:
```json
{
  "ticker": "NVDA",
  "company_name": "NVIDIA CORP",
  "ceo_name": "Jensen Huang",
  "company_posts": [
    {
      "id": "1234567890",
      "text": "NVIDIA crushes earnings expectations!",
      "created_at": "2025-10-10T10:30:00",
      "author_username": "stocktrader",
      "author_name": "Stock Trader",
      "author_verified": false,
      "retweet_count": 150,
      "reply_count": 45,
      "like_count": 890,
      "quote_count": 23,
      "sentiment": "bullish",
      "compound_score": 0.85,
      "positive_score": 0.75,
      "negative_score": 0.05,
      "topics": ["earnings", "AI"],
      "url": "https://twitter.com/stocktrader/status/1234567890"
    }
  ],
  "ceo_posts": [
    {
      "id": "9876543210",
      "text": "Jensen Huang's keynote at GTC was incredible!",
      "created_at": "2025-10-09T15:20:00",
      "sentiment": "bullish",
      "topics": ["news", "AI"]
    }
  ],
  "total_company_posts": 100,
  "total_ceo_posts": 45,
  "fetch_timestamp": "2025-10-10T12:00:00"
}
```

### Summary File
`x_data_summary_{timestamp}.json`:
```json
{
  "fetch_timestamp": "2025-10-10T12:00:00",
  "total_companies": 6588,
  "successful_fetches": 6500,
  "time_range_months": 6,
  "companies": [ /* array of all company results */ ]
}
```

## Configuration

Edit `fetch_data.py` to customize:

```python
# Time range (in months)
X_MONTHS_BACK = 6

# Maximum posts per search
max_results = 100  # Max allowed by X API per request
```

## Rate Limits

The X API v2 has rate limits:
- **Basic tier**: 450 requests per 15 minutes
- Script includes automatic retry with exponential backoff
- Built-in rate limit detection and 15-minute wait period

With 6,588 companies and ~2 requests per company (company + CEO search):
- Total requests: ~13,000
- Estimated time: 4-6 hours (with rate limiting)

## Troubleshooting

### Error: "X API credentials not found"
- Check your `.env` file has X API credentials
- Ensure `.env` file is in the project root directory

### Error: "Rate limit exceeded"
- Script will automatically wait 15 minutes and retry
- Consider reducing the number of companies or increasing delay between requests

### Error: "tweepy not installed"
- Install tweepy: `pip install tweepy`

### No results found
- Check if the ticker/company name is correct
- Try manually searching on X to verify posts exist
- Some companies may have very low social media presence

## Best Practices

1. **Run during off-peak hours**: X API rate limits are shared across all your apps
2. **Monitor progress**: Check `data_fetch.log` for detailed progress
3. **Incremental collection**: The script saves each company individually, so you can stop/resume
4. **Regular updates**: Run weekly/monthly to keep data fresh

## Data Usage

The collected X data can be used for:
- Social media sentiment analysis
- Event detection (earnings, product launches, etc.)
- Correlation with stock price movements
- CEO reputation monitoring
- Market trend identification

## Privacy & Ethics

- Only public posts are collected
- No personal user information beyond username/display name
- Follows X API terms of service
- Data collected for research/analysis purposes only
