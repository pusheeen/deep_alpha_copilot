# YouTube Video Fetching Setup Guide

This guide explains how to use the YouTube video fetching and analysis functionality in `fetch_data.py`.

## Features

The YouTube integration provides:
- **Automatic channel discovery**: Finds official company YouTube channels
- **Recent video fetching**: Retrieves the latest videos from each channel
- **AI-powered analysis**: Uses Gemini 2.5 Pro to generate comprehensive summaries
- **Transcript processing**: Analyzes video transcripts when available
- **Fallback handling**: Analyzes title/description when transcripts aren't available

## Setup Instructions

### 1. Get a YouTube API Key

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Enable the **YouTube Data API v3**:
   - Navigate to "APIs & Services" > "Library"
   - Search for "YouTube Data API v3"
   - Click "Enable"
4. Create credentials:
   - Go to "APIs & Services" > "Credentials"
   - Click "Create Credentials" > "API Key"
   - Copy the generated API key

### 2. Configure Environment Variables

Add these variables to your `.env` file:

```bash
YOUTUBE_API_KEY=your_youtube_api_key_here
GEMINI_API_KEY=your_gemini_api_key_here
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

The key packages needed are:
- `google-api-python-client` - YouTube API client
- `youtube-transcript-api` - Transcript fetching
- `google-generativeai` - Gemini AI integration

## Usage

### Method 1: Test Script (Recommended for first run)

Use the test script to fetch videos for a few tickers:

```bash
# Test with specific tickers (3 videos per company)
python test_youtube.py NVDA AMD

# Test with all target tickers
python test_youtube.py
```

### Method 2: Python Import

Use the function directly in your Python code:

```python
from fetch_data import fetch_youtube_data, fetch_youtube_videos_for_ticker

# Fetch videos for specific tickers
fetch_youtube_data(tickers=['NVDA', 'AMD'], max_videos_per_ticker=5)

# Or fetch for a single company
videos = fetch_youtube_videos_for_ticker('NVDA', 'NVIDIA Corporation', max_videos=10)
print(f"Found {len(videos)} videos")
for video in videos:
    print(f"- {video['title']}: {video['url']}")
    print(f"  Summary: {video['summary'][:200]}...")
```

### Method 3: Standalone Function

Fetch only YouTube data without running the entire pipeline:

```bash
python -c "from fetch_data import fetch_youtube_data_only; fetch_youtube_data_only()"
```

## Output Format

Results are saved to `data/unstructured/youtube/youtube_videos_YYYYMMDD_HHMMSS.json`

Example output structure:

```json
{
  "NVDA": {
    "company_name": "NVIDIA CORP",
    "ticker": "NVDA",
    "fetched_at": "2025-11-03T10:30:00",
    "videos": [
      {
        "video_id": "abc123",
        "url": "https://www.youtube.com/watch?v=abc123",
        "title": "NVIDIA GTC 2025 Keynote",
        "published_at": "2025-03-20T14:00:00Z",
        "has_transcript": true,
        "summary": "Overview:\nNVIDIA's CEO Jensen Huang announced...\n\nKey Announcements:\n- New GPU architecture...\n..."
      }
    ]
  }
}
```

## YouTube Channel Mapping

Pre-configured channels are defined in `fetch_data.py`:

```python
COMPANY_YOUTUBE_CHANNELS = {
    'NVDA': 'UCOoVRHTi6TodJqZelnYkOKw',  # NVIDIA
    'AMD': 'UCWqubGZQYw4nP_F_z2Ht5FA',   # AMD
    'TSM': 'UCk7NMZd5_l-Ddu_KvQvuWVQ',   # TSMC
    'AVGO': 'UChdnhwmVGSEVDcCgvfvCjig',  # Broadcom
    'ORCL': 'UCaWLRwbEJdTpSNIFJNVqEKg',  # Oracle
    'ALB': 'UC0YlQUyMUEcQPMfIsFR-bfQ',   # Albemarle
    # Others will be auto-discovered
}
```

For companies without pre-configured channels, the system will automatically search for their official channel.

## API Rate Limits

Be aware of these limits:
- **YouTube API**: 10,000 quota units per day (default)
  - Search: 100 units per request
  - Videos list: 1 unit per request
- **Gemini API**: Check your Google Cloud quota

The implementation includes rate limiting delays to avoid hitting these limits.

## Troubleshooting

### "YOUTUBE_API_KEY not found"
Make sure your `.env` file contains the YouTube API key and is in the project root directory.

### "No transcript available"
This is normal for some videos. The system will fall back to analyzing the title and description.

### "Quota exceeded"
You've hit the YouTube API daily quota. Wait 24 hours or request a quota increase in Google Cloud Console.

### "Channel not found"
The automatic search couldn't find the company's channel. You can:
1. Manually find the channel ID on YouTube (in the channel URL)
2. Add it to `COMPANY_YOUTUBE_CHANNELS` in `fetch_data.py`

## Integration with Main Pipeline

To include YouTube fetching in the main data pipeline, add this to the `__main__` section of `fetch_data.py`:

```python
# Add after the X/Twitter data fetching section
logger.info("")
logger.info("=" * 60)
logger.info("FETCHING YOUTUBE DATA")
logger.info("=" * 60)
fetch_youtube_data()
```

## Notes

- Video summaries use **Gemini 2.5 Pro** for higher quality analysis
- Transcripts are limited to 50,000 characters to stay within API limits
- Results include both videos with and without transcripts
- The system respects rate limits with built-in delays
