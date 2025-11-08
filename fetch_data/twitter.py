import os
import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any
from .utils import retry_on_failure, X_DATA_DIR

try:
    import tweepy
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    X_AVAILABLE = True
except ImportError:
    X_AVAILABLE = False

logger = logging.getLogger(__name__)

COMPANY_X_HANDLES = {
    'NVDA': 'nvidia',
    'AMD': 'AMD',
    'TSM': 'TSMC',
    'AVGO': 'Broadcom',
    'ORCL': 'Oracle',
}

CEO_X_HANDLES = {
    'NVDA': 'JenHsunHuang',
    'AMD': 'LisaSu',
    'TSM': None,
    'AVGO': None,
    'ORCL': None,
}

X_DAYS_BACK = 7

def initialize_x_client():
    if not X_AVAILABLE:
        logger.warning("X/Twitter API not available (tweepy not installed). Skipping...")
        return None

    try:
        bearer_token = os.getenv('X_BEARER_TOKEN')
        api_key = os.getenv('X_API_KEY')
        api_secret = os.getenv('X_API_SECRET')
        access_token = os.getenv('X_ACCESS_TOKEN')
        access_token_secret = os.getenv('X_ACCESS_TOKEN_SECRET')

        if not bearer_token and not (api_key and api_secret):
            logger.warning("X API credentials not found.")
            return None

        if bearer_token:
            client = tweepy.Client(bearer_token=bearer_token)
            logger.info("X API client initialized with bearer token")
        else:
            client = tweepy.Client(
                consumer_key=api_key,
                consumer_secret=api_secret,
                access_token=access_token,
                access_token_secret=access_token_secret
            )
            logger.info("X API client initialized with OAuth credentials")
        return client
    except Exception as e:
        logger.error(f"Failed to initialize X client: {e}")
        return None

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def search_x_posts(client, query: str, max_results: int = 100) -> List[Dict[str, Any]]:
    if not client:
        return []

    try:
        tweets = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
            expansions=['author_id'],
            user_fields=['username', 'name', 'verified']
        )

        if not tweets.data:
            return []

        users = {}
        if tweets.includes and 'users' in tweets.includes:
            for user in tweets.includes['users']:
                users[user.id] = {
                    'username': user.username,
                    'name': user.name,
                    'verified': getattr(user, 'verified', False)
                }

        posts = []
        for tweet in tweets.data:
            author_info = users.get(tweet.author_id, {'username': 'unknown', 'name': 'Unknown', 'verified': False})
            post = {
                'id': tweet.id,
                'text': tweet.text,
                'created_at': tweet.created_at.isoformat() if tweet.created_at else None,
                'author_id': tweet.author_id,
                'author_username': author_info['username'],
                'author_name': author_info['name'],
                'author_verified': author_info['verified'],
                'retweet_count': tweet.public_metrics.get('retweet_count', 0) if tweet.public_metrics else 0,
                'reply_count': tweet.public_metrics.get('reply_count', 0) if tweet.public_metrics else 0,
                'like_count': tweet.public_metrics.get('like_count', 0) if tweet.public_metrics else 0,
                'quote_count': tweet.public_metrics.get('quote_count', 0) if tweet.public_metrics else 0,
                'lang': tweet.lang if hasattr(tweet, 'lang') else 'unknown',
                'url': f"https://twitter.com/{author_info['username']}/status/{tweet.id}"
            }
            posts.append(post)
        return posts
    except tweepy.errors.TooManyRequests as e:
        logger.error(f"Rate limit exceeded for X API: {e}")
        time.sleep(900)
        raise
    except Exception as e:
        logger.error(f"Error searching X: {e}")
        return []

