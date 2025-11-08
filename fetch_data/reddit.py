import os
import re
import json
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from .utils import retry_on_failure, REDDIT_DATA_DIR, TARGET_TICKERS

try:
    import praw
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False

logger = logging.getLogger(__name__)

SUBREDDITS = [
    'stocks', 'investing', 'wallstreetbets', 'SecurityAnalysis', 'ValueInvesting',
    'UraniumSqueeze', 'uraniumstocks', 'renewableenergy', 'cryptomining',
    'BitcoinMining', 'NVDA', 'CryptoCurrency', 'gpumining', 'NiceHash',
    'EtherMining', 'CryptoMiningTalk', 'BitcoinMiningStock', 'CryptoMarkets'
]

DAYS_BACK = 1
TICKER_ALIASES: Dict[str, List[str]] = {ticker: [ticker, f'${ticker}'] for ticker in TARGET_TICKERS}

def contains_ticker(text: str) -> List[str]:
    text_upper = text.upper()
    found_tickers = []
    for ticker, aliases in TICKER_ALIASES.items():
        for alias in aliases:
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_upper):
                if ticker not in found_tickers:
                    found_tickers.append(ticker)
                break
    return found_tickers

def analyze_sentiment(text: str, analyzer) -> Dict[str, Any]:
    scores = analyzer.polarity_scores(text)
    if scores['compound'] >= 0.05:
        sentiment = 'bullish'
    elif scores['compound'] <= -0.05:
        sentiment = 'bearish'
    else:
        sentiment = 'neutral'
    return {
        'sentiment': sentiment,
        'compound_score': scores['compound'],
        'positive_score': scores['pos'],
        'negative_score': scores['neg'],
        'neutral_score': scores['neu']
    }

def extract_topics(text: str) -> List[str]:
    text_lower = text.lower()
    topics = []
    topic_keywords = {
        'earnings': ['earnings', 'quarterly', 'q1', 'q2', 'q3', 'q4', 'revenue', 'profit'],
        'technical_analysis': ['chart', 'ta', 'technical', 'support', 'resistance', 'breakout'],
        'fundamentals': ['pe ratio', 'p/e', 'valuation', 'book value', 'debt', 'cash flow'],
        'news': ['news', 'announcement', 'press release', 'ceo', 'management'],
        'partnerships': ['partnership', 'deal', 'acquisition', 'merger', 'collaboration'],
        'regulatory': ['sec', 'fda', 'approval', 'regulation', 'compliance'],
        'market_sentiment': ['bullish', 'bearish', 'optimistic', 'pessimistic', 'hype'],
        'AI': ['ai', 'artificial intelligence', 'machine learning', 'gpu', 'data center'],
        'crypto': ['crypto', 'bitcoin', 'ethereum', 'mining', 'blockchain'],
        'uranium': ['uranium', 'nuclear', 'reactor', 'fuel'],
        'renewable': ['renewable', 'solar', 'wind', 'clean energy', 'green']
    }
    for topic, keywords in topic_keywords.items():
        if any(keyword in text_lower for keyword in keywords):
            topics.append(topic)
    return topics

def scrape_subreddit_with_praw(reddit_client, subreddit_name: str, analyzer, since_date, limit: int = 100) -> List[Dict[str, Any]]:
    logger.info(f"Scraping r/{subreddit_name}...")
    subreddit = reddit_client.subreddit(subreddit_name)
    posts_data = []
    seen_post_ids = set()
    try:
        for post_type, post_generator in [('hot', subreddit.hot(limit=limit)), ('new', subreddit.new(limit=limit))]:
            for post in post_generator:
                if post.id in seen_post_ids:
                    continue
                seen_post_ids.add(post.id)
                post_date = datetime.fromtimestamp(post.created_utc)
                if post_date < since_date:
                    continue
                full_text = f"{post.title}\n{post.selftext or ''}"
                mentioned_tickers = contains_ticker(full_text)
                if not mentioned_tickers:
                    continue
                sentiment_data = analyze_sentiment(full_text, analyzer)
                topics = extract_topics(full_text)
                comments_data = []
                post.comments.replace_more(limit=0)
                for comment in post.comments[:5]:
                    if hasattr(comment, 'body') and comment.body != '[deleted]':
                        comment_tickers = contains_ticker(comment.body)
                        if comment_tickers:
                            comment_sentiment = analyze_sentiment(comment.body, analyzer)
                            comments_data.append({
                                'id': comment.id,
                                'body': comment.body[:500],
                                'score': comment.score,
                                'created_utc': comment.created_utc,
                                'mentioned_tickers': comment_tickers,
                                'sentiment': comment_sentiment['sentiment'],
                                'compound_score': comment_sentiment['compound_score']
                            })
                post_data = {
                    'id': post.id,
                    'title': post.title,
                    'selftext': post.selftext or '',
                    'score': post.score,
                    'upvote_ratio': post.upvote_ratio,
                    'num_comments': post.num_comments,
                    'created_utc': post.created_utc,
                    'subreddit': subreddit_name,
                    'url': f"https://reddit.com{post.permalink}",
                    'mentioned_tickers': mentioned_tickers,
                    'sentiment': sentiment_data['sentiment'],
                    'compound_score': sentiment_data['compound_score'],
                    'positive_score': sentiment_data['positive_score'],
                    'negative_score': sentiment_data['negative_score'],
                    'topics': topics,
                    'comments': comments_data
                }
                posts_data.append(post_data)
                logger.info(f"  Found post about {mentioned_tickers}: {post.title[:50]}...")
                time.sleep(1)
    except Exception as e:
        logger.error(f"Error scraping r/{subreddit_name}: {e}")
    return posts_data

