#!/usr/bin/env python3
"""
Simple example showing how to use the YouTube video fetching functions.

This demonstrates the basic API for fetching and analyzing company YouTube videos.
"""

from fetch_data import fetch_youtube_videos_for_ticker
import json

def example_single_ticker():
    """Example: Fetch videos for a single company"""
    print("="*60)
    print("Example: Fetching YouTube videos for NVIDIA")
    print("="*60)

    # Fetch videos for NVIDIA
    ticker = 'NVDA'
    company_name = 'NVIDIA Corporation'
    max_videos = 3

    print(f"\nFetching {max_videos} recent videos for {company_name}...")
    videos = fetch_youtube_videos_for_ticker(
        ticker=ticker,
        company_name=company_name,
        max_videos=max_videos
    )

    # Display results
    if videos:
        print(f"\n✅ Successfully fetched {len(videos)} videos:\n")
        for i, video in enumerate(videos, 1):
            print(f"{i}. {video['title']}")
            print(f"   URL: {video['url']}")
            print(f"   Published: {video['published_at']}")
            print(f"   Has Transcript: {video['has_transcript']}")
            print(f"   Summary Preview: {video['summary'][:150]}...")
            print()
    else:
        print("❌ No videos were fetched. Check your API keys and logs.")

    # Save to file
    if videos:
        output_file = f"example_output_{ticker}.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump({
                'ticker': ticker,
                'company_name': company_name,
                'videos': videos
            }, f, indent=2, ensure_ascii=False)
        print(f"✅ Results saved to {output_file}")


def example_multiple_tickers():
    """Example: Fetch videos for multiple companies"""
    from fetch_data import fetch_youtube_data

    print("\n" + "="*60)
    print("Example: Fetching YouTube videos for multiple companies")
    print("="*60)

    # Specify which tickers to fetch
    tickers = ['NVDA', 'AMD']

    print(f"\nFetching videos for: {', '.join(tickers)}")
    print("This will create a timestamped JSON file in data/unstructured/youtube/\n")

    # Fetch videos for multiple tickers
    fetch_youtube_data(
        tickers=tickers,
        max_videos_per_ticker=3
    )

    print("\n✅ Batch fetch completed!")


if __name__ == "__main__":
    import sys

    print("\n" + "="*60)
    print("YouTube Video Fetching Examples")
    print("="*60)
    print("\nBefore running these examples, make sure you have:")
    print("1. YOUTUBE_API_KEY set in your .env file")
    print("2. GEMINI_API_KEY set in your .env file")
    print("3. Installed requirements: pip install -r requirements.txt")
    print("="*60 + "\n")

    if len(sys.argv) > 1 and sys.argv[1] == 'multiple':
        # Run example for multiple tickers
        example_multiple_tickers()
    else:
        # Run example for single ticker (default)
        example_single_ticker()

    print("\n" + "="*60)
    print("Example completed!")
    print("="*60)
    print("\nTo run the multiple tickers example:")
    print("  python example_youtube_usage.py multiple")
    print()