def fetch_x_data_for_company(client, ticker: str, company_name: str, ceo_name: str, analyzer) -> Dict[str, Any]:
    logger.info(f"Fetching X data for {ticker} ({company_name})...")
    company_posts = []
    ceo_posts = []
    now = datetime.now(tz=None)
    threshold_time = now - timedelta(days=X_DAYS_BACK)
    company_handle = COMPANY_X_HANDLES.get(ticker)
    ceo_handle = CEO_X_HANDLES.get(ticker)

    if company_handle:
        try:
            company_query = f'from:{company_handle} -is:retweet lang:en'
            logger.info(f"  Searching X for posts from @{company_handle}: {company_query}")
            company_results = search_x_posts(client, company_query, max_results=100)
            filtered_results = []
            for post in company_results:
                if post.get('created_at'):
                    post_time = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    if post_time.tzinfo is not None:
                        post_time = post_time.replace(tzinfo=None)
                    if post_time >= threshold_time:
                        filtered_results.append(post)
            company_results = filtered_results
            logger.info(f"  Found {len(company_results)} posts from @{company_handle} in last 24 hours")
            if company_results:
                for post in company_results:
                    sentiment_data = analyzer.polarity_scores(post['text'])
                    post['sentiment'] = 'bullish' if sentiment_data['compound'] >= 0.05 else 'bearish' if sentiment_data['compound'] <= -0.05 else 'neutral'
                    post['compound_score'] = sentiment_data['compound']
                company_posts = company_results
            time.sleep(3)
        except Exception as e:
            logger.error(f"Error fetching posts from @{company_handle}: {e}")

    if ceo_handle:
        try:
            ceo_query = f'from:{ceo_handle} -is:retweet lang:en'
            logger.info(f"  Searching X for posts from CEO @{ceo_handle}: {ceo_query}")
            ceo_results = search_x_posts(client, ceo_query, max_results=100)
            filtered_results = []
            for post in ceo_results:
                if post.get('created_at'):
                    post_time = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    if post_time.tzinfo is not None:
                        post_time = post_time.replace(tzinfo=None)
                    if post_time >= threshold_time:
                        filtered_results.append(post)
            ceo_results = filtered_results
            logger.info(f"  Found {len(ceo_results)} posts from CEO @{ceo_handle} in last 24 hours")
            if ceo_results:
                for post in ceo_results:
                    sentiment_data = analyzer.polarity_scores(post['text'])
                    post['sentiment'] = 'bullish' if sentiment_data['compound'] >= 0.05 else 'bearish' if sentiment_data['compound'] <= -0.05 else 'neutral'
                    post['compound_score'] = sentiment_data['compound']
                ceo_posts = ceo_results
            time.sleep(3)
        except Exception as e:
            logger.error(f"Error fetching posts from CEO @{ceo_handle}: {e}")

    all_scores = [post.get('compound_score', 0) for post in (company_posts + ceo_posts)]
    if all_scores:
        avg_compound = sum(all_scores) / len(all_scores)
        bullish_score = int(round(((avg_compound + 1) / 2) * 9 + 1))
    else:
        bullish_score = None

    return {
        'ticker': ticker,
        'company_name': company_name,
        'company_x_handle': f'@{company_handle}' if company_handle else None,
        'ceo_name': ceo_name,
        'ceo_x_handle': f'@{ceo_handle}' if ceo_handle else None,
        'company_posts': company_posts,
        'ceo_posts': ceo_posts,
        'total_posts': len(company_posts) + len(ceo_posts),
        'bullish_score': bullish_score,
        'fetch_timestamp': datetime.now().isoformat(),
    }

def fetch_x_data(companies_df):
    if not X_AVAILABLE:
        return

    logger.info("=" * 60)
    logger.info("FETCHING X/TWITTER DATA")
    logger.info("=" * 60)

    client = initialize_x_client()
    if not client:
        return

    now = datetime.now()
    date_str = now.strftime('%Y%m%d_%H%M%S')
    analyzer = SentimentIntensityAnalyzer()

    ceo_data_map = {}
    ceo_reports = sorted(os.listdir(os.path.join(X_DATA_DIR, '..', 'reports')))
    if ceo_reports:
        latest_ceo_report = os.path.join(X_DATA_DIR, '..', 'reports', ceo_reports[-1])
        ceo_df = pd.read_csv(latest_ceo_report)
        for _, row in ceo_df.iterrows():
            ceo_data_map[row['ticker']] = row['ceo_name']

    for index, row in companies_df.iterrows():
        ticker = row['ticker']
        company_name = row['company_name']
        ceo_name = ceo_data_map.get(ticker, "Not found")

        logger.info(f"Processing {index + 1}/{len(companies_df)}: {ticker}")

        try:
            result = fetch_x_data_for_company(client, ticker, company_name, ceo_name, analyzer)
            company_file = os.path.join(X_DATA_DIR, f"{ticker}_x_posts_{date_str}.json")
            with open(company_file, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"✅ Saved X data for {ticker} to {company_file}")
            time.sleep(10)
        except Exception as e:
            logger.error(f"Failed to fetch X data for {ticker}: {e}")
            continue
