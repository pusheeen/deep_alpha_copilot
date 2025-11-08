#!/usr/bin/env python3
"""
Test script for YouTube video fetching functionality.

Before running this script, make sure to:
1. Set up your YOUTUBE_API_KEY in the .env file
   - Get one from: https://console.cloud.google.com/apis/credentials
   - Enable YouTube Data API v3 in your Google Cloud project
2. Set up your GEMINI_API_KEY in the .env file
3. Install required packages: pip install -r requirements.txt

Usage:
    python test_youtube.py
    or
    python test_youtube.py NVDA AMD  # Test specific tickers
"""

import sys
from fetch_data import fetch_youtube_data, fetch_youtube_videos_for_ticker
from target_tickers import TARGET_TICKERS
import json

def main():
    # Parse command-line arguments for specific tickers
    if len(sys.argv) > 1:
        test_tickers = [arg.strip().upper() for arg in sys.argv[1:]]
        print(f"Testing YouTube fetch for specific tickers: {test_tickers}")
    else:
        # Use default tickers
        test_tickers = TARGET_TICKERS
        print(f"Testing YouTube fetch for all target tickers: {test_tickers}")

    print("\n" + "="*60)
    print("YouTube Video Fetching Test")
    print("="*60)
    print("\nThis script will:")
    print("1. Search for official YouTube channels")
    print("2. Fetch recent videos from each channel")
    print("3. Generate summaries using Gemini 2.5 Pro")
    print("\nResults will be saved to: data/unstructured/youtube/")
    print("="*60 + "\n")

    # Fetch YouTube data
    fetch_youtube_data(tickers=test_tickers, max_videos_per_ticker=3)

    print("\n" + "="*60)
    print("Test completed!")
    print("="*60)

if __name__ == "__main__":
    main()
