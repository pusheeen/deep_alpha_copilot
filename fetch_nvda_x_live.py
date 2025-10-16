#!/usr/bin/env python3
"""
Fetch LIVE X/Twitter data for NVDA using configured API credentials.
"""

import json
from datetime import datetime
from fetch_data import fetch_x_data_for_company, initialize_x_client
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

print("=" * 80)
print("FETCHING LIVE X/TWITTER DATA FOR NVDA")
print("=" * 80)
print()

# Initialize X client with credentials from .env
print("Initializing X/Twitter API client...")
client = initialize_x_client()

if not client:
    print("❌ Failed to initialize X client. Check your credentials in .env file.")
    exit(1)

print("✅ X API client initialized\n")

# Initialize sentiment analyzer
print("Initializing sentiment analyzer...")
analyzer = SentimentIntensityAnalyzer()
print("✅ Sentiment analyzer ready\n")

# Fetch live data for NVDA
print("Fetching live X/Twitter data for NVDA...")
print("This may take a few moments due to API rate limits...\n")

try:
    x_data = fetch_x_data_for_company(
        client=client,
        ticker='NVDA',
        company_name='NVIDIA CORP',
        ceo_name='Jensen Huang',
        analyzer=analyzer
    )

    print("=" * 80)
    print("LIVE X/TWITTER DATA RETRIEVED")
    print("=" * 80)
    print()

    print(f"Ticker: {x_data['ticker']}")
    print(f"Company: {x_data['company_name']}")
    print(f"CEO: {x_data['ceo_name']}")
    print(f"Fetched: {x_data['fetch_timestamp']}")
    print()

    print(f"Company Posts: {x_data['total_company_posts']}")
    print(f"CEO Posts: {x_data['total_ceo_posts']}")
    print()

    # Save to file
    output_file = f"data/unstructured/x/NVDA_x_posts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(x_data, f, indent=2)

    print("=" * 80)
    print("DATA SAVED")
    print("=" * 80)
    print(f"✅ Live X data saved to: {output_file}")
    print()

    # Show sample posts
    if x_data['company_posts']:
        print("=" * 80)
        print("SAMPLE COMPANY POSTS")
        print("=" * 80)
        print()

        for i, post in enumerate(x_data['company_posts'][:3], 1):
            print(f"{i}. {post['text'][:100]}...")
            print(f"   @{post['author_username']}")
            print(f"   Sentiment: {post['sentiment']} (score: {post['compound_score']:.2f})")
            print(f"   Engagement: {post['like_count']} likes, {post['retweet_count']} retweets")
            print()

    if x_data['ceo_posts']:
        print("=" * 80)
        print("SAMPLE CEO POSTS")
        print("=" * 80)
        print()

        for i, post in enumerate(x_data['ceo_posts'][:2], 1):
            print(f"{i}. {post['text'][:100]}...")
            print(f"   @{post['author_username']}")
            print(f"   Sentiment: {post['sentiment']} (score: {post['compound_score']:.2f})")
            print(f"   Engagement: {post['like_count']} likes, {post['retweet_count']} retweets")
            print()

    # Sentiment summary
    all_posts = x_data['company_posts'] + x_data['ceo_posts']
    if all_posts:
        bullish = sum(1 for p in all_posts if p['sentiment'] == 'bullish')
        bearish = sum(1 for p in all_posts if p['sentiment'] == 'bearish')
        neutral = sum(1 for p in all_posts if p['sentiment'] == 'neutral')

        print("=" * 80)
        print("SENTIMENT SUMMARY")
        print("=" * 80)
        print(f"Bullish: {bullish} ({bullish/len(all_posts)*100:.1f}%)")
        print(f"Bearish: {bearish} ({bearish/len(all_posts)*100:.1f}%)")
        print(f"Neutral: {neutral} ({neutral/len(all_posts)*100:.1f}%)")

        avg_compound = sum(p['compound_score'] for p in all_posts) / len(all_posts)
        print(f"Average Compound Score: {avg_compound:.3f}")
        print()

    print("=" * 80)
    print("✅ SUCCESS - Real X/Twitter data fetched!")
    print("=" * 80)

except Exception as e:
    print("=" * 80)
    print("ERROR FETCHING X DATA")
    print("=" * 80)
    print(f"Error: {e}")
    print()
    print("Common issues:")
    print("  - API rate limits exceeded (wait 15 minutes)")
    print("  - Invalid bearer token")
    print("  - Network connectivity issues")
    print()
