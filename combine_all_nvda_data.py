#!/usr/bin/env python3
"""
Combine ALL NVDA-related data into one comprehensive JSON file:
- Financial metrics
- News (past 7 days)
- X/Twitter data (REAL live data, spam filtered)
- Reddit data (all NVDA posts)
- Sector comparison data
"""

import json
import os
import yfinance as yf
from datetime import datetime
from pathlib import Path
from fetch_data import get_company_metrics, get_company_news

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
print("COMBINING ALL NVDA DATA INTO ONE COMPREHENSIVE FILE")
print("=" * 80)
print()

ticker = "NVDA"

# 1. Fetch market benchmark
print("1. Fetching market data (SPY)...")
spy = yf.Ticker("SPY")
spy_hist = spy.history(period="1y")
market_prices = spy_hist['Close']
print("   ✅ Market data loaded\n")

# 2. Fetch company metrics
print("2. Fetching NVDA company metrics...")
metrics = get_company_metrics(ticker, market_prices)
print("   ✅ Company metrics loaded\n")

# 3. Fetch news from past 7 days
print("3. Fetching NVDA news from past 7 days...")
news = get_company_news(ticker, days=7)
print(f"   ✅ Found {len(news)} news articles\n")

# 4. Load REAL X/Twitter data (live data, not example)
print("4. Loading REAL X/Twitter data...")
x_data = None
x_files = list(Path("data/unstructured/x").glob("NVDA_x_posts_live_*.json"))
if x_files:
    # Get most recent live file
    latest_x_file = sorted(x_files)[-1]
    print(f"   Loading: {latest_x_file}")
    with open(latest_x_file, 'r') as f:
        x_data = json.load(f)

    # Apply spam filtering to loaded data
    initial_company = len(x_data.get('company_posts', []))
    initial_ceo = len(x_data.get('ceo_posts', []))

    x_data['company_posts'] = [p for p in x_data.get('company_posts', []) if is_quality_post(p)]
    x_data['ceo_posts'] = [p for p in x_data.get('ceo_posts', []) if is_quality_post(p)]
    x_data['total_company_posts'] = len(x_data['company_posts'])
    x_data['total_ceo_posts'] = len(x_data['ceo_posts'])

    filtered_company = initial_company - len(x_data['company_posts'])
    filtered_ceo = initial_ceo - len(x_data['ceo_posts'])
    total_filtered = filtered_company + filtered_ceo

    print(f"   ✅ Loaded {x_data['total_company_posts']} quality company posts and {x_data['total_ceo_posts']} quality CEO posts")
    print(f"      (filtered {total_filtered} spam: {filtered_company} company, {filtered_ceo} CEO)\n")
else:
    # Fallback to example if no live data
    x_file = "data/unstructured/x/NVDA_x_posts_EXAMPLE.json"
    if os.path.exists(x_file):
        print(f"   ⚠️  No live data found, loading example data")
        with open(x_file, 'r') as f:
            x_data = json.load(f)
        print(f"   Loaded {x_data['total_company_posts']} company posts and {x_data['total_ceo_posts']} CEO posts (example)\n")

# 5. Load and filter Reddit data
print("5. Loading Reddit data and filtering for NVDA...")
reddit_data = []
reddit_files = list(Path("data/unstructured/reddit").glob("reddit_posts_*.json"))
if reddit_files:
    # Get most recent reddit file
    latest_reddit_file = sorted(reddit_files)[-1]
    print(f"   Loading: {latest_reddit_file}")

    with open(latest_reddit_file, 'r') as f:
        all_reddit_posts = json.load(f)

    # Filter for NVDA-related posts
    for post in all_reddit_posts:
        title = post.get('title', '').upper()
        text = post.get('selftext', '').upper()

        if 'NVDA' in title or 'NVDA' in text or 'NVIDIA' in title or 'NVIDIA' in text:
            reddit_data.append(post)

    print(f"   ✅ Found {len(reddit_data)} NVDA-related Reddit posts (from {len(all_reddit_posts)} total)\n")

# 6. Load sector comparison data if available
print("6. Loading sector comparison data...")
sector_data = None
sector_files = list(Path("data/structured/sector_metrics").glob("NVDA_vs_sector_*.json"))
if sector_files:
    # Get most recent sector file
    latest_sector_file = sorted(sector_files)[-1]
    print(f"   Loading: {latest_sector_file}")
    with open(latest_sector_file, 'r') as f:
        sector_data = json.load(f)
    print(f"   ✅ Loaded sector comparison data\n")
