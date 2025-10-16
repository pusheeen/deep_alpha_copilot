#!/usr/bin/env python3
"""
Fetch comprehensive data for a batch of companies.
Creates ONE complete file per company containing all relevant data.
"""

import json
import os
import yfinance as yf
from datetime import datetime
from pathlib import Path
from fetch_data import get_company_metrics, get_company_news
from collections import Counter
import time

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
    """Filter for quality posts"""
    if is_spam_post(post['text']):
        return False
    if len(post['text']) < 20:
        return False
    has_engagement = post.get('like_count', 0) >= 5 or post.get('retweet_count', 0) >= 1
    is_verified = post.get('author_verified', False)
    return has_engagement or is_verified


def fetch_company_complete_data(ticker, market_prices, company_info=None):
    """
    Fetch ALL data for a single company and return comprehensive structure.

    Args:
        ticker: Stock ticker symbol
        market_prices: SPY benchmark prices for beta calculation
        company_info: Optional dict with company_name, ceo_name (if available)

    Returns:
        dict: Comprehensive company data structure
    """
    print(f"\n{'=' * 80}")
    print(f"FETCHING COMPLETE DATA FOR {ticker}")
    print(f"{'=' * 80}\n")

    # 1. Fetch company metrics
    print(f"1. Fetching {ticker} company metrics...")
    try:
        metrics = get_company_metrics(ticker, market_prices)
        print(f"   ✅ Company metrics loaded\n")
    except Exception as e:
        print(f"   ❌ Error fetching metrics: {e}\n")
        return None

    # 2. Fetch news
    print(f"2. Fetching {ticker} news from past 7 days...")
    try:
        news = get_company_news(ticker, days=7)
        print(f"   ✅ Found {len(news)} news articles\n")
    except Exception as e:
        print(f"   ❌ Error fetching news: {e}\n")
        news = []

    # 3. Load X/Twitter data if available
    print(f"3. Loading X/Twitter data for {ticker}...")
    x_data = None
    x_files = list(Path("data/unstructured/x").glob(f"{ticker}_x_posts_live_*.json"))
    if x_files:
        latest_x_file = sorted(x_files)[-1]
        print(f"   Loading: {latest_x_file}")
        try:
            with open(latest_x_file, 'r') as f:
                x_data = json.load(f)

            # Apply spam filtering
            initial_company = len(x_data.get('company_posts', []))
            initial_ceo = len(x_data.get('ceo_posts', []))

            x_data['company_posts'] = [p for p in x_data.get('company_posts', []) if is_quality_post(p)]
            x_data['ceo_posts'] = [p for p in x_data.get('ceo_posts', []) if is_quality_post(p)]
            x_data['total_company_posts'] = len(x_data['company_posts'])
            x_data['total_ceo_posts'] = len(x_data['ceo_posts'])

            filtered = (initial_company - len(x_data['company_posts'])) + (initial_ceo - len(x_data['ceo_posts']))
            print(f"   ✅ Loaded {x_data['total_company_posts']} company + {x_data['total_ceo_posts']} CEO posts (filtered {filtered} spam)\n")
        except Exception as e:
            print(f"   ❌ Error loading X data: {e}\n")
            x_data = None
    else:
        print(f"   ⚠️  No X/Twitter data found for {ticker}\n")

    # 4. Load Reddit data if available
    print(f"4. Loading Reddit data for {ticker}...")
    reddit_data = []
    reddit_files = list(Path("data/unstructured/reddit").glob("reddit_posts_*.json"))
    if reddit_files:
        latest_reddit_file = sorted(reddit_files)[-1]
        print(f"   Loading: {latest_reddit_file}")
        try:
            with open(latest_reddit_file, 'r') as f:
                all_reddit_posts = json.load(f)

            # Filter for ticker-related posts
            company_name = company_info.get('company_name', '') if company_info else ''
            for post in all_reddit_posts:
                title = post.get('title', '').upper()
                text = post.get('selftext', '').upper()

                # Check for ticker or company name
                if ticker in title or ticker in text:
                    reddit_data.append(post)
                elif company_name and company_name.upper() in title:
                    reddit_data.append(post)

            print(f"   ✅ Found {len(reddit_data)} {ticker}-related Reddit posts\n")
        except Exception as e:
            print(f"   ❌ Error loading Reddit data: {e}\n")
    else:
        print(f"   ⚠️  No Reddit data files found\n")

    # 5. Load sector comparison if available
    print(f"5. Loading sector comparison data for {ticker}...")
    sector_data = None
    sector_files = list(Path("data/structured/sector_metrics").glob(f"{ticker}_vs_sector_*.json"))
    if sector_files:
        latest_sector_file = sorted(sector_files)[-1]
        print(f"   Loading: {latest_sector_file}")
        try:
            with open(latest_sector_file, 'r') as f:
                sector_data = json.load(f)
            print(f"   ✅ Loaded sector comparison data\n")
        except Exception as e:
            print(f"   ❌ Error loading sector data: {e}\n")
    else:
        print(f"   ⚠️  No sector comparison data found for {ticker}\n")

    # 6. Calculate statistics
    print(f"6. Calculating summary statistics...")

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

    print(f"   ✅ Statistics calculated\n")

    # 7. Compile comprehensive data structure
    print(f"7. Compiling comprehensive data structure...")

    # Get company name and CEO from company_info or metrics
    if company_info:
        company_name = company_info.get('company_name', ticker)
        ceo_name = company_info.get('ceo_name', 'Unknown')
    else:
        company_name = ticker
        ceo_name = 'Unknown'

    comprehensive_data = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'ticker': ticker,
            'data_sources': {
                'financial_metrics': 'yfinance',
                'news': 'Yahoo Finance API',
                'x_twitter': 'Available (spam filtered)' if x_data else 'Not available',
                'reddit': f'{len(reddit_data)} posts' if reddit_data else 'Not available',
                'sector_comparison': 'Available' if sector_data else 'Not available'
            }
        },

        'company_info': {
            'ticker': ticker,
            'company_name': company_name,
            'ceo': ceo_name,
            'sector': metrics.get('sector'),
            'industry': metrics.get('industry'),
            'market_cap': metrics.get('market_cap')
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
                'overall_sentiment_score': (x_stats.get('avg_sentiment', 0) + reddit_stats.get('avg_sentiment', 0)) / 2 if x_stats and reddit_stats else x_stats.get('avg_sentiment', 0) if x_stats else reddit_stats.get('avg_sentiment', 0) if reddit_stats else 0
            }
        }
    }

    print(f"   ✅ Data structure compiled\n")

    return comprehensive_data


