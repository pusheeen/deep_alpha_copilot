#!/usr/bin/env python3
"""
Simple test script to fetch X/Twitter data for NVDA (just company posts, no CEO).
"""

import os
import json
import sys
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Try to import tweepy
try:
    import tweepy
except ImportError:
    print("❌ tweepy not installed. Run: pip install tweepy")
    sys.exit(1)

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
from fetch_data import analyze_sentiment, extract_topics, X_DATA_DIR

def simple_fetch_x():
    """Simple X data fetch for NVDA."""

    print("=" * 80)
    print("SIMPLE X DATA FETCH TEST FOR NVDA")
    print("=" * 80)
    print()

    # Initialize X client
    bearer_token = os.getenv('X_BEARER_TOKEN')
    if not bearer_token:
        print("❌ X_BEARER_TOKEN not found in .env")
        return

    print("✅ Bearer token found")
    print()

    try:
        client = tweepy.Client(bearer_token=bearer_token)
        print("✅ X client initialized")
        print()
    except Exception as e:
        print(f"❌ Failed to initialize client: {e}")
        return

    # Search for NVDA posts (past 7 days, limit 10)
    print("Step 1: Searching for NVDA posts...")
    print("Query: $NVDA -is:retweet lang:en")
    print("Time range: Past 7 days (free tier limit)")
    print("Max results: 10")
    print()

    try:
        start_time = datetime.now() - timedelta(days=7)

        tweets = client.search_recent_tweets(
            query='$NVDA -is:retweet lang:en',
            max_results=10,
            start_time=start_time,
            tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
            expansions=['author_id'],
            user_fields=['username', 'name', 'verified']
        )

        if not tweets.data:
            print("⚠️ No tweets found")
            return

        print(f"✅ Found {len(tweets.data)} tweets")
        print()

        # Build user lookup
        users = {}
        if tweets.includes and 'users' in tweets.includes:
            for user in tweets.includes['users']:
                users[user.id] = {
                    'username': user.username,
                    'name': user.name,
                    'verified': getattr(user, 'verified', False)
                }

        # Initialize sentiment analyzer
        analyzer = SentimentIntensityAnalyzer()

        # Process tweets
        posts = []
        print("=" * 80)
        print("POSTS")
        print("=" * 80)
        print()

        for i, tweet in enumerate(tweets.data, 1):
            author_info = users.get(tweet.author_id, {
                'username': 'unknown',
                'name': 'Unknown',
                'verified': False
            })

            # Analyze sentiment
            sentiment_data = analyze_sentiment(tweet.text, analyzer)
            topics = extract_topics(tweet.text)

            post = {
                'id': tweet.id,
                'text': tweet.text,
                'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                'author_username': author_info['username'],
                'author_name': author_info['name'],
                'author_verified': author_info['verified'],
                'retweet_count': tweet.public_metrics.get('retweet_count', 0) if tweet.public_metrics else 0,
                'reply_count': tweet.public_metrics.get('reply_count', 0) if tweet.public_metrics else 0,
                'like_count': tweet.public_metrics.get('like_count', 0) if tweet.public_metrics else 0,
                'quote_count': tweet.public_metrics.get('quote_count', 0) if tweet.public_metrics else 0,
                'sentiment': sentiment_data['sentiment'],
                'compound_score': sentiment_data['compound_score'],
                'topics': topics,
                'url': f"https://twitter.com/{author_info['username']}/status/{tweet.id}"
            }
            posts.append(post)

            # Display
            print(f"📝 Post #{i}")
            print(f"   Author: @{post['author_username']} ({post['author_name']})")
            print(f"   Text: {post['text'][:200]}")
            if len(post['text']) > 200:
                print(f"         {'...' + post['text'][-50:]}")
            print(f"   Sentiment: {post['sentiment']} (score: {post['compound_score']:.2f})")
            print(f"   Topics: {', '.join(post['topics']) if post['topics'] else 'None'}")
            print(f"   Engagement: ❤️  {post['like_count']} | 🔄 {post['retweet_count']} | 💬 {post['reply_count']}")
            print(f"   URL: {post['url']}")
            print()

        # Sentiment distribution
        bullish = sum(1 for p in posts if p['sentiment'] == 'bullish')
        bearish = sum(1 for p in posts if p['sentiment'] == 'bearish')
        neutral = sum(1 for p in posts if p['sentiment'] == 'neutral')

        print("=" * 80)
        print("SENTIMENT DISTRIBUTION")
        print("=" * 80)
        print(f"🟢 Bullish: {bullish} ({bullish/len(posts)*100:.1f}%)")
        print(f"🔴 Bearish: {bearish} ({bearish/len(posts)*100:.1f}%)")
        print(f"⚪ Neutral: {neutral} ({neutral/len(posts)*100:.1f}%)")
        print()

        # Save to file
        result = {
            'ticker': 'NVDA',
            'company_name': 'NVIDIA CORP',
            'company_posts': posts,
            'total_company_posts': len(posts),
            'fetch_timestamp': datetime.now().isoformat(),
            'time_range_days': 7
        }

        output_file = os.path.join(X_DATA_DIR, "NVDA_x_posts.json")
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        print("=" * 80)
        print("FILE SAVED")
        print("=" * 80)
        print(f"✅ Saved to: {output_file}")
        file_size = os.path.getsize(output_file)
        print(f"📦 File size: {file_size:,} bytes ({file_size/1024:.1f} KB)")
        print()

        print("=" * 80)
        print("TEST COMPLETED SUCCESSFULLY! ✅")
        print("=" * 80)

    except tweepy.errors.TooManyRequests as e:
        print(f"❌ Rate limit exceeded: {e}")
        print("⏳ Please wait 15 minutes before trying again")
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    simple_fetch_x()