def scrape_reddit_with_praw() -> List[Dict[str, Any]]:
    if not REDDIT_AVAILABLE:
        logger.warning("Reddit scraping not available (praw not installed). Skipping...")
        return []

    logger.info("=" * 60)
    logger.info("SCRAPING REDDIT WITH PRAW API")
    logger.info("=" * 60)
    logger.info(f"Target tickers: {', '.join(sorted(TARGET_TICKERS))}")
    logger.info(f"Subreddits: {', '.join(SUBREDDITS)}")
    logger.info(f"Time range: Past {DAYS_BACK} days")

    try:
        reddit_client = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID', "9RrzkLg9kN06g-kpti2ncw"),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET', "OH0pyFbl8T2ykN0IeAC1m5uNUu287A"),
            user_agent=os.getenv('REDDIT_USER_AGENT', "FinancialAgent/1.0 by u/Feeling-Berry5335")
        )
        logger.info(f"Authenticated as: {reddit_client.user.me() if reddit_client.user.me() else 'Anonymous (Read-only)'}")
    except Exception as e:
        logger.error(f"Failed to initialize Reddit client: {e}")
        return []

    analyzer = SentimentIntensityAnalyzer()
    since_date = datetime.now() - timedelta(days=DAYS_BACK)
    all_posts = []

    for subreddit_name in SUBREDDITS:
        try:
            posts = scrape_subreddit_with_praw(reddit_client, subreddit_name, analyzer, since_date)
            all_posts.extend(posts)
            logger.info(f"  Scraped {len(posts)} posts from r/{subreddit_name}")
        except Exception as e:
            logger.error(f"Failed to scrape r/{subreddit_name}: {e}")
            continue

    return all_posts

def fetch_reddit_data():
    posts_data = scrape_reddit_with_praw()

    if not posts_data:
        logger.warning("No Reddit posts found via live scrape. Skipping save.")
        return

    now = datetime.now()
    fetch_timestamp = now.isoformat()
    date_str = now.strftime('%Y%m%d_%H%M%S')

    for ticker in TARGET_TICKERS:
        posts_for_ticker = [post for post in posts_data if ticker in post['mentioned_tickers']]
        total_posts = len(posts_for_ticker)
        bullish_posts = sum(1 for p in posts_for_ticker if p['sentiment'] == 'bullish')
        bearish_posts = sum(1 for p in posts_for_ticker if p['sentiment'] == 'bearish')
        neutral_posts = sum(1 for p in posts_for_ticker if p['sentiment'] == 'neutral')
        subreddits = list({p['subreddit'] for p in posts_for_ticker})
        if posts_for_ticker:
            avg_compound = sum(p.get('compound_score', 0) for p in posts_for_ticker) / total_posts
            bullish_score = int(round(((avg_compound + 1) / 2) * 9 + 1))
        else:
            avg_compound = None
            bullish_score = None
        result = {
            'ticker': ticker,
            'posts': posts_for_ticker,
            'total_posts': total_posts,
            'bullish_posts': bullish_posts,
            'bearish_posts': bearish_posts,
            'neutral_posts': neutral_posts,
            'subreddits': subreddits,
            'avg_sentiment': avg_compound,
            'bullish_score': bullish_score,
            'fetch_timestamp': fetch_timestamp
        }
        ticker_file = os.path.join(REDDIT_DATA_DIR, f"{ticker}_reddit_posts_{date_str}.json")
        with open(ticker_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"✅ Saved Reddit data and summary for {ticker} to {ticker_file}")