def main():
    """Main batch processing function"""
    print("=" * 80)
    print("BATCH COMPANY DATA FETCHER")
    print("=" * 80)
    print()

    # Load target tickers from target_tickers.py
    try:
        from target_tickers import get_target_tickers
        target_companies = get_target_tickers()
        print(f"Loaded {len(target_companies)} companies from target_tickers.py")
    except Exception as e:
        print(f"Error loading target_tickers.py: {e}")
        print("Using default ticker list...")
        target_companies = [
            {'ticker': 'NVDA', 'company_name': 'NVIDIA CORP', 'ceo_name': 'Jensen Huang'},
            {'ticker': 'AAPL', 'company_name': 'Apple Inc.', 'ceo_name': 'Tim Cook'},
            {'ticker': 'MSFT', 'company_name': 'Microsoft Corporation', 'ceo_name': 'Satya Nadella'},
        ]

    print()

    # Fetch market benchmark (SPY) once for all companies
    print("Fetching market benchmark (SPY)...")
    spy = yf.Ticker("SPY")
    spy_hist = spy.history(period="1y")
    market_prices = spy_hist['Close']
    print("✅ Market data loaded\n")

    # Create output directory
    output_dir = Path("data/structured/companies")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Track results
    results = {
        'timestamp': datetime.now().isoformat(),
        'total_companies': len(target_companies),
        'successful': [],
        'failed': []
    }

    # Process each company
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    for idx, company in enumerate(target_companies, 1):
        ticker = company['ticker']
        print(f"\n[{idx}/{len(target_companies)}] Processing {ticker}...")

        try:
            # Fetch comprehensive data
            company_data = fetch_company_complete_data(
                ticker=ticker,
                market_prices=market_prices,
                company_info=company
            )

            if company_data:
                # Save to individual file
                output_file = output_dir / f"{ticker}_complete_{timestamp}.json"
                with open(output_file, 'w') as f:
                    json.dump(company_data, f, indent=2)

                file_size = os.path.getsize(output_file) / 1024
                print(f"✅ Saved: {output_file} ({file_size:.1f} KB)")

                results['successful'].append({
                    'ticker': ticker,
                    'file': str(output_file),
                    'size_kb': file_size,
                    'market_cap': company_data['company_info']['market_cap'],
                    'sentiment': company_data['overall_sentiment_summary']['combined']
                })
            else:
                print(f"❌ Failed to fetch data for {ticker}")
                results['failed'].append({'ticker': ticker, 'reason': 'Failed to fetch metrics'})

        except Exception as e:
            print(f"❌ Error processing {ticker}: {e}")
            results['failed'].append({'ticker': ticker, 'reason': str(e)})

        # Rate limiting - wait between requests
        if idx < len(target_companies):
            time.sleep(2)  # Wait 2 seconds between companies

    # Save batch summary
    summary_file = Path("data/structured") / f"batch_summary_{timestamp}.json"
    with open(summary_file, 'w') as f:
        json.dump(results, f, indent=2)

    # Print final summary
    print("\n" + "=" * 80)
    print("BATCH PROCESSING COMPLETE")
    print("=" * 80)
    print(f"Total companies: {results['total_companies']}")
    print(f"Successful: {len(results['successful'])}")
    print(f"Failed: {len(results['failed'])}")
    print()
    print(f"Batch summary saved to: {summary_file}")
    print()
    print("Individual company files saved to: data/structured/companies/")
    for result in results['successful']:
        print(f"  ✓ {result['ticker']}: {result['file']}")

    if results['failed']:
        print("\nFailed companies:")
        for failed in results['failed']:
            print(f"  ✗ {failed['ticker']}: {failed['reason']}")

    print("\n" + "=" * 80)


if __name__ == "__main__":
    main()
