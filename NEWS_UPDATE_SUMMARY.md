# News API & Cache Updates - December 3, 2025

## ✅ Changes Completed

### 1. API Test Results
- **Status**: ✅ **WORKING**
- **Test**: Fetched news for NVDA
- **Results**: 
  - 8 articles found
  - Latest article: Dec 2, 2025 (The Motley Fool)
  - All articles within 72-hour window
  - API functioning correctly

### 2. Cache Refresh Frequency
- **Before**: 30 minutes
- **After**: **12 hours** ✅
- **Location**: `app/main.py` line 190
- **Change**: `REALTIME_NEWS_TTL = timedelta(hours=12)`

### 3. UI Updates

#### Header Indicator
- Added: "(Refreshes every 12 hours)" indicator in section header
- Location: News section title
- Visual: Small gray text next to title

#### Last Updated Timestamp
- Added: "Last updated: [timestamp] ([time ago])" display
- Location: Above news articles list
- Format Examples:
  - "Last updated: 12/3/2025, 2:21 PM (5m ago)"
  - "Last updated: 12/3/2025, 2:21 PM (2h 30m ago)"
  - "Last updated: 12/3/2025, 2:21 PM (13h ago - refresh due)"

#### Section Title Update
- Updated: "Latest News Coverage" → "Latest News Coverage (Last 72 Hours)"
- Clarifies the time window for users

---

## How It Works Now

### Cache Behavior
1. **First Request**: Fetches fresh news from Google Search API
2. **Cached Requests**: Returns cached data if < 12 hours old
3. **After 12 Hours**: Automatically fetches fresh news on next request
4. **Window**: Always fetches last 72 hours of news

### User Experience
- **Header**: Shows "(Refreshes every 12 hours)" indicator
- **Timestamp**: Shows when news was last fetched
- **Refresh Status**: Indicates if refresh is due (>12 hours old)

---

## Technical Details

### Cache File Location
- `data/runtime/news/{TICKER}_realtime_news.json`
- Contains: articles, summary, fetched_at timestamp

### API Endpoint
- `/api/latest-news/{ticker}`
- Checks cache first, fetches if expired
- Returns news from last 72 hours

### Cache Logic
```python
# Check cache
payload = _load_cached_news(ticker)
if not payload:  # Cache expired or doesn't exist
    payload = fetch_realtime_news(ticker, window_hours=72)
    _save_cached_news(ticker, payload)
```

---

## Testing

✅ **API Test**: Passed (8 articles found)  
✅ **Cache TTL**: Updated to 12 hours  
✅ **UI Display**: Timestamp and refresh indicator added  

---

**Status**: ✅ **COMPLETE**  
**Date**: December 3, 2025

