#!/usr/bin/env python3
"""
Test script to fetch X/Twitter data for NVDA only.
"""

import os
import json
from datetime import datetime
from dotenv import load_dotenv
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Load environment
load_dotenv()

# Import X functions from fetch_data
from fetch_data import (
    initialize_x_client,
    fetch_x_data_for_company,
    analyze_sentiment,
    extract_topics,
    logger,
    X_DATA_DIR
)

if __name__ == "__main__":
    print("=" * 80)
    print("TESTING X DATA COLLECTION FOR NVDA")
    print("=" * 80)
    print()

    # Test data for NVDA
    ticker = "NVDA"
    company_name = "NVIDIA CORP"
    ceo_name = "Jensen Huang"

    print(f"Company: {company_name}")
    print(f"Ticker: ${ticker}")
    print(f"CEO: {ceo_name}")
    print()

    # Initialize X client
    print("Step 1: Initializing X API client...")
    client = initialize_x_client()

    if not client:
        print("❌ Failed to initialize X client. Check your X_BEARER_TOKEN in .env")
        exit(1)

    print("✅ X client initialized successfully")
    print()

    # Initialize sentiment analyzer
    print("Step 2: Initializing sentiment analyzer...")
    analyzer = SentimentIntensityAnalyzer()
    print("✅ Sentiment analyzer ready")
    print()

    # Fetch X data
    print("Step 3: Fetching X posts for NVDA...")
    print("-" * 80)

    try:
        result = fetch_x_data_for_company(
            client=client,
            ticker=ticker,
            company_name=company_name,
            ceo_name=ceo_name,
            analyzer=analyzer
        )

        print()
        print("=" * 80)
        print("RESULTS")
        print("=" * 80)
        print()

        # Summary statistics
        print(f"📊 Company Posts Found: {result['total_company_posts']}")
        print(f"👔 CEO Posts Found: {result['total_ceo_posts']}")
        print()

        # Show sample company posts
        if result['company_posts']:
            print("=" * 80)
            print("SAMPLE COMPANY POSTS (First 3)")
            print("=" * 80)
            print()

            for i, post in enumerate(result['company_posts'][:3], 1):
                print(f"Post #{i}:")
                print(f"  Author: @{post['author_username']} ({post['author_name']})")
                print(f"  Text: {post['text'][:150]}...")
                print(f"  Sentiment: {post['sentiment']} (score: {post['compound_score']:.2f})")
                print(f"  Topics: {', '.join(post['topics']) if post['topics'] else 'None'}")
                print(f"  Engagement: ❤️ {post['like_count']} | 🔄 {post['retweet_count']} | 💬 {post['reply_count']}")
                print(f"  URL: {post['url']}")
                print()
        else:
            print("⚠️ No company posts found")
            print()

        # Show sample CEO posts
        if result['ceo_posts']:
            print("=" * 80)
            print("SAMPLE CEO POSTS (First 3)")
            print("=" * 80)
            print()

            for i, post in enumerate(result['ceo_posts'][:3], 1):
                print(f"Post #{i}:")
                print(f"  Author: @{post['author_username']} ({post['author_name']})")
                print(f"  Text: {post['text'][:150]}...")
                print(f"  Sentiment: {post['sentiment']} (score: {post['compound_score']:.2f})")
                print(f"  Topics: {', '.join(post['topics']) if post['topics'] else 'None'}")
                print(f"  Engagement: ❤️ {post['like_count']} | 🔄 {post['retweet_count']} | 💬 {post['reply_count']}")
                print(f"  URL: {post['url']}")
                print()
        else:
            print("⚠️ No CEO posts found")
            print()

        # Calculate sentiment distribution for company posts
        if result['company_posts']:
            bullish = sum(1 for p in result['company_posts'] if p['sentiment'] == 'bullish')
            bearish = sum(1 for p in result['company_posts'] if p['sentiment'] == 'bearish')
            neutral = sum(1 for p in result['company_posts'] if p['sentiment'] == 'neutral')

            print("=" * 80)
            print("COMPANY SENTIMENT DISTRIBUTION")
            print("=" * 80)
            print(f"🟢 Bullish: {bullish} ({bullish/len(result['company_posts'])*100:.1f}%)")
            print(f"🔴 Bearish: {bearish} ({bearish/len(result['company_posts'])*100:.1f}%)")
            print(f"⚪ Neutral: {neutral} ({neutral/len(result['company_posts'])*100:.1f}%)")
            print()

        # Save to file
        output_file = os.path.join(X_DATA_DIR, f"{ticker}_x_posts.json")
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print("=" * 80)
        print("FILE SAVED")
        print("=" * 80)
        print(f"✅ Saved to: {output_file}")
        print()

        # Show file size
        file_size = os.path.getsize(output_file)
        print(f"📦 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print()

        print("=" * 80)
        print("TEST COMPLETED SUCCESSFULLY! ✅")
        print("=" * 80)

    except Exception as e:
        print()
        print("=" * 80)
        print("ERROR")
        print("=" * 80)
        print(f"❌ {e}")
        import traceback
        traceback.print_exc()
