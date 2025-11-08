import os
import re
import json
import logging
import requests
from datetime import datetime
from typing import Dict, List, Any
from .utils import retry_on_failure, NEWS_DATA_DIR

logger = logging.getLogger(__name__)

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_sector_news(sector: str, max_articles: int = 20) -> List[Dict[str, Any]]:
    """
    Fetches news for a given sector.
    """
    logger.info(f"Fetching news for sector: {sector}...")
    all_articles = []
    seen_urls = set()

    news_api_key = os.getenv("NEWS_API_KEY")
    if not news_api_key:
        logger.warning("News API key not found. Cannot fetch sector news.")
        return []

    try:
        # More generic query for a sector
        query = f'"{sector} sector" OR "{sector} industry"'
        url = f"https://newsapi.org/v2/everything?q={query}&apiKey={news_api_key}&language=en&sortBy=publishedAt&pageSize={max_articles}"
        response = requests.get(url)
        response.raise_for_status()
        news_data = response.json()

        if news_data.get('articles'):
            for article in news_data['articles']:
                if article['url'] not in seen_urls:
                    all_articles.append({
                        'source': 'News API',
                        'title': article.get('title'),
                        'link': article.get('url'),
                        'publisher': article['source'].get('name'),
                        'publish_time': article.get('publishedAt'),
                        'summary': article.get('description'),
                        'type': 'Article'
                    })
                    seen_urls.add(article['url'])
            logger.info(f"  Found {len(news_data['articles'])} articles for sector '{sector}'")

    except Exception as e:
        logger.warning(f"  Could not fetch news from News API for sector '{sector}': {e}")
        return []

    all_articles.sort(key=lambda x: x['publish_time'] or '', reverse=True)
    final_articles = all_articles[:max_articles]

    # Define the directory for sector news
    SECTOR_NEWS_DIR = os.path.join(os.path.dirname(NEWS_DATA_DIR), 'sector_news')
    os.makedirs(SECTOR_NEWS_DIR, exist_ok=True)

    # Sanitize sector name for filename and add timestamp
    safe_sector_name = re.sub(r'[^a-zA-Z0-9_]', '_', sector)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(SECTOR_NEWS_DIR, f"{safe_sector_name}_news_{timestamp}.json")

    with open(output_file, 'w') as f:
        json.dump({
            'sector': sector,
            'fetch_timestamp': datetime.now().isoformat(),
            'total_articles': len(final_articles),
            'articles': final_articles
        }, f, indent=2)

    logger.info(f"✅ Saved {len(final_articles)} news articles for sector '{sector}' to {output_file}")
    return final_articles
