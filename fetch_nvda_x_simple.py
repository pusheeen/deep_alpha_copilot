#!/usr/bin/env python3
"""
Fetch LIVE X/Twitter data for NVDA using simpler API call (no date restrictions).
Includes spam filtering for high-quality posts only.
"""

import json
import os
import tweepy
from datetime import datetime
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# Import topic extraction from fetch_data
import sys
sys.path.insert(0, os.path.dirname(__file__))
from fetch_data import extract_topics, analyze_sentiment

# Spam keywords to filter out
SPAM_KEYWORDS = [
    'BSDchallenge', 'BSDairdrop', 'simulation market',
    'earned +', 'BSD in the', '@BlockSt_HQ',
    'I just earned', 'please retweet', 'retweet for'
]

def is_spam_post(text):
    """Check if post contains spam keywords"""
    text_lower = text.lower()
    return any(keyword.lower() in text_lower for keyword in SPAM_KEYWORDS)

def is_quality_post(post):
    """
    Filter for quality posts based on:
    - Not spam
    - Has engagement (5+ likes OR 1+ retweet) OR is from verified account
    - Not too short (more than 20 characters)
    """
    # Check spam
    if is_spam_post(post['text']):
        return False

    # Check length
    if len(post['text']) < 20:
        return False

    # Check engagement or verification
    has_engagement = post.get('like_count', 0) >= 5 or post.get('retweet_count', 0) >= 1
    is_verified = post.get('author_verified', False)

    return has_engagement or is_verified

print("=" * 80)
print("FETCHING LIVE X/TWITTER DATA FOR NVDA (SIMPLIFIED)")
print("=" * 80)
print()

# Initialize X client
print("Initializing X/Twitter API client...")
bearer_token = os.getenv('X_BEARER_TOKEN')

if not bearer_token:
    print("❌ No X_BEARER_TOKEN found in environment")
    exit(1)

client = tweepy.Client(bearer_token=bearer_token)
print("✅ X API client initialized\n")

# Initialize sentiment analyzer
analyzer = SentimentIntensityAnalyzer()

# Fetch company posts (no start_time to avoid API restrictions)
print("Fetching company posts about NVDA...")

company_posts = []
try:
    # Simple search without date restrictions and cashtag (Basic tier limitation)
    tweets = client.search_recent_tweets(
        query='(NVDA OR "NVIDIA") -is:retweet lang:en',
        max_results=100,  # Get up to 100 recent tweets for comprehensive data
        tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
        expansions=['author_id'],
        user_fields=['username', 'name', 'verified']
    )

    if tweets.data:
        # Build user lookup
        users = {}
        if tweets.includes and 'users' in tweets.includes:
            for user in tweets.includes['users']:
                users[user.id] = {
                    'username': user.username,
                    'name': user.name,
                    'verified': getattr(user, 'verified', False)
                }

        # Process tweets
        for tweet in tweets.data:
            user_info = users.get(tweet.author_id, {})

            # Analyze sentiment
            sentiment_data = analyze_sentiment(tweet.text, analyzer)

            post = {
                'id': str(tweet.id),
                'text': tweet.text,
                'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                'author_id': str(tweet.author_id),
                'author_username': user_info.get('username', 'unknown'),
                'author_name': user_info.get('name', 'Unknown'),
                'author_verified': user_info.get('verified', False),
                'retweet_count': tweet.public_metrics.get('retweet_count', 0),
                'reply_count': tweet.public_metrics.get('reply_count', 0),
                'like_count': tweet.public_metrics.get('like_count', 0),
                'quote_count': tweet.public_metrics.get('quote_count', 0),
                'lang': tweet.lang,
                'url': f"https://twitter.com/{user_info.get('username', 'i')}/status/{tweet.id}",
                'sentiment': sentiment_data['sentiment'],
                'compound_score': sentiment_data['compound_score'],
                'positive_score': sentiment_data['positive_score'],
                'negative_score': sentiment_data['negative_score'],
                'topics': extract_topics(tweet.text)
            }

            company_posts.append(post)

        # Filter for quality posts
        initial_count = len(company_posts)
        company_posts = [p for p in company_posts if is_quality_post(p)]
        filtered_count = initial_count - len(company_posts)

        print(f"✅ Found {len(company_posts)} quality company posts ({filtered_count} spam filtered)\n")
    else:
        print("⚠️ No tweets found\n")