else:
    print("   ⚠️  No sector comparison data found\n")

# 7. Calculate summary statistics
print("7. Calculating summary statistics...")

# News stats
news_publishers = {}
for article in news:
    pub = article.get('publisher', 'Unknown')
    news_publishers[pub] = news_publishers.get(pub, 0) + 1

# X/Twitter stats
x_stats = {}
if x_data:
    all_x_posts = x_data.get('company_posts', []) + x_data.get('ceo_posts', [])
    x_stats = {
        'total_posts': len(all_x_posts),
        'total_likes': sum(p.get('like_count', 0) for p in all_x_posts),
        'total_retweets': sum(p.get('retweet_count', 0) for p in all_x_posts),
        'bullish': sum(1 for p in all_x_posts if p.get('sentiment') == 'bullish'),
        'bearish': sum(1 for p in all_x_posts if p.get('sentiment') == 'bearish'),
        'neutral': sum(1 for p in all_x_posts if p.get('sentiment') == 'neutral'),
        'avg_sentiment': sum(p.get('compound_score', 0) for p in all_x_posts) / len(all_x_posts) if all_x_posts else 0
    }

# Reddit stats
reddit_stats = {}
if reddit_data:
    from collections import Counter
    reddit_stats = {
        'total_posts': len(reddit_data),
        'total_upvotes': sum(p.get('score', 0) for p in reddit_data),
        'total_comments': sum(p.get('num_comments', 0) for p in reddit_data),
        'bullish': sum(1 for p in reddit_data if p.get('sentiment') == 'bullish'),
        'bearish': sum(1 for p in reddit_data if p.get('sentiment') == 'bearish'),
        'neutral': sum(1 for p in reddit_data if p.get('sentiment') == 'neutral'),
        'avg_sentiment': sum(p.get('compound_score', 0) for p in reddit_data) / len(reddit_data) if reddit_data else 0,
        'top_subreddits': dict(Counter([p['subreddit'] for p in reddit_data]).most_common(5))
    }

print("   ✅ Statistics calculated\n")

# 8. Compile comprehensive data structure
print("8. Compiling comprehensive data structure...")

comprehensive_data = {
    'metadata': {
        'timestamp': datetime.now().isoformat(),
        'ticker': ticker,
        'data_sources': {
            'financial_metrics': 'yfinance',
            'news': 'Yahoo Finance API',
            'x_twitter': 'X API v2 (live, spam filtered)' if x_files else 'Example data',
            'reddit': f'{len(reddit_data)} posts' if reddit_data else 'None',
            'sector_comparison': 'Available' if sector_data else 'Not available'
        }
    },

    'company_info': {
        'ticker': ticker,
        'company_name': 'NVIDIA CORP',
        'ceo': 'Jensen Huang',
        'sector': metrics.get('sector'),
        'industry': metrics.get('industry'),
        'market_cap': metrics.get('market_cap'),
        'description': 'Leading AI chip and GPU manufacturer'
    },

    'financial_metrics': {
        'profitability': {
            'roe': metrics.get('roe'),
            'roa': metrics.get('roa'),
            'roic': metrics.get('roic'),
            'net_margin': metrics.get('net_margin'),
            'gross_margin': metrics.get('gross_margin')
        },
        'growth': {
            'cagr': metrics.get('cagr'),
            'momentum_1m': metrics.get('momentum_1m'),
            'momentum_3m': metrics.get('momentum_3m'),
            'momentum_6m': metrics.get('momentum_6m'),
            'momentum_1y': metrics.get('momentum_1y')
        },
        'valuation': {
            'pe_ratio': metrics.get('pe_ratio'),
            'ps_ratio': metrics.get('ps_ratio'),
            'pb_ratio': metrics.get('pb_ratio')
        },
        'risk': {
            'beta': metrics.get('beta'),
            'volatility': metrics.get('volatility'),
            'sharpe_ratio': metrics.get('sharpe_ratio')
        },
        'financial_health': {
            'debt_to_equity': metrics.get('debt_to_equity'),
            'current_ratio': metrics.get('current_ratio'),
            'quick_ratio': metrics.get('quick_ratio'),
            'interest_coverage': metrics.get('interest_coverage')
        }
    },

    'news_data': {
        'summary': {
            'total_articles': len(news),
            'date_range': '7 days',
            'publishers': news_publishers
        },
        'articles': news
    },

    'x_twitter_data': {
        'summary': x_stats,
        'raw_data': x_data
    },

    'reddit_data': {
        'summary': reddit_stats,
        'posts': reddit_data
    },

    'sector_comparison': sector_data,

    'overall_sentiment_summary': {
        'x_twitter': {
            'sentiment': 'bullish' if x_stats.get('bullish', 0) > x_stats.get('bearish', 0) else 'bearish' if x_stats.get('bearish', 0) > x_stats.get('bullish', 0) else 'neutral',
            'score': x_stats.get('avg_sentiment', 0),
            'confidence': f"{x_stats.get('bullish', 0)}/{x_stats.get('total_posts', 1)} bullish" if x_stats else 'N/A'
        },
        'reddit': {
            'sentiment': 'bullish' if reddit_stats.get('bullish', 0) > reddit_stats.get('bearish', 0) else 'bearish' if reddit_stats.get('bearish', 0) > reddit_stats.get('bullish', 0) else 'neutral',
            'score': reddit_stats.get('avg_sentiment', 0),
            'confidence': f"{reddit_stats.get('bullish', 0)}/{reddit_stats.get('total_posts', 1)} bullish" if reddit_stats else 'N/A'
        },
        'combined': {
            'total_social_posts': x_stats.get('total_posts', 0) + reddit_stats.get('total_posts', 0),
            'total_bullish': x_stats.get('bullish', 0) + reddit_stats.get('bullish', 0),
            'total_bearish': x_stats.get('bearish', 0) + reddit_stats.get('bearish', 0),
            'overall_sentiment_score': (x_stats.get('avg_sentiment', 0) + reddit_stats.get('avg_sentiment', 0)) / 2 if x_stats and reddit_stats else 0
        }
    }
}

