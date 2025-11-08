import os
import re
import json
import logging
import requests
import time
import yfinance as yf
from datetime import datetime, timedelta
from typing import Dict, List, Any, Set
from difflib import SequenceMatcher
from .utils import retry_on_failure, NEWS_DATA_DIR, NEWS_INTERPRETATION_DIR

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)

GEMINI_MODEL = os.getenv('GEMINI_MODEL', 'gemini-2.5-pro')
TITLE_SIMILARITY_THRESHOLD = 0.75  # Titles with >75% similarity are considered duplicates (lowered to catch more variations)

if GEMINI_AVAILABLE:
    try:
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        gemini_model = genai.GenerativeModel(GEMINI_MODEL)
        logger.info(f"Google Generative AI initialized with model: {GEMINI_MODEL}")
    except Exception as e:
        logger.error(f"Failed to initialize Google Generative AI: {e}")
        gemini_model = None
else:
    gemini_model = None

def calculate_title_similarity(title1: str, title2: str) -> float:
    """Calculate similarity ratio between two titles (0-1 scale)."""
    if not title1 or not title2:
        return 0.0
    # Normalize titles: lowercase and remove extra whitespace
    t1 = ' '.join(title1.lower().split())
    t2 = ' '.join(title2.lower().split())
    return SequenceMatcher(None, t1, t2).ratio()

def is_duplicate_title(new_title: str, existing_titles: Set[str], threshold: float = TITLE_SIMILARITY_THRESHOLD) -> bool:
    """Check if a new title is too similar to any existing titles."""
    for existing_title in existing_titles:
        if calculate_title_similarity(new_title, existing_title) >= threshold:
            return True
    return False