except Exception as e:
    print(f"❌ Error searching: {e}\n")

# Fetch CEO posts
print("Fetching posts about Jensen Huang...")

ceo_posts = []
try:
    tweets = client.search_recent_tweets(
        query='"Jensen Huang" (NVIDIA OR NVDA) -is:retweet lang:en',
        max_results=100,  # Get up to 100 CEO-related tweets for comprehensive data
        tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
        expansions=['author_id'],
        user_fields=['username', 'name', 'verified']
    )

    if tweets.data:
        # Build user lookup
        users = {}
        if tweets.includes and 'users' in tweets.includes:
            for user in tweets.includes['users']:
                users[user.id] = {
                    'username': user.username,
                    'name': user.name,
                    'verified': getattr(user, 'verified', False)
                }

        # Process tweets
        for tweet in tweets.data:
            user_info = users.get(tweet.author_id, {})

            # Analyze sentiment
            sentiment_data = analyze_sentiment(tweet.text, analyzer)

            post = {
                'id': str(tweet.id),
                'text': tweet.text,
                'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                'author_id': str(tweet.author_id),
                'author_username': user_info.get('username', 'unknown'),
                'author_name': user_info.get('name', 'Unknown'),
                'author_verified': user_info.get('verified', False),
                'retweet_count': tweet.public_metrics.get('retweet_count', 0),
                'reply_count': tweet.public_metrics.get('reply_count', 0),
                'like_count': tweet.public_metrics.get('like_count', 0),
                'quote_count': tweet.public_metrics.get('quote_count', 0),
                'lang': tweet.lang,
                'url': f"https://twitter.com/{user_info.get('username', 'i')}/status/{tweet.id}",
                'sentiment': sentiment_data['sentiment'],
                'compound_score': sentiment_data['compound_score'],
                'positive_score': sentiment_data['positive_score'],
                'negative_score': sentiment_data['negative_score'],
                'topics': extract_topics(tweet.text)
            }

            ceo_posts.append(post)

        # Filter for quality posts
        initial_count = len(ceo_posts)
        ceo_posts = [p for p in ceo_posts if is_quality_post(p)]
        filtered_count = initial_count - len(ceo_posts)

        print(f"✅ Found {len(ceo_posts)} quality CEO posts ({filtered_count} spam filtered)\n")
    else:
        print("⚠️ No tweets found\n")

except Exception as e:
    print(f"❌ Error searching: {e}\n")

# Compile data
x_data = {
    'ticker': 'NVDA',
    'company_name': 'NVIDIA CORP',
    'ceo_name': 'Jensen Huang',
    'company_posts': company_posts,
    'ceo_posts': ceo_posts,
    'total_company_posts': len(company_posts),
    'total_ceo_posts': len(ceo_posts),
    'fetch_timestamp': datetime.now().isoformat()
}

# Save to file
output_file = f"data/unstructured/x/NVDA_x_posts_live_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
with open(output_file, 'w') as f:
    json.dump(x_data, f, indent=2)

print("=" * 80)
print("LIVE X/TWITTER DATA SUMMARY (HIGH-QUALITY POSTS ONLY)")
print("=" * 80)
print(f"Company Posts: {len(company_posts)} (spam filtered)")
print(f"CEO Posts: {len(ceo_posts)} (spam filtered)")
print(f"Total Quality Posts: {len(company_posts) + len(ceo_posts)}")
print()

if company_posts or ceo_posts:
    all_posts = company_posts + ceo_posts

    # Sentiment summary
    bullish = sum(1 for p in all_posts if p['sentiment'] == 'bullish')
    bearish = sum(1 for p in all_posts if p['sentiment'] == 'bearish')
    neutral = sum(1 for p in all_posts if p['sentiment'] == 'neutral')

    print("Sentiment:")
    print(f"  Bullish: {bullish}")
    print(f"  Bearish: {bearish}")
    print(f"  Neutral: {neutral}")
    print()

    # Show sample posts
    print("Sample posts:")
    for i, post in enumerate(all_posts[:3], 1):
        print(f"\n{i}. {post['text'][:80]}...")
        print(f"   @{post['author_username']}")
        print(f"   Sentiment: {post['sentiment']} ({post['compound_score']:.2f})")
        print(f"   {post['like_count']} likes, {post['retweet_count']} retweets")

print()
print("=" * 80)
print(f"✅ Data saved to: {output_file}")
print("=" * 80)