print("   ✅ Data structure compiled\n")

# 9. Save to file
output_file = f"data/structured/nvda_complete_combined_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
print(f"9. Saving to file: {output_file}")

with open(output_file, 'w') as f:
    json.dump(comprehensive_data, f, indent=2)

print("   ✅ File saved\n")

# 10. Display summary
print("=" * 80)
print("COMPREHENSIVE NVDA DATA - SUMMARY")
print("=" * 80)
print()

print(f"📊 COMPANY: {comprehensive_data['company_info']['company_name']}")
print(f"Ticker: {ticker}")
print(f"CEO: {comprehensive_data['company_info']['ceo']}")
print(f"Sector: {comprehensive_data['company_info']['sector']}")
print(f"Industry: {comprehensive_data['company_info']['industry']}")
print(f"Market Cap: ${comprehensive_data['company_info']['market_cap']:,.0f}")
print()

print("💰 FINANCIAL METRICS")
print("-" * 80)
prof = comprehensive_data['financial_metrics']['profitability']
growth = comprehensive_data['financial_metrics']['growth']
val = comprehensive_data['financial_metrics']['valuation']
risk = comprehensive_data['financial_metrics']['risk']

print(f"ROE: {prof['roe']:.2f}% | ROA: {prof['roa']:.2f}% | Net Margin: {prof['net_margin']:.2f}%")
print(f"CAGR: {growth['cagr']:.2f}% | 6M Momentum: {growth['momentum_6m']:.2f}%")
print(f"P/E: {val['pe_ratio']:.2f} | P/S: {val['ps_ratio']:.2f} | Beta: {risk['beta']:.2f}")
print()

print(f"📰 NEWS: {comprehensive_data['news_data']['summary']['total_articles']} articles (past 7 days)")
print("-" * 80)
top_publishers = sorted(news_publishers.items(), key=lambda x: x[1], reverse=True)[:3]
for pub, count in top_publishers:
    print(f"  {pub}: {count} articles")
print()