def filter_and_rank_articles_with_ai(ticker: str, company_name: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Use Gemini AI to filter and rank articles by company relevance and importance."""
    if not gemini_model or not articles:
        return articles

    logger.info(f"Filtering and ranking {len(articles)} articles with AI for {ticker}...")

    # Process articles in batches to avoid token limits
    batch_size = 10
    ranked_articles = []

    for i in range(0, len(articles), batch_size):
        batch = articles[i:i+batch_size]

        # Create prompt for filtering and ranking
        prompt = f"""You are a financial news analyst. Your task is to filter and rank news articles for {company_name} ({ticker}).

For each article below, evaluate if it meets BOTH criteria:
1. **Company-Specific**: The article is specifically about {company_name} ({ticker}), not just mentioning it in passing or discussing the broader industry.
2. **Factual**: The article reports factual news (earnings, product launches, partnerships, regulatory actions, etc.), NOT opinion pieces, market analysis, or speculation.

For articles that meet BOTH criteria, assign an importance score (1-10):
- 10: Major company news (earnings, CEO changes, major partnerships, product launches)
- 7-9: Significant company news (analyst upgrades, medium partnerships, operational updates)
- 4-6: Minor company news (mentions in industry reports, small updates)
- 1-3: Tangential relevance

Articles to evaluate:
"""

        for idx, article in enumerate(batch, 1):
            title = article.get('title', '')
            summary = article.get('summary', '')
            prompt += f"\n{idx}. Title: {title}\n"
            if summary:
                prompt += f"   Summary: {summary}\n"

        prompt += """
Please respond with a JSON object mapping article numbers to importance scores.
Example: {"1": 9, "3": 7, "5": 10} means article 1 scores 9, article 3 scores 7, article 5 scores 10.
Only include articles that meet BOTH criteria (company-specific AND factual).
Response format: Just the JSON object, nothing else."""

        try:
            response = gemini_model.generate_content(prompt)
            response_text = response.text.strip()

            # Extract JSON object from response
            json_match = re.search(r'\{[^}]+\}', response_text)
            if json_match:
                scores = json.loads(json_match.group(0))
                # Add scored articles from this batch
                for idx_str, score in scores.items():
                    idx = int(idx_str)
                    if 1 <= idx <= len(batch):
                        article = batch[idx - 1].copy()
                        article['importance_score'] = score
                        ranked_articles.append(article)
                logger.info(f"  Batch {i//batch_size + 1}: {len(scores)}/{len(batch)} articles passed AI filter")
            else:
                logger.warning(f"  Could not parse AI response for batch {i//batch_size + 1}, keeping all articles with default score")
                for article in batch:
                    article_copy = article.copy()
                    article_copy['importance_score'] = 5  # Default score
                    ranked_articles.append(article_copy)

            # Rate limiting
            time.sleep(1)

        except Exception as e:
            logger.warning(f"  Error filtering batch {i//batch_size + 1} with AI: {e}. Keeping all articles with default score.")
            for article in batch:
                article_copy = article.copy()
                article_copy['importance_score'] = 5  # Default score
                ranked_articles.append(article_copy)

    # Sort by importance score (highest first)
    ranked_articles.sort(key=lambda x: x.get('importance_score', 0), reverse=True)

    logger.info(f"✓ AI filtering: {len(ranked_articles)}/{len(articles)} articles passed, sorted by importance")
    return ranked_articles

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_news_for_ticker(ticker: str, company_name: str, max_articles: int = 5) -> List[Dict[str, Any]]:
    logger.info(f"Fetching news for {ticker} ({company_name})...")
    all_articles = []
    seen_urls = set()
    seen_titles = set()  # Track titles for deduplication

    # Calculate date range: last 24 hours
    now = datetime.now()
    from_date = (now - timedelta(days=1)).strftime('%Y-%m-%d')
    to_date = now.strftime('%Y-%m-%d')
    logger.info(f"  Fetching news from {from_date} to {to_date} (last 24 hours)")

    try:
        stock = yf.Ticker(ticker)
        news = stock.news
        if news:
            for item in news:
                title = item.get('title', '')
                link = item.get('link', '')

                # Check for URL and title duplicates
                if link not in seen_urls and not is_duplicate_title(title, seen_titles):
                    all_articles.append({
                        'source': 'Yahoo Finance',
                        'title': title,
                        'link': link,
                        'publisher': item.get('publisher'),
                        'publish_time': datetime.fromtimestamp(item['providerPublishTime']).isoformat() if 'providerPublishTime' in item else None,
                        'summary': None,
                        'type': item.get('type')
                    })
                    seen_urls.add(link)
                    seen_titles.add(title)
            logger.info(f"  Found {len(news)} articles from Yahoo Finance")
    except Exception as e:
        logger.warning(f"  Could not fetch news from Yahoo Finance for {ticker}: {e}")

    news_api_key = os.getenv("NEWS_API_KEY")
    if news_api_key:
        try:
            # More specific query to focus on company-specific news from last 24 hours
            query = f'"{company_name}" OR "{ticker}"'
            url = f"https://newsapi.org/v2/everything?q={query}&from={from_date}&to={to_date}&apiKey={news_api_key}&language=en&sortBy=publishedAt&pageSize=50"
            response = requests.get(url)
            response.raise_for_status()
            news_data = response.json()
            if news_data.get('articles'):
                for article in news_data['articles']:
                    title = article.get('title', '')
                    link = article.get('url', '')

                    # Check for URL and title duplicates
                    if link not in seen_urls and not is_duplicate_title(title, seen_titles):
                        all_articles.append({
                            'source': 'News API',
                            'title': title,
                            'link': link,
                            'publisher': article['source'].get('name'),
                            'publish_time': article.get('publishedAt'),
                            'summary': article.get('description'),
                            'type': 'Article'
                        })
                        seen_urls.add(link)
                        seen_titles.add(title)
                logger.info(f"  Found {len(news_data['articles'])} articles from News API")
        except Exception as e:
            logger.warning(f"  Could not fetch news from News API for {ticker}: {e}")

    fmp_api_key = os.getenv("FMP_API_KEY")
    if fmp_api_key:
        try:
            url = f"https://financialmodelingprep.com/api/v3/stock_news?tickers={ticker}&limit=50&apikey={fmp_api_key}"
            response = requests.get(url)
            response.raise_for_status()
            fmp_news = response.json()
            if fmp_news:
                for article in fmp_news:
                    title = article.get('title', '')
                    link = article.get('url', '')

                    # Check for URL and title duplicates
                    if link not in seen_urls and not is_duplicate_title(title, seen_titles):
                        all_articles.append({
                            'source': 'Financial Modeling Prep',
                            'title': title,
                            'link': link,
                            'publisher': article.get('site'),
                            'publish_time': article.get('publishedDate'),
                            'summary': article.get('text'),
                            'type': 'Article'
                        })
                        seen_urls.add(link)
                        seen_titles.add(title)
                logger.info(f"  Found {len(fmp_news)} articles from FMP")
        except Exception as e:
            logger.warning(f"  Could not fetch news from FMP for {ticker}: {e}")

    logger.info(f"  Total articles after deduplication: {len(all_articles)}")

    # Filter articles to only include those from last 24 hours
    cutoff_time = now - timedelta(days=1)
    recent_articles = []
    for article in all_articles:
        pub_time = article.get('publish_time')
        if pub_time:
            try:
                # Parse the publish time
                if isinstance(pub_time, str):
                    # Handle ISO format (2024-11-07T12:00:00Z)
                    pub_dt = datetime.fromisoformat(pub_time.replace('Z', '+00:00'))
                    # Remove timezone for comparison
                    pub_dt = pub_dt.replace(tzinfo=None)
                else:
                    pub_dt = pub_time

                # Only include if published in last 24 hours
                if pub_dt >= cutoff_time:
                    recent_articles.append(article)
            except (ValueError, AttributeError) as e:
                logger.warning(f"  Could not parse publish_time '{pub_time}': {e}")
                # If we can't parse, include it to be safe
                recent_articles.append(article)
        else:
            # No publish time, include it
            recent_articles.append(article)

    logger.info(f"  Articles from last 24 hours: {len(recent_articles)}")

    # Sort by publish time (most recent first)
    recent_articles.sort(key=lambda x: x['publish_time'] or '', reverse=True)

    # Apply AI filtering and ranking for company-specific, factual, and important content
    ranked_articles = filter_and_rank_articles_with_ai(ticker, company_name, recent_articles)

    # Take top N most important articles after filtering and ranking
    final_articles = ranked_articles[:max_articles]

    # Add timestamp suffix to filename
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_file = os.path.join(NEWS_DATA_DIR, f"{ticker}_news_{timestamp}.json")
    with open(output_file, 'w') as f:
        json.dump({
            'ticker': ticker,
            'company_name': company_name,
            'fetch_timestamp': datetime.now().isoformat(),
            'date_range': {
                'from': from_date,
                'to': to_date,
                'description': 'Last 24 hours'
            },
            'total_articles': len(final_articles),
            'filtering_stats': {
                'total_fetched': len(all_articles),
                'after_date_filter': len(recent_articles),
                'after_ai_filter_and_ranking': len(ranked_articles),
                'final_count': len(final_articles),
                'deduplication_enabled': True,
                'ai_filter_enabled': gemini_model is not None,
                'importance_ranking_enabled': gemini_model is not None
            },
            'articles': final_articles
        }, f, indent=2)

    logger.info(f"✅ Saved {len(final_articles)} most important, company-specific, factual news articles for {ticker} (last 24 hours)")
    logger.info(f"   Filtering pipeline: {len(all_articles)} fetched → {len(recent_articles)} from last 24h → {len(ranked_articles)} after AI filter → {len(final_articles)} top ranked")
    return final_articles

def interpret_news_with_gemini(ticker: str, company_name: str, articles: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not gemini_model:
        logger.warning("Google Gemini model not available. Skipping news interpretation.")
        return {
            'interpretation': 'Gemini model not available.',
            'recommendation': 'N/A',
            'reasoning': 'N/A',
            'interpretation_timestamp': datetime.now().isoformat()
        }

    if not articles:
        return {
            'interpretation': 'No news articles to analyze.',
            'recommendation': 'N/A',
            'reasoning': 'No data.',
            'interpretation_timestamp': datetime.now().isoformat()
        }

    logger.info(f"Interpreting news for {ticker} with Gemini...")

    prompt = f"""
    As a senior financial analyst, your task is to analyze the following news headlines for {company_name} ({ticker}) and provide a concise investment recommendation.

    **News Headlines:**
    """
    for i, article in enumerate(articles[:10]):
        prompt += f"{i+1}. {article['title']} (Source: {article['publisher']})\n"

    prompt += """
    **Analysis and Recommendation:**

    Based on these headlines, please provide the following in a structured format:

    1.  **INTERPRETATION:** A brief (2-3 sentences) summary of the overall sentiment and key themes from the news. Is the news generally positive, negative, or mixed? What are the main drivers?
    2.  **RECOMMENDATION:** A clear investment recommendation: **BUY**, **HOLD**, or **SELL**.
    3.  **REASONING:** A concise (1-2 sentences) explanation for your recommendation, directly referencing the news.

    **Example Output:**
    INTERPRETATION: The recent news for the company is largely positive, focusing on strong earnings and new product launches. However, there are some concerns about regulatory scrutiny.
    RECOMMENDATION: BUY
    REASONING: The strong earnings report and positive product momentum outweigh the potential regulatory risks, suggesting a favorable risk/reward profile at the current valuation.
    """

    try:
        response = gemini_model.generate_content(prompt)
        interpretation_text = response.text

        interpretation = "N/A"
        recommendation = "N/A"
        reasoning = "N/A"

        interp_match = re.search(r'INTERPRETATION[:\*\s]+(.*?)\s*\d*\.\s*\**RECOMMENDATION', interpretation_text, re.DOTALL)
        if interp_match:
            interpretation = interp_match.group(1).strip()

        # Try multiple patterns for recommendation
        rec_match = re.search(r'RECOMMENDATION[:\*\s]+(BUY|HOLD|SELL)', interpretation_text, re.IGNORECASE)
        if rec_match:
            recommendation = rec_match.group(1).strip().upper()

        reason_match = re.search(r'REASONING[:\*\s]+(.*?)(?:\n\n|$)', interpretation_text, re.DOTALL)
        if reason_match:
            reasoning = reason_match.group(1).strip()

        result = {
            'ticker': ticker,
            'company_name': company_name,
            'interpretation': interpretation,
            'recommendation': recommendation,
            'reasoning': reasoning,
            'full_response': interpretation_text,
            'interpretation_timestamp': datetime.now().isoformat()
        }

        # Add timestamp suffix to filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(NEWS_INTERPRETATION_DIR, f"{ticker}_news_interpretation_{timestamp}.json")
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2)

        logger.info(f"✅ Saved news interpretation for {ticker} to {output_file}")
        return result

    except Exception as e:
        logger.error(f"Error interpreting news for {ticker} with Gemini: {e}")
        return {
            'interpretation': f'Error during Gemini analysis: {e}',
            'recommendation': 'N/A',
            'reasoning': 'N/A',
            'interpretation_timestamp': datetime.now().isoformat()
        }

def fetch_and_interpret_news(companies_df):
    logger.info("=" * 60)
    logger.info("FETCHING AND INTERPRETING NEWS")
    logger.info("=" * 60)

    for index, row in companies_df.iterrows():
        ticker = row['ticker']
        company_name = row['company_name']

        articles = fetch_news_for_ticker(ticker, company_name)

        if articles:
            interpret_news_with_gemini(ticker, company_name, articles)
        else:
            logger.warning(f"No articles found for {ticker}, skipping interpretation.")

        time.sleep(2)
