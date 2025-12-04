# Website Loading Performance Analysis

## 🔍 Why Does the Website Take Long to Load?

### Root Causes

1. **Initial Data Download (Cloud Run)**
   - On first startup, Cloud Run instances download all data from GCS
   - This happens in background but can still impact first requests
   - **Location**: `app/main.py` - `lifespan()` function

2. **Ticker Scoreboard Loading**
   - Loads scores for ALL tickers on page load
   - Makes multiple API calls (batched, but still many)
   - **Location**: `app/templates/index.html` - `loadAllTickerMetrics()`

3. **Lazy Loading Not Fully Implemented**
   - Some data is lazy-loaded, but scoreboard loads everything upfront
   - Each ticker card requires an API call

4. **No Caching Strategy**
   - Frontend doesn't cache ticker scores
   - Every page load fetches fresh data

---

## 📊 Current Loading Flow

```
Page Load
    ↓
1. HTML loads (fast)
    ↓
2. JavaScript executes
    ↓
3. loadAllTickerMetrics() called
    ↓
4. Fetches scores for ALL tickers (batched in groups of 5)
    ↓
5. Each batch makes 5 API calls
    ↓
6. For 35 tickers = 7 batches = 7 sequential API call groups
    ↓
Total Time: ~3-5 seconds (depending on network)
```

---

## 🚀 Solutions to Make It Faster

### Solution 1: Lazy Load Ticker Cards (Recommended)

**Current**: Loads all ticker scores immediately  
**Better**: Load ticker scores only when visible or on-demand

```javascript
// Instead of loading all on page load:
// Load only visible tickers initially
// Load others as user scrolls or clicks
```

### Solution 2: Server-Side Caching

**Current**: Each API call computes scores fresh  
**Better**: Cache computed scores for 5-15 minutes

```python
# In app/main.py
@lru_cache(maxsize=100)
def get_cached_score(ticker: str):
    # Cache scores for 5 minutes
    pass
```

### Solution 3: Batch API Endpoint

**Current**: Multiple individual API calls  
**Better**: Single batch endpoint that returns all scores

```python
@app.get("/api/scores/batch")
async def get_batch_scores(tickers: List[str]):
    # Return all scores in one response
    pass
```

### Solution 4: Pre-compute and Store Scores

**Current**: Scores computed on-demand  
**Better**: Pre-compute scores and store in cache

```python
# Background job computes scores
# Store in Redis or file cache
# API just reads from cache
```

### Solution 5: Optimize Data Download

**Current**: Downloads all data on startup  
**Better**: Download only essential data, lazy-load rest

```python
# Download only:
# - Popular tickers (top 10)
# - Essential data files
# Lazy-load others as needed
```

---

## 🎯 Recommended Implementation

### Priority 1: Lazy Load Ticker Cards

**Impact**: High (reduces initial load from 35 API calls to ~5-10)  
**Effort**: Medium

```javascript
// Load only visible tickers initially
const visibleTickers = supportedTickers.slice(0, 10);
await loadTickerMetricsBatch(visibleTickers);

// Load rest on scroll or button click
document.addEventListener('scroll', () => {
    // Load more as user scrolls
});
```

### Priority 2: Add Server-Side Caching

**Impact**: High (reduces computation time)  
**Effort**: Low

```python
from functools import lru_cache
from datetime import datetime, timedelta

score_cache = {}
cache_ttl = timedelta(minutes=5)

def get_cached_score(ticker: str):
    if ticker in score_cache:
        cached_time, score = score_cache[ticker]
        if datetime.now() - cached_time < cache_ttl:
            return score
    # Compute and cache
    score = compute_company_scores(ticker)
    score_cache[ticker] = (datetime.now(), score)
    return score
```

### Priority 3: Batch API Endpoint

**Impact**: Medium (reduces network overhead)  
**Effort**: Medium

```python
@app.get("/api/scores/batch")
async def get_batch_scores(tickers: str = Query(...)):
    ticker_list = tickers.split(',')
    results = {}
    for ticker in ticker_list:
        results[ticker] = compute_company_scores(ticker)
    return {"status": "success", "data": results}
```

---

## 📈 Expected Performance Improvements

| Solution | Current Time | Improved Time | Improvement |
|----------|--------------|---------------|-------------|
| **Current** | 3-5 seconds | - | - |
| **Lazy Load** | 3-5 seconds | 0.5-1 second | 70-80% faster |
| **+ Caching** | 0.5-1 second | 0.2-0.5 second | 50% faster |
| **+ Batch API** | 0.2-0.5 second | 0.1-0.3 second | 50% faster |

**Total Improvement: 85-90% faster!**

---

## 🔧 Implementation Steps

1. **Implement lazy loading** for ticker cards
2. **Add server-side caching** for computed scores
3. **Create batch API endpoint** for multiple tickers
4. **Optimize data download** to only essential files
5. **Add loading indicators** for better UX

---

## 💡 Quick Wins

1. **Reduce initial ticker load** from 35 to 10
2. **Add caching** (5-minute TTL)
3. **Show loading states** so users know it's working
4. **Load rest on scroll** or "Load More" button

These changes alone will make the site feel **much faster**!