print(f"🐦 X/TWITTER: {x_stats.get('total_posts', 0)} posts")
print("-" * 80)
if x_stats:
    print(f"  Bullish: {x_stats['bullish']} | Bearish: {x_stats['bearish']} | Neutral: {x_stats['neutral']}")
    print(f"  Avg Sentiment: {x_stats['avg_sentiment']:.3f}")
    print(f"  Total Engagement: {x_stats['total_likes']:,} likes, {x_stats['total_retweets']:,} retweets")

    # Show sample X post texts
    if x_data:
        all_x_posts = x_data.get('company_posts', []) + x_data.get('ceo_posts', [])
        if all_x_posts:
            print(f"\n  Sample Posts (showing top 3):")
            # Sort by engagement (likes + retweets)
            sorted_posts = sorted(all_x_posts, key=lambda p: p.get('like_count', 0) + p.get('retweet_count', 0), reverse=True)
            for i, post in enumerate(sorted_posts[:3], 1):
                text_preview = post.get('text', '')[:100].replace('\n', ' ')
                print(f"    {i}. \"{text_preview}...\"")
                print(f"       @{post.get('author_username', 'unknown')} | {post.get('sentiment', 'N/A')} ({post.get('compound_score', 0):.2f})")
                print(f"       {post.get('like_count', 0)} likes, {post.get('retweet_count', 0)} retweets")
print()

print(f"🔴 REDDIT: {reddit_stats.get('total_posts', 0)} posts")
print("-" * 80)
if reddit_stats:
    print(f"  Bullish: {reddit_stats['bullish']} | Bearish: {reddit_stats['bearish']} | Neutral: {reddit_stats['neutral']}")
    print(f"  Avg Sentiment: {reddit_stats['avg_sentiment']:.3f}")
    print(f"  Total Engagement: {reddit_stats['total_upvotes']:,} upvotes, {reddit_stats['total_comments']:,} comments")
    print(f"  Top Subreddits: {', '.join([f'r/{s}' for s in list(reddit_stats['top_subreddits'].keys())[:3]])}")

    # Show sample Reddit post titles
    if reddit_data:
        print(f"\n  Sample Posts (showing top 3 by upvotes):")
        sorted_reddit = sorted(reddit_data, key=lambda p: p.get('score', 0), reverse=True)
        for i, post in enumerate(sorted_reddit[:3], 1):
            title = post.get('title', 'No title')[:80]
            print(f"    {i}. \"{title}\"")
            print(f"       r/{post.get('subreddit', 'unknown')} | {post.get('sentiment', 'N/A')} ({post.get('compound_score', 0):.2f})")
            print(f"       {post.get('score', 0)} upvotes, {post.get('num_comments', 0)} comments")
print()

print("📈 SECTOR COMPARISON")
print("-" * 80)
if sector_data:
    print(f"  Classification: {sector_data.get('company_vs_sector', {}).get('classification', 'N/A')}")
    print(f"  Performance Score: {sector_data.get('company_vs_sector', {}).get('relative_performance_score', 0):.1f}/100")
    strengths = sector_data.get('company_vs_sector', {}).get('strengths', [])
    print(f"  Key Strengths: {', '.join(strengths[:5])}")
else:
    print("  Not available")
print()

print("🎯 OVERALL SENTIMENT")
print("-" * 80)
combined = comprehensive_data['overall_sentiment_summary']['combined']
print(f"Total Social Posts: {combined['total_social_posts']}")
print(f"Bullish: {combined['total_bullish']} | Bearish: {combined['total_bearish']}")
print(f"Overall Sentiment Score: {combined['overall_sentiment_score']:.3f}")

if combined['total_bullish'] > combined['total_bearish'] * 2:
    print("📊 Assessment: STRONGLY BULLISH")
elif combined['total_bullish'] > combined['total_bearish']:
    print("📊 Assessment: BULLISH")
elif combined['total_bearish'] > combined['total_bullish']:
    print("📊 Assessment: BEARISH")
else:
    print("📊 Assessment: NEUTRAL")
print()

print("=" * 80)
print("✅ COMPLETE - ALL NVDA DATA COMBINED")
print("=" * 80)
print()
print(f"Output file: {output_file}")
print()
print("File contains:")
print("  ✓ Company information and CEO details")
print("  ✓ Complete financial metrics (profitability, growth, valuation, risk, health)")
print(f"  ✓ {len(news)} news articles from past 7 days")
print(f"  ✓ {x_stats.get('total_posts', 0)} X/Twitter posts with sentiment analysis")
print(f"  ✓ {reddit_stats.get('total_posts', 0)} Reddit posts with sentiment analysis")
if sector_data:
    print("  ✓ Sector comparison analysis (vs Technology sector peers)")
print("  ✓ Overall sentiment summary combining all sources")
print()
print(f"File size: {os.path.getsize(output_file) / 1024:.1f} KB")
print()
print("=" * 80)
