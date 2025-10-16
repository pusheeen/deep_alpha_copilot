#!/usr/bin/env python3
"""
Display X/Twitter data for NVDA and show how to fetch live data.
"""

import json
import os
from pathlib import Path
from datetime import datetime

print("=" * 80)
print("X/TWITTER DATA FOR NVDA")
print("=" * 80)
print()

# Check for example data file
example_file = "data/unstructured/x/NVDA_x_posts_EXAMPLE.json"

if os.path.exists(example_file):
    print(f"Loading example X data from: {example_file}")
    print()

    with open(example_file, 'r') as f:
        x_data = json.load(f)

    print("=" * 80)
    print("COMPANY INFORMATION")
    print("=" * 80)
    print(f"Ticker:       {x_data['ticker']}")
    print(f"Company:      {x_data['company_name']}")
    print(f"CEO:          {x_data['ceo_name']}")
    print(f"Fetched:      {x_data['fetch_timestamp']}")
    print()

    print("=" * 80)
    print(f"COMPANY POSTS ({x_data['total_company_posts']} posts)")
    print("=" * 80)
    print()

    # Analyze sentiment distribution
    bullish = sum(1 for p in x_data['company_posts'] if p['sentiment'] == 'bullish')
    bearish = sum(1 for p in x_data['company_posts'] if p['sentiment'] == 'bearish')
    neutral = sum(1 for p in x_data['company_posts'] if p['sentiment'] == 'neutral')

    print(f"Sentiment Distribution:")
    print(f"  Bullish: {bullish} ({bullish/len(x_data['company_posts'])*100:.1f}%)")
    print(f"  Bearish: {bearish} ({bearish/len(x_data['company_posts'])*100:.1f}%)")
    print(f"  Neutral: {neutral} ({neutral/len(x_data['company_posts'])*100:.1f}%)")
    print()

    # Calculate average sentiment scores
    avg_compound = sum(p['compound_score'] for p in x_data['company_posts']) / len(x_data['company_posts'])
    print(f"Average Compound Score: {avg_compound:.2f}")
    print()

    # Show all posts
    for i, post in enumerate(x_data['company_posts'], 1):
        print(f"{i}. {post['text']}")
        print(f"   Author: @{post['author_username']} ({post['author_name']})")
        if post['author_verified']:
            print(f"   ✓ Verified")
        print(f"   Posted: {post['created_at']}")
        print(f"   Sentiment: {post['sentiment'].upper()} (score: {post['compound_score']:.2f})")
        print(f"   Engagement: {post['like_count']} likes, {post['retweet_count']} retweets")
        print(f"   Topics: {', '.join(post['topics'])}")
        print(f"   URL: {post['url']}")
        print()

    print("=" * 80)
    print(f"CEO POSTS ({x_data['total_ceo_posts']} posts about {x_data['ceo_name']})")
    print("=" * 80)
    print()

    for i, post in enumerate(x_data['ceo_posts'], 1):
        print(f"{i}. {post['text']}")
        print(f"   Author: @{post['author_username']} ({post['author_name']})")
        if post['author_verified']:
            print(f"   ✓ Verified")
        print(f"   Posted: {post['created_at']}")
        print(f"   Sentiment: {post['sentiment'].upper()} (score: {post['compound_score']:.2f})")
        print(f"   Engagement: {post['like_count']} likes, {post['retweet_count']} retweets")
        print(f"   Topics: {', '.join(post['topics'])}")
        print(f"   URL: {post['url']}")
        print()

    # Summary statistics
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    print()

    all_posts = x_data['company_posts'] + x_data['ceo_posts']
    total_likes = sum(p['like_count'] for p in all_posts)
    total_retweets = sum(p['retweet_count'] for p in all_posts)
    total_replies = sum(p['reply_count'] for p in all_posts)

    print(f"Total Posts:     {len(all_posts)}")
    print(f"Total Likes:     {total_likes:,}")
    print(f"Total Retweets:  {total_retweets:,}")
    print(f"Total Replies:   {total_replies:,}")
    print()

    # Topic analysis
    all_topics = []
    for post in all_posts:
        all_topics.extend(post['topics'])

    from collections import Counter
    topic_counts = Counter(all_topics)

    print("Top Topics:")
    for topic, count in topic_counts.most_common(5):
        print(f"  {topic}: {count}")
    print()

else:
    print("No example X data file found.")
    print()

print("=" * 80)
print("HOW TO FETCH LIVE X/TWITTER DATA")
print("=" * 80)
print()
print("To fetch live X/Twitter data for NVDA, you need:")
print()
print("1. X/Twitter API credentials (Bearer Token or OAuth)")
print("   - Sign up at: https://developer.twitter.com/")
print("   - Create a project and get API credentials")
print()
print("2. Add credentials to .env file:")
print("   X_BEARER_TOKEN=\"your_bearer_token_here\"")
print("   # OR use OAuth:")
print("   X_API_KEY=\"your_api_key\"")
print("   X_API_SECRET=\"your_api_secret\"")
print("   X_ACCESS_TOKEN=\"your_access_token\"")
print("   X_ACCESS_TOKEN_SECRET=\"your_access_secret\"")
print()
print("3. Run the fetch script:")
print("   python -c \"from fetch_data import fetch_x_data_for_company, initialize_x_client; \\")
print("              from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer; \\")
print("              client = initialize_x_client(); \\")
print("              analyzer = SentimentIntensityAnalyzer(); \\")
print("              data = fetch_x_data_for_company(client, 'NVDA', 'NVIDIA CORP', 'Jensen Huang', analyzer); \\")
print("              import json; print(json.dumps(data, indent=2))\"")
print()
print("=" * 80)
print("DATA STRUCTURE")
print("=" * 80)
print()
print("Each X data file contains:")
print("  - ticker: Stock symbol")
print("  - company_name: Full company name")
print("  - ceo_name: CEO name")
print("  - company_posts: Array of posts about the company")
print("  - ceo_posts: Array of posts about the CEO")
print("  - fetch_timestamp: When data was collected")
print()
print("Each post includes:")
print("  - text: Post content")
print("  - created_at: Post timestamp")
print("  - author info: username, name, verified status")
print("  - engagement: likes, retweets, replies, quotes")
print("  - sentiment: bullish/bearish/neutral + scores")
print("  - topics: AI, earnings, news, technical_analysis, etc.")
print("  - url: Link to original post")
print()
print("=" * 80)
