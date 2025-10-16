#!/usr/bin/env python3
"""
Extract and display Reddit data for NVDA.
"""

import json
from collections import Counter
from datetime import datetime

print("=" * 80)
print("REDDIT DATA FOR NVDA")
print("=" * 80)
print()

# Load the most recent Reddit data file
reddit_file = "data/unstructured/reddit/reddit_posts_20251010_231732.json"

print(f"Loading Reddit data from: {reddit_file}")
print()

with open(reddit_file, 'r') as f:
    all_posts = json.load(f)

print(f"Total Reddit posts in file: {len(all_posts)}")
print()

# Filter for NVDA-related posts
nvda_posts = []
for post in all_posts:
    title = post.get('title', '').upper()
    text = post.get('text', '').upper()

    if 'NVDA' in title or 'NVDA' in text or 'NVIDIA' in title or 'NVIDIA' in text:
        nvda_posts.append(post)

print(f"NVDA-related posts found: {len(nvda_posts)}")
print()

if not nvda_posts:
    print("No NVDA-related posts found in this dataset.")
    exit(0)

# Analyze subreddit distribution
subreddits = [p['subreddit'] for p in nvda_posts]
subreddit_counts = Counter(subreddits)

print("=" * 80)
print("SUBREDDIT DISTRIBUTION")
print("=" * 80)
for subreddit, count in subreddit_counts.most_common():
    print(f"  r/{subreddit}: {count} posts")
print()

# Analyze sentiment
sentiment_counts = Counter([p['sentiment'] for p in nvda_posts])
total_posts = len(nvda_posts)

print("=" * 80)
print("SENTIMENT ANALYSIS")
print("=" * 80)
print(f"Bullish:  {sentiment_counts['bullish']:2d} ({sentiment_counts['bullish']/total_posts*100:.1f}%)")
print(f"Bearish:  {sentiment_counts['bearish']:2d} ({sentiment_counts['bearish']/total_posts*100:.1f}%)")
print(f"Neutral:  {sentiment_counts['neutral']:2d} ({sentiment_counts['neutral']/total_posts*100:.1f}%)")
print()

# Calculate average scores
avg_compound = sum(p['compound_score'] for p in nvda_posts) / len(nvda_posts)
avg_positive = sum(p['positive_score'] for p in nvda_posts) / len(nvda_posts)
avg_negative = sum(p['negative_score'] for p in nvda_posts) / len(nvda_posts)

print(f"Average Compound Score:  {avg_compound:.3f}")
print(f"Average Positive Score:  {avg_positive:.3f}")
print(f"Average Negative Score:  {avg_negative:.3f}")
print()

# Analyze topics
all_topics = []
for post in nvda_posts:
    all_topics.extend(post.get('topics', []))

topic_counts = Counter(all_topics)

print("=" * 80)
print("TOP TOPICS")
print("=" * 80)
for topic, count in topic_counts.most_common(10):
    print(f"  {topic}: {count}")
print()

# Display all NVDA posts
print("=" * 80)
print("ALL NVDA-RELATED POSTS")
print("=" * 80)
print()

# Sort by score (upvotes)
nvda_posts_sorted = sorted(nvda_posts, key=lambda x: x.get('score', 0), reverse=True)

for i, post in enumerate(nvda_posts_sorted, 1):
    print(f"{i}. r/{post['subreddit']} - {post['title']}")

    # Convert timestamp to readable date
    try:
        from datetime import datetime
        date_str = datetime.fromtimestamp(post['created_utc']).strftime('%Y-%m-%d %H:%M')
        print(f"   Posted: {date_str}")
    except:
        print(f"   Posted: {post['created_utc']}")

    if post.get('author'):
        print(f"   Author: u/{post['author']}")

    print(f"   Score: {post['score']} | Comments: {post['num_comments']}")
    print(f"   Sentiment: {post['sentiment'].upper()} (compound: {post['compound_score']:.2f})")

    if post.get('topics'):
        print(f"   Topics: {', '.join(post['topics'])}")

    # Show text preview (first 200 chars)
    if post.get('selftext'):
        text_preview = post['selftext'][:200].replace('\n', ' ')
        print(f"   Preview: {text_preview}...")

    print(f"   URL: {post['url']}")
    print()

# Summary statistics
print("=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)
print()

total_score = sum(p['score'] for p in nvda_posts)
total_comments = sum(p['num_comments'] for p in nvda_posts)
avg_score = total_score / len(nvda_posts)
avg_comments = total_comments / len(nvda_posts)

print(f"Total Posts:        {len(nvda_posts)}")
print(f"Total Upvotes:      {total_score:,}")
print(f"Total Comments:     {total_comments:,}")
print(f"Avg Upvotes/Post:   {avg_score:.1f}")
print(f"Avg Comments/Post:  {avg_comments:.1f}")
print()

# Most engaging post
most_engaging = max(nvda_posts, key=lambda x: x['score'] + x['num_comments'])
print(f"Most Engaging Post:")
print(f"  Title: {most_engaging['title']}")
print(f"  r/{most_engaging['subreddit']}")
print(f"  Score: {most_engaging['score']} | Comments: {most_engaging['num_comments']}")
print(f"  Sentiment: {most_engaging['sentiment']} ({most_engaging['compound_score']:.2f})")
print()

print("=" * 80)
