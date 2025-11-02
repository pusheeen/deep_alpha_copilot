#!/usr/bin/env python3
"""
Data fetching script for the financial agent project.
Fetches:
1. Company information from SEC (ticker, company name, CIK)
2. CEO profiles and information
3. Financial statements
4. Stock prices
5. 10-K filings
"""

import os
import requests
import pandas as pd
import numpy as np
import json
import time
import csv
import re
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm
import yfinance as yf
from bs4 import BeautifulSoup
from typing import Dict, List, Any, Optional, Callable
import logging
import atexit

# Optional neo4j import - using JSON files instead
try:
    from neo4j import GraphDatabase, basic_auth
    NEO4J_AVAILABLE = True
except ImportError:
    NEO4J_AVAILABLE = False
    GraphDatabase = None
    basic_auth = None

from functools import wraps
from datetime import datetime, timezone
import re
from dotenv import load_dotenv
load_dotenv()
# Model for news factual judgement and interpretation
NEWS_LLM_MODEL = os.getenv('NEWS_LLM_MODEL', 'claude-3-5-sonnet-20241022')

# Optional imports for Reddit
try:
    import praw
    import feedparser
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    REDDIT_AVAILABLE = True
except ImportError:
    REDDIT_AVAILABLE = False
    print("Warning: Reddit scraping not available. Install praw, feedparser, and vaderSentiment to enable.")

# Optional imports for X/Twitter
try:
    import tweepy
    X_AVAILABLE = True
except ImportError:
    X_AVAILABLE = False
    print("Warning: X/Twitter scraping not available. Install tweepy to enable.")

# Optional imports for Anthropic Claude
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: Anthropic not available. News filtering will be disabled. Install anthropic to enable.")

# Optional imports for Google Gemini
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("Warning: Google Generative AI not available. Install google-generativeai to enable.")

# Load environment variables
load_dotenv()
SEC_USER_AGENT = os.getenv("SEC_USER_AGENT", "Your Name your.email@provider.com")

# Import target tickers
from target_tickers import TARGET_TICKERS

# Dynamically generate ticker aliases based on TARGET_TICKERS
TICKER_ALIASES: Dict[str, List[str]] = {ticker: [ticker, f'${ticker}'] for ticker in TARGET_TICKERS}
import sys  # for command-line ticker override

# Allow overriding TARGET_TICKERS via command-line args
# Usage: python fetch_data.py TICKER1 TICKER2 ...
if __name__ == "__main__" and len(sys.argv) > 1:
    # Parse tickers from args and override defaults
    new_tickers = [arg.strip().upper() for arg in sys.argv[1:]]
    TARGET_TICKERS = new_tickers
    # Regenerate aliases based on overridden TARGET_TICKERS
    TICKER_ALIASES = {ticker: [ticker, f'${ticker}'] for ticker in TARGET_TICKERS}
    # Clean up sys.argv so downstream libraries don't see extra args
    sys.argv = sys.argv[:1]

# Official Twitter/X handles for companies and CEOs
COMPANY_X_HANDLES = {
    'NVDA': 'nvidia',
    'AMD': 'AMD',
    'TSM': 'TSMC',
    'AVGO': 'Broadcom',
    'ORCL': 'Oracle',
}

CEO_X_HANDLES = {
    'NVDA': 'JenHsunHuang',  # Jensen Huang
    'AMD': 'LisaSu',  # Lisa Su
    'TSM': None,  # C.C. Wei doesn't have a public Twitter
    'AVGO': None,  # Hock Tan doesn't have a public Twitter
    'ORCL': None,  # Michael Sicilia doesn't have a public Twitter (Larry Ellison has @larryellison but he's not current CEO)
}

# --- Configuration ---
DATA_DIR = "data"
COMPANIES_CSV_PATH = "data/companies.csv"
FINANCIALS_DIR = "data/structured/financials"
PRICES_DIR = "data/structured/prices"
FILINGS_10K_DIR = "data/unstructured/10k"
CEO_REPORTS_DIR = "data/reports"
REDDIT_DATA_DIR = "data/unstructured/reddit"
X_DATA_DIR = "data/unstructured/x"
NEWS_DATA_DIR = "data/unstructured/news"
NEWS_INTERPRETATION_DIR = "data/unstructured/news_interpretation"
EARNINGS_DIR = "data/structured/earnings"
SECTOR_METRICS_DIR = "data/structured/sector_metrics"
FALLBACK_REDDIT_POST_FILES = [
    Path(REDDIT_DATA_DIR) / "reddit_posts_comprehensive.json",
    Path(REDDIT_DATA_DIR) / "reddit_posts_3months.json",
    Path(REDDIT_DATA_DIR) / "reddit_posts_sample.json",
    Path(REDDIT_DATA_DIR) / "reddit_posts_rss_20251005_233054.json",
]

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(FINANCIALS_DIR, exist_ok=True)
os.makedirs(PRICES_DIR, exist_ok=True)
os.makedirs(FILINGS_10K_DIR, exist_ok=True)
os.makedirs(CEO_REPORTS_DIR, exist_ok=True)
os.makedirs(REDDIT_DATA_DIR, exist_ok=True)
os.makedirs(X_DATA_DIR, exist_ok=True)
os.makedirs(NEWS_DATA_DIR, exist_ok=True)
os.makedirs(NEWS_INTERPRETATION_DIR, exist_ok=True)
os.makedirs(EARNINGS_DIR, exist_ok=True)
os.makedirs(SECTOR_METRICS_DIR, exist_ok=True)
# Directory for market indices
MARKET_INDEX_DIR = os.path.join(DATA_DIR, 'market_index')
os.makedirs(MARKET_INDEX_DIR, exist_ok=True)
# Ensure per-company CEO profiles directory
CEO_PROFILE_DIR = os.path.join(DATA_DIR, 'ceo_profiles')
os.makedirs(CEO_PROFILE_DIR, exist_ok=True)

# Directories for news articles and interpretations
NEWS_DATA_DIR = os.path.join(DATA_DIR, 'unstructured', 'news')
os.makedirs(NEWS_DATA_DIR, exist_ok=True)
NEWS_INTERPRETATION_DIR = os.path.join(DATA_DIR, 'unstructured', 'news_interpretation')
os.makedirs(NEWS_INTERPRETATION_DIR, exist_ok=True)

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data_fetch.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# --- Neo4j Connection for Earnings Storage ---
NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://a71a1e63.databases.neo4j.io")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "bSGrnZh1_1dWDXVz-xEiV6LOHIv5klPln0P2B4kWyN0")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

# Initialize neo4j driver only if library is available
if NEO4J_AVAILABLE and GraphDatabase is not None:
    try:
        neo4j_driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=basic_auth(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        logger.info("Neo4j driver initialized successfully")
    except Exception as neo4j_error:
        neo4j_driver = None
        logger.warning(f"Unable to initialize Neo4j driver: {neo4j_error}")
else:
    neo4j_driver = None
    logger.info("Neo4j is disabled - using JSON files for data storage")


def close_neo4j_driver():
    if neo4j_driver:
        neo4j_driver.close()


atexit.register(close_neo4j_driver)

# Static CEO database cache (to avoid repeated web searches for known CEOs)
# This will be populated from data/reports/ceo_summary_*.csv if available
_CEO_CACHE = {}


# --- Retry Decorator ---
def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0, exceptions: tuple = (Exception,)):
    """
    Decorator to retry a function on failure with exponential backoff.

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries in seconds
        backoff: Multiplier for delay after each retry
        exceptions: Tuple of exceptions to catch and retry on
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    if attempt < max_retries:
                        # Extract ticker from args for better logging
                        ticker = args[0] if args else "unknown"
                        logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed for {func.__name__}({ticker}): {str(e)}")
                        logger.info(f"Retrying in {current_delay:.1f} seconds...")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All {max_retries + 1} attempts failed for {func.__name__}({ticker if 'ticker' in locals() else 'unknown'}): {str(e)}")

            # If all retries failed, log and return None or raise
            return None

        return wrapper
    return decorator


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_company_info_from_sec() -> pd.DataFrame:
    """
    Fetches company information (ticker, company name, CIK) from SEC
    for all tickers in TARGET_TICKERS.
    """
    logger.info("Fetching company information from SEC...")

    url = "https://www.sec.gov/files/company_tickers.json"
    headers = {'User-Agent': SEC_USER_AGENT}

    try:
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        company_data = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading SEC data: {e}")
        return pd.DataFrame()

    # Process the data into a list of dictionaries
    all_companies = [
        {
            "cik": str(details['cik_str']),
            "ticker": details['ticker'],
            "company_name": details['title']
        }
        for details in company_data.values()
    ]

    # Convert to DataFrame
    df = pd.DataFrame(all_companies)

    # Filter for only the tickers in TARGET_TICKERS
    filtered_df = df[df['ticker'].isin(TARGET_TICKERS)]

    # Ensure the columns are in the desired order
    final_df = filtered_df[['ticker', 'company_name', 'cik']]

    # Save to CSV
    final_df.to_csv(COMPANIES_CSV_PATH, index=False)

    logger.info(f"Successfully fetched {len(final_df)} companies from SEC")
    logger.info(f"Saved to {COMPANIES_CSV_PATH}")

    return final_df


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def search_linkedin_profile(ceo_name: str, company_name: str) -> Dict[str, Any]:
    """
    Search for LinkedIn profile URL and extract profile data using Google search.
    """
    linkedin_data = {
        "linkedin_url": "Not found",
        "education": "Not found",
        "past_experience": [],
        "career_highlights": [],
        "start_date": "Not found",
        "tenure_duration": "Not found"
    }

    if ceo_name == "Not found" or not ceo_name:
        return linkedin_data

    try:
        # Clean CEO name (remove titles like Mr., Dr., etc.)
        clean_name = re.sub(r'\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s*', '', ceo_name).strip()

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }

        # Search for LinkedIn profile
        search_query = f"{clean_name} {company_name} CEO LinkedIn"
        search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Find LinkedIn URL in search results
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com/in/' in href:
                    # Extract clean LinkedIn URL
                    match = re.search(r'(https://[a-z]+\.linkedin\.com/in/[^&\s]+)', href)
                    if match:
                        linkedin_url = match.group(1)
                        # Remove trailing garbage
                        linkedin_url = re.sub(r'["\'].*$', '', linkedin_url)
                        linkedin_data["linkedin_url"] = linkedin_url
                        logger.info(f"Found LinkedIn URL: {linkedin_url}")
                        break

        # If LinkedIn URL found, try to scrape profile page for additional info
        if linkedin_data["linkedin_url"] != "Not found":
            time.sleep(2)  # Be respectful
            try:
                profile_response = requests.get(linkedin_data["linkedin_url"], headers=headers, timeout=15)
                if profile_response.status_code == 200:
                    profile_soup = BeautifulSoup(profile_response.content, 'html.parser')
                    page_text = profile_soup.get_text()

                    # Try to extract education (basic pattern matching)
                    education_patterns = [
                        r'(University|College|Institute|School) of [A-Z][a-z\s]+',
                        r'(Harvard|Stanford|MIT|Yale|Princeton|Berkeley|Cambridge|Oxford)[^,\.]*',
                        r'(Bachelor|Master|MBA|PhD|B\.S\.|M\.S\.|B\.A\.|M\.A\.)[^,\.]{0,50}'
                    ]

                    for pattern in education_patterns:
                        matches = re.findall(pattern, page_text, re.IGNORECASE)
                        if matches:
                            # Take first 2 matches to avoid too much data
                            linkedin_data["education"] = ', '.join(matches[:2])
                            break

                    # Try to extract experience (look for company names and positions)
                    experience_pattern = r'(Chief|Senior|Vice President|Director|Manager|Head of)[^\.]{0,100}'
                    experience_matches = re.findall(experience_pattern, page_text)
                    if experience_matches:
                        linkedin_data["past_experience"] = experience_matches[:5]  # Top 5

                    # Try to find start date / tenure
                    year_patterns = re.findall(r'(20\d{2})\s*-\s*Present', page_text, re.IGNORECASE)
                    if year_patterns:
                        start_year = int(year_patterns[0])
                        current_year = datetime.now().year
                        years = current_year - start_year
                        linkedin_data["start_date"] = str(start_year)
                        linkedin_data["tenure_duration"] = f"{years} year{'s' if years != 1 else ''}"

            except Exception as e:
                logger.warning(f"Could not scrape LinkedIn profile: {e}")

        time.sleep(2)  # Rate limiting

    except Exception as e:
        logger.warning(f"LinkedIn search failed: {e}")

    return linkedin_data


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def query_ceo_info_by_ticker(ticker: str, company_name: str) -> Dict[str, Any]:
    """
    Queries CEO information by company ticker using yfinance and LinkedIn.
    """
    try:
        if not ticker or not isinstance(ticker, str):
            return {"error": "Invalid ticker"}

        ticker = ticker.upper().strip()
        logger.info(f"Fetching CEO data for {ticker}")

        ceo_data = {
            "ticker": ticker,
            "company_name": company_name,
            "ceo_name": "Not found",
            "ceo_title": "Not found",
            "tenure_duration": "Not found",
            "start_date": "Not found",
            "linkedin_url": "Not found",
            "source": "yfinance + LinkedIn",
            "past_experience": [],
            "education": "Not found",
            "career_highlights": [],
            "fetch_timestamp": datetime.now().isoformat()
        }

        # Try to get officer information from yfinance
        try:
            stock = yf.Ticker(ticker)

            # Get company info which includes officers
            info = stock.info

            # Try to get officers data
            if hasattr(stock, 'get_officers') and callable(stock.get_officers):
                officers = stock.get_officers()
                if officers is not None and not officers.empty:
                    # Look for CEO in the officers list
                    for idx, officer in officers.iterrows():
                        title = officer.get('title', '').lower()
                        if 'chief executive officer' in title or 'ceo' in title or title == 'ceo':
                            ceo_data["ceo_name"] = officer.get('name', 'Not found')
                            ceo_data["ceo_title"] = officer.get('title', 'Chief Executive Officer')

                            # Try to get age/tenure info
                            if 'age' in officer:
                                ceo_data["age"] = officer.get('age')

                            # Try to get pay info
                            if 'totalPay' in officer:
                                ceo_data["total_pay"] = officer.get('totalPay')

                            logger.info(f"Found CEO {ceo_data['ceo_name']} via yfinance officers")
                            break

            # Fallback: Try to get CEO from company info
            if ceo_data["ceo_name"] == "Not found":
                # Some companies have companyOfficers in info
                if 'companyOfficers' in info and info['companyOfficers']:
                    for officer in info['companyOfficers']:
                        title = officer.get('title', '').lower()
                        if 'chief executive officer' in title or 'ceo' in title:
                            ceo_data["ceo_name"] = officer.get('name', 'Not found')
                            ceo_data["ceo_title"] = officer.get('title', 'Chief Executive Officer')

                            # Get additional info if available
                            if 'age' in officer:
                                ceo_data["age"] = officer['age']
                            if 'yearBorn' in officer:
                                ceo_data["year_born"] = officer['yearBorn']
                            if 'totalPay' in officer:
                                ceo_data["total_pay"] = officer['totalPay']

                            logger.info(f"Found CEO {ceo_data['ceo_name']} via yfinance info")
                            break

            # If still not found, try alternative field names
            if ceo_data["ceo_name"] == "Not found":
                # Check for CEO in various info fields
                for field in ['ceo', 'CEO', 'chiefExecutiveOfficer']:
                    if field in info and info[field]:
                        ceo_data["ceo_name"] = info[field]
                        ceo_data["ceo_title"] = "Chief Executive Officer"
                        logger.info(f"Found CEO {ceo_data['ceo_name']} via yfinance {field} field")
                        break

        except Exception as e:
            logger.warning(f"yfinance lookup failed for {ticker}: {e}")

        # Enrich with LinkedIn data
        if ceo_data["ceo_name"] != "Not found":
            logger.info(f"Searching LinkedIn for {ceo_data['ceo_name']}")
            linkedin_data = search_linkedin_profile(ceo_data["ceo_name"], company_name)

            # Update CEO data with LinkedIn info (only if found)
            if linkedin_data["linkedin_url"] != "Not found":
                ceo_data["linkedin_url"] = linkedin_data["linkedin_url"]

            if linkedin_data["education"] != "Not found":
                ceo_data["education"] = linkedin_data["education"]

            if linkedin_data["past_experience"]:
                ceo_data["past_experience"] = linkedin_data["past_experience"]

            if linkedin_data["start_date"] != "Not found":
                ceo_data["start_date"] = linkedin_data["start_date"]
                ceo_data["tenure_duration"] = linkedin_data["tenure_duration"]

        return {
            "success": True,
            "ceo_data": ceo_data,
            "note": "CEO information from yfinance and LinkedIn"
        }

    except Exception as e:
        logger.error(f"Error fetching CEO for {ticker}: {e}")
        return {"error": f"Error: {str(e)}"}


def fetch_ceo_profiles(companies_df: pd.DataFrame):
    """
    Fetches CEO profiles for all companies in the dataframe.
    """
    logger.info("=" * 60)
    logger.info("Starting CEO profile batch processing")
    logger.info("=" * 60)

    results = []
    successful_count = 0
    failed_count = 0

    for index, row in companies_df.iterrows():
        ticker = row['ticker'].upper()
        company_name = row['company_name']

        logger.info(f"Processing CEO for {index+1}/{len(companies_df)}: {ticker} ({company_name})")

        try:
            # Fetch CEO data
            result = query_ceo_info_by_ticker(ticker, company_name)
            results.append(result)
            # Save individual CEO profile
            profile_data = result.get('ceo_data') if result.get('success', False) else result
            ceo_file = os.path.join(CEO_PROFILE_DIR, f"{ticker}_ceo_profile.json")
            with open(ceo_file, 'w', encoding='utf-8') as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved CEO profile for {ticker} to {ceo_file}")

            if result.get('success', False):
                successful_count += 1
                ceo_name = result.get('ceo_data', {}).get('ceo_name', 'Not found')
                logger.info(f"✅ {ticker}: Found CEO {ceo_name}")
            else:
                failed_count += 1
                error = result.get('error', 'Unknown error')
                logger.warning(f"❌ {ticker}: {error}")

        except Exception as e:
            logger.error(f"❌ {ticker}: Unexpected error - {e}")
            results.append({
                'success': False,
                'ticker': ticker,
                'error': f"Unexpected error: {str(e)}"
            })
            failed_count += 1

        # Delay between requests (longer due to Google search + LinkedIn scraping)
        if index < len(companies_df) - 1:
            time.sleep(5)

    # Create summary reports
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # JSON report
    json_report = {
        "batch_info": {
            "timestamp": datetime.now().isoformat(),
            "total_companies": len(companies_df),
            "successful_fetches": successful_count,
            "failed_fetches": failed_count
        },
        "results": results
    }

    json_filename = os.path.join(CEO_REPORTS_DIR, f"ceo_batch_report_{timestamp}.json")
    with open(json_filename, 'w', encoding='utf-8') as f:
        json.dump(json_report, f, indent=2, ensure_ascii=False)

    # CSV report
    csv_filename = os.path.join(CEO_REPORTS_DIR, f"ceo_summary_{timestamp}.csv")
    with open(csv_filename, 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['ticker', 'company_name', 'ceo_name', 'ceo_title', 'tenure_duration',
                     'start_date', 'education', 'num_past_roles', 'num_highlights',
                     'linkedin_url', 'source', 'fetch_timestamp']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            if result.get('success', False):
                ceo_data = result.get('ceo_data', {})
                writer.writerow({
                    'ticker': ceo_data.get('ticker', 'Unknown'),
                    'company_name': ceo_data.get('company_name', 'Unknown'),
                    'ceo_name': ceo_data.get('ceo_name', 'Not found'),
                    'ceo_title': ceo_data.get('ceo_title', 'Not found'),
                    'tenure_duration': ceo_data.get('tenure_duration', 'Not found'),
                    'start_date': ceo_data.get('start_date', 'Not found'),
                    'education': ceo_data.get('education', 'Not found'),
                    'num_past_roles': len(ceo_data.get('past_experience', [])),
                    'num_highlights': len(ceo_data.get('career_highlights', [])),
                    'linkedin_url': ceo_data.get('linkedin_url', 'Not found'),
                    'source': ceo_data.get('source', 'Unknown'),
                    'fetch_timestamp': ceo_data.get('fetch_timestamp', 'Unknown')
                })
            else:
                writer.writerow({
                    'ticker': result.get('ticker', 'Unknown'),
                    'company_name': 'Error',
                    'ceo_name': 'Error',
                    'ceo_title': 'Error',
                    'tenure_duration': 'Error',
                    'start_date': 'Error',
                    'education': 'Error',
                    'num_past_roles': 0,
                    'num_highlights': 0,
                    'linkedin_url': 'Error',
                    'source': 'Error',
                    'fetch_timestamp': datetime.now().isoformat()
                })

    # Final summary
    logger.info("=" * 60)
    logger.info("CEO BATCH PROCESSING COMPLETED")
    logger.info("=" * 60)
    logger.info(f"Total companies: {len(companies_df)}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Success rate: {successful_count/len(companies_df)*100:.1f}%")
    logger.info(f"JSON report: {json_filename}")
    logger.info(f"CSV report: {csv_filename}")





def _clean_numeric(value: Any) -> Optional[float]:
    """Convert values to floats where possible."""
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            if pd.isna(value):
                return None
            return float(value)
        if isinstance(value, str):
            value = value.strip().replace(',', '')
            if not value:
                return None
            return float(value)
    except (ValueError, TypeError):
        return None
    return None


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_quarterly_earnings(ticker: str) -> List[Dict[str, Any]]:
    """
    Fetches the latest four quarters of earnings data for a ticker.

    Returns:
        List of dictionaries containing quarter, revenue, earnings, net income, and EPS metrics.
    """
    logger.info(f"Fetching quarterly earnings for {ticker}...")
    records: List[Dict[str, Any]] = []

    try:
        stock = yf.Ticker(ticker)
        quarterly_earnings = stock.quarterly_earnings
        quarterly_financials = stock.quarterly_financials

        # Normalize financials columns for easier lookup
        financials_lookup = {}
        if quarterly_financials is not None and not quarterly_financials.empty:
            normalized_financials = quarterly_financials.copy()
            normalized_financials.columns = normalized_financials.columns.map(lambda c: str(c))
            for label in normalized_financials.index:
                financials_lookup[label] = normalized_financials.loc[label].to_dict()

        if quarterly_earnings is not None and not quarterly_earnings.empty:
            quarterly_earnings = quarterly_earnings.head(4)
            quarterly_earnings.index = quarterly_earnings.index.map(lambda idx: str(idx))
            for period, row in quarterly_earnings.iterrows():
                record = {
                    "ticker": ticker,
                    "period": period,
                    "revenue": _clean_numeric(row.get("Revenue")),
                    "earnings": _clean_numeric(row.get("Earnings")),
                    "net_income": None,
                    "eps": None,
                }

                if financials_lookup:
                    potential_keys = {
                        "net_income": ["Net Income", "NetIncome", "Net Income Applicable To Common Shares"],
                        "eps": ["Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"]
                    }
                    for target_key, candidates in potential_keys.items():
                        for candidate in candidates:
                            values = financials_lookup.get(candidate)
                            if values and period in values:
                                value = _clean_numeric(values[period])
                                if value is not None:
                                    record[target_key] = value
                                    break

                records.append(record)
        elif quarterly_financials is not None and not quarterly_financials.empty:
            logger.info(f"Quarterly earnings not available for {ticker}; falling back to quarterly financials.")
            normalized_financials = quarterly_financials.copy()
            normalized_financials.columns = normalized_financials.columns.map(lambda c: str(c))
            target_columns = list(normalized_financials.columns)[:4]

            for period in target_columns:
                record = {
                    "ticker": ticker,
                    "period": period,
                    "revenue": None,
                    "earnings": None,
                    "net_income": None,
                    "eps": None,
                }

                revenue_candidates = ["Total Revenue", "TotalRevenue", "Revenue"]
                earnings_candidates = ["Gross Profit", "Operating Income"]
                net_income_candidates = ["Net Income", "NetIncome", "Net Income Applicable To Common Shares"]
                eps_candidates = ["Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"]

                for candidate in revenue_candidates:
                    if candidate in normalized_financials.index:
                        record["revenue"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break
                for candidate in earnings_candidates:
                    if candidate in normalized_financials.index:
                        record["earnings"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break
                for candidate in net_income_candidates:
                    if candidate in normalized_financials.index:
                        record["net_income"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break
                for candidate in eps_candidates:
                    if candidate in normalized_financials.index:
                        record["eps"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break

                records.append(record)
        else:
            logger.warning(f"No quarterly earnings or financial data found for {ticker}")

        if records:
            output_path = os.path.join(EARNINGS_DIR, f"{ticker}_quarterly_earnings.json")
            with open(output_path, 'w') as f:
                json.dump(records, f, indent=2)
            logger.info(f"✅ Saved quarterly earnings for {ticker} to {output_path}")

        return records
    except Exception as exc:
        logger.error(f"Error fetching quarterly earnings for {ticker}: {exc}")
        return []


def fetch_financial_statements(ticker: str):
    """
    Fetch comprehensive financial statements from yfinance and save to JSON.

    Args:
        ticker: Stock ticker symbol
    """
    logger.info(f"Fetching financial statements for {ticker}...")

    try:
        stock = yf.Ticker(ticker)

        # Get all financial data
        financials_data = {
            "ticker": ticker,
            "fetch_date": datetime.now().isoformat(),
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow": {},
            "quarterly_income_statement": {},
            "quarterly_balance_sheet": {},
            "quarterly_cash_flow": {},
            "key_metrics": {}
        }

        # Helper function to convert DataFrame with datetime columns to dict
        def df_to_json_dict(df):
            if df is None or df.empty:
                return {}
            # Convert column names (which might be Timestamps) to strings
            df_copy = df.copy()
            df_copy.columns = df_copy.columns.map(str)
            return df_copy.to_dict()

        # Annual Income Statement
        if hasattr(stock, 'financials') and stock.financials is not None and not stock.financials.empty:
            financials_data["income_statement"] = df_to_json_dict(stock.financials)

        # Annual Balance Sheet
        if hasattr(stock, 'balance_sheet') and stock.balance_sheet is not None and not stock.balance_sheet.empty:
            financials_data["balance_sheet"] = df_to_json_dict(stock.balance_sheet)

        # Annual Cash Flow
        if hasattr(stock, 'cashflow') and stock.cashflow is not None and not stock.cashflow.empty:
            financials_data["cash_flow"] = df_to_json_dict(stock.cashflow)

        # Quarterly Income Statement
        if hasattr(stock, 'quarterly_financials') and stock.quarterly_financials is not None and not stock.quarterly_financials.empty:
            financials_data["quarterly_income_statement"] = df_to_json_dict(stock.quarterly_financials)

        # Quarterly Balance Sheet
        if hasattr(stock, 'quarterly_balance_sheet') and stock.quarterly_balance_sheet is not None and not stock.quarterly_balance_sheet.empty:
            financials_data["quarterly_balance_sheet"] = df_to_json_dict(stock.quarterly_balance_sheet)

        # Quarterly Cash Flow
        if hasattr(stock, 'quarterly_cashflow') and stock.quarterly_cashflow is not None and not stock.quarterly_cashflow.empty:
            financials_data["quarterly_cash_flow"] = df_to_json_dict(stock.quarterly_cashflow)

        # Get key metrics from info
        info = stock.info
        financials_data["key_metrics"] = {
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "revenue": info.get("totalRevenue"),
            "ebitda": info.get("ebitda"),
            "gross_profits": info.get("grossProfits"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

        # Save to JSON file
        output_file = os.path.join(FINANCIALS_DIR, f"{ticker}_financials.json")
        with open(output_file, 'w') as f:
            json.dump(financials_data, f, indent=2, default=str)

        logger.info(f"✅ Saved financial statements for {ticker}")

    except Exception as e:
        logger.error(f"Failed to fetch financials for {ticker}: {e}")


def store_quarterly_earnings_in_neo4j(ticker: str, company_name: Optional[str], earnings: List[Dict[str, Any]]):
    """Persist quarterly earnings records into Neo4j."""
    if not earnings:
        return
    if not neo4j_driver:
        logger.warning("Neo4j driver not available; skipping quarterly earnings storage.")
        return

    def transform(record: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "period": record.get("period"),
            "revenue": record.get("revenue"),
            "earnings": record.get("earnings"),
            "net_income": record.get("net_income"),
            "eps": record.get("eps")
        }

    try:
        with neo4j_driver.session(database=NEO4J_DATABASE) as session:
            session.execute_write(
                _upsert_quarterly_earnings,
                ticker,
                company_name,
                [transform(rec) for rec in earnings]
            )
        logger.info(f"✅ Stored quarterly earnings for {ticker} in Neo4j.")
    except Exception as exc:
        logger.error(f"Failed to store quarterly earnings for {ticker} in Neo4j: {exc}")


def _upsert_quarterly_earnings(tx, ticker: str, company_name: Optional[str], records: List[Dict[str, Any]]):
    query = """
    MERGE (c:Company {ticker: $ticker})
    ON CREATE SET c.name = coalesce($company_name, c.name)
    ON MATCH SET c.name = coalesce($company_name, c.name)
    WITH c, $records AS earnings
    UNWIND earnings AS record
    MERGE (q:QuarterlyEarnings {company: $ticker, period: record.period})
    SET q.revenue = record.revenue,
        q.earnings = record.earnings,
        q.netIncome = record.net_income,
        q.eps = record.eps,
        q.lastUpdated = datetime()
    MERGE (c)-[:HAS_QUARTERLY_EARNINGS]->(q)
    """
    tx.run(query, ticker=ticker, company_name=company_name, records=records)


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_stock_prices(ticker: str):
    """Fetches the maximum available daily stock prices using yfinance."""
    logger.info(f"Fetching stock prices for {ticker}...")
    try:
        stock = yf.Ticker(ticker)
        hist = stock.history(period="max")

        if hist.empty:
            logger.warning(f"No price data found for {ticker}")
            return

        hist.to_csv(os.path.join(PRICES_DIR, f"{ticker}_prices.csv"))
        logger.info(f"✅ Saved prices for {ticker}")
    except Exception as e:
        logger.error(f"Error fetching prices for {ticker}: {e}")


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_10k_filings(ticker: str, cik: str):
    """Fetches the last 5 annual 10-K or 20-F filings from the SEC EDGAR database."""
    logger.info(f"Fetching annual 10-K/20-F filings for {ticker} (CIK: {cik})...")
    headers = {'User-Agent': SEC_USER_AGENT}

    submissions_url = f"https://data.sec.gov/submissions/CIK{cik.zfill(10)}.json"
    try:
        response = requests.get(submissions_url, headers=headers)
        response.raise_for_status()
        submissions = response.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Error fetching submission history for {ticker}: {e}")
        return

    filing_count = 0
    recent_filings = submissions['filings']['recent']

    for i in range(len(recent_filings['form'])):
        if filing_count >= 5:
            break
        form = recent_filings['form'][i]
        if form in ('10-K', '20-F'):
            accession_no = recent_filings['accessionNumber'][i].replace('-', '')
            primary_doc_name = recent_filings['primaryDocument'][i]
            filing_date = recent_filings['filingDate'][i]
            year = filing_date.split('-')[0]

            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik}/{accession_no}/{primary_doc_name}"

            logger.info(f"  Downloading {form} for {year}...")
            try:
                time.sleep(0.2)
                doc_response = requests.get(doc_url, headers=headers)
                doc_response.raise_for_status()

                # Use form code (e.g., 10K, 20F) in filename
                form_code = form.replace('-', '')
                file_path = os.path.join(FILINGS_10K_DIR, f"{ticker}_{form_code}_{year}.html")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(doc_response.text)

                filing_count += 1
            except requests.exceptions.RequestException as e:
                logger.error(f"    Error downloading filing {doc_url}: {e}")

    logger.info(f"✅ Finished fetching filings for {ticker}")
    
# --- Market Indices Fetch Functions ---
@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_cboe_put_call_ratio() -> Any:
    """
    Fetches the CBOE total put/call ratio using Financial Modeling Prep or FRED API if available.
    Saves the result to data/market_index/put_call_ratio.json.
    """
    logger.info("Fetching CBOE put/call ratio...")
    # Try Financial Modeling Prep API
    fmp_key = os.getenv("FMP_API_KEY")
    if fmp_key:
        url = f"https://financialmodelingprep.com/api/v3/put-call-ratio?apikey={fmp_key}"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            output_path = os.path.join(MARKET_INDEX_DIR, "put_call_ratio.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved put/call ratio to {output_path}")
            return data
        except Exception as e:
            logger.error(f"Error fetching put/call ratio from FMP: {e}")
    # Try FRED API
    fred_key = os.getenv("FRED_API_KEY")
    if fred_key:
        series_id = "PC1"
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={fred_key}&file_type=json"
        try:
            resp = requests.get(url)
            resp.raise_for_status()
            data = resp.json()
            output_path = os.path.join(MARKET_INDEX_DIR, "put_call_ratio.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved put/call ratio to {output_path}")
            return data
        except Exception as e:
            logger.error(f"Error fetching put/call ratio from FRED: {e}")
    # Fallback: scrape Yahoo Finance HTML for ^PCR quote
    try:
        logger.info("Falling back to scraping Yahoo Finance for ^PCR")
        y_url = "https://finance.yahoo.com/quote/%5EPCR"
        headers = {'User-Agent': 'Mozilla/5.0'}
        resp = requests.get(y_url, headers=headers, timeout=10)
        resp.raise_for_status()
        # Extract raw price
        match = re.search(r'"regularMarketPrice":\{"raw":([0-9\.]+)', resp.text)
        if match:
            price = float(match.group(1))
            data = {
                "symbol": "^PCR",
                "put_call_ratio": price,
                "fetch_timestamp": datetime.now().isoformat()
            }
            output_path = os.path.join(MARKET_INDEX_DIR, "put_call_ratio.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved put/call ratio (scraped) to {output_path}")
            return data
        else:
            logger.error("Could not parse put/call ratio from Yahoo Finance HTML.")
    except Exception as e:
        logger.error(f"Error scraping Yahoo Finance for put/call ratio: {e}")
    # All methods failed
    logger.error("Unable to fetch put/call ratio via FMP, FRED, or Yahoo Finance.")
    return None

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_market_indices() -> Dict[str, Any]:
    """
    Fetches major market indices (VIX, NASDAQ, Dow Jones, Russell 2000) and CBOE put/call ratio.
    Saves each dataset as JSON in data/market_index.
    """
    indices = {
        "vix": "^VIX",
        "nasdaq": "^IXIC",
        "dowjones": "^DJI",
        "russell2000": "^RUT",
    }
    results: Dict[str, Any] = {}
    for name, ticker in indices.items():
        logger.info(f"Fetching market index {name} ({ticker})...")
        try:
            stock = yf.Ticker(ticker)
            hist = stock.history(period="5y")
            data = []
            if hist is not None and not hist.empty:
                df = hist.reset_index()
                df['Date'] = df['Date'].dt.strftime("%Y-%m-%d")
                data = df.to_dict(orient="records")
            output_path = os.path.join(MARKET_INDEX_DIR, f"{name}.json")
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"✅ Saved {name} data to {output_path}")
            results[name] = data
        except Exception as e:
            logger.error(f"Error fetching {name} ({ticker}): {e}")
            results[name] = None
    # Fetch put/call ratio
    put_call_data = fetch_cboe_put_call_ratio()
    results["put_call_ratio"] = put_call_data
    return results


# ========== REDDIT SCRAPING FUNCTIONS (PRAW API) ==========

# Subreddits to scrape
SUBREDDITS = [
    'stocks', 'investing', 'wallstreetbets', 'SecurityAnalysis', 'ValueInvesting',
    'UraniumSqueeze', 'uraniumstocks', 'renewableenergy', 'cryptomining',
    'BitcoinMining', 'NVDA', 'CryptoCurrency', 'gpumining', 'NiceHash',
    'EtherMining', 'CryptoMiningTalk', 'BitcoinMiningStock', 'CryptoMarkets'
]

# Time range: past 1 day
# Number of days back to fetch Reddit posts
# Number of days back to fetch Reddit posts (reset to daily fetch)
DAYS_BACK = 1


def contains_ticker(text: str) -> List[str]:
    """Check if text contains any of our target tickers or company names."""
    text_upper = text.upper()
    found_tickers = []

    # Iterate through tickers and their aliases defined in TICKER_ALIASES
    for ticker, aliases in TICKER_ALIASES.items():
        for alias in aliases:
            pattern = r'\b' + re.escape(alias) + r'\b'
            if re.search(pattern, text_upper):
                if ticker not in found_tickers:
                    found_tickers.append(ticker)
                break

    return found_tickers


def analyze_sentiment(text: str, analyzer) -> Dict[str, Any]:
    """Analyze sentiment of text using VADER."""
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
    """Extract key topics from text using simple keyword matching."""
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
    """Scrape posts from a specific subreddit using PRAW."""
    logger.info(f"Scraping r/{subreddit_name}...")

    subreddit = reddit_client.subreddit(subreddit_name)
    posts_data = []
    seen_post_ids = set()

    try:
        # Get both hot and new posts for better coverage
        for post_type, post_generator in [('hot', subreddit.hot(limit=limit)),
                                          ('new', subreddit.new(limit=limit))]:
            for post in post_generator:
                # Skip duplicates
                if post.id in seen_post_ids:
                    continue
                seen_post_ids.add(post.id)

                # Check if post is from the past month
                post_date = datetime.fromtimestamp(post.created_utc)
                if post_date < since_date:
                    continue

                # Combine title and selftext
                full_text = f"{post.title}\n{post.selftext or ''}"

                # Check if post mentions any of our tickers
                mentioned_tickers = contains_ticker(full_text)
                if not mentioned_tickers:
                    continue

                # Analyze sentiment
                sentiment_data = analyze_sentiment(full_text, analyzer)

                # Extract topics
                topics = extract_topics(full_text)

                # Get top comments (up to 5)
                comments_data = []
                post.comments.replace_more(limit=0)  # Don't load more comments
                for comment in post.comments[:5]:
                    if hasattr(comment, 'body') and comment.body != '[deleted]':
                        comment_tickers = contains_ticker(comment.body)
                        if comment_tickers:
                            comment_sentiment = analyze_sentiment(comment.body, analyzer)
                            comments_data.append({
                                'id': comment.id,
                                'body': comment.body[:500],  # Limit length
                                'score': comment.score,
                                'created_utc': comment.created_utc,
                                'mentioned_tickers': comment_tickers,
                                'sentiment': comment_sentiment['sentiment'],
                                'compound_score': comment_sentiment['compound_score']
                            })

                # Store post data
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

                # Rate limiting
                time.sleep(1)

    except Exception as e:
        logger.error(f"Error scraping r/{subreddit_name}: {e}")

    return posts_data


def scrape_reddit_with_praw() -> List[Dict[str, Any]]:
    """Scrape Reddit posts using PRAW API with authentication."""
    if not REDDIT_AVAILABLE:
        logger.warning("Reddit scraping not available (praw not installed). Skipping...")
        return []

    logger.info("=" * 60)
    logger.info("SCRAPING REDDIT WITH PRAW API")
    logger.info("=" * 60)
    logger.info(f"Target tickers: {', '.join(sorted(TARGET_TICKERS))}")
    logger.info(f"Subreddits: {', '.join(SUBREDDITS)}")
    logger.info(f"Time range: Past {DAYS_BACK} days")

    # Initialize Reddit API client
    try:
        reddit_client = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID', "9RrzkLg9kN06g-kpti2ncw"),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET', "OH0pyFbl8T2ykN0IeAC1m5uNUu287A"),
            user_agent=os.getenv('REDDIT_USER_AGENT', "FinancialAgent/1.0 by u/Feeling-Berry5335")
        )

        # Test authentication
        logger.info(f"Authenticated as: {reddit_client.user.me() if reddit_client.user.me() else 'Anonymous (Read-only)'}")
    except Exception as e:
        logger.error(f"Failed to initialize Reddit client: {e}")
        logger.info("Falling back to RSS scraping...")
        return []

    analyzer = SentimentIntensityAnalyzer()
    # Fetch posts from the past DAYS_BACK day(s)
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
    """Fetch Reddit data and save to files."""

    def load_fallback_posts() -> List[Dict[str, Any]]:
        """Load pre-generated Reddit dataset if live scrape fails."""
        for candidate in FALLBACK_REDDIT_POST_FILES:
            if candidate.exists():
                try:
                    with open(candidate, 'r') as f:
                        data = json.load(f)
                    logger.warning(f"Using fallback Reddit dataset: {candidate}")
                    return data
                except Exception as fallback_error:
                    logger.error(f"Failed to load fallback Reddit file {candidate}: {fallback_error}")
        logger.warning("No fallback Reddit dataset found.")
        return []

    posts_data = scrape_reddit_with_praw()

    if not posts_data:
        logger.warning("No Reddit posts found via live scrape. Attempting fallback dataset...")
        posts_data = load_fallback_posts()
        if not posts_data:
            logger.warning("Skipping Reddit data save because no data is available.")
            return

    # Timestamp and datetime string for file naming
    now = datetime.now()
    fetch_timestamp = now.isoformat()
    # include hours, minutes, seconds to avoid overwrites
    date_str = now.strftime('%Y%m%d_%H%M%S')
    # Generate per-company combined raw posts + summary
    for ticker in TARGET_TICKERS:
        # Filter posts for this ticker
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
        # Save per-ticker data with timestamp suffix
        ticker_file = os.path.join(
            REDDIT_DATA_DIR,
            f"{ticker}_reddit_posts_{date_str}.json"
        )
        with open(ticker_file, 'w') as f:
            json.dump(result, f, indent=2)
        logger.info(f"✅ Saved Reddit data and summary for {ticker} to {ticker_file}")


# ========== X/TWITTER SCRAPING FUNCTIONS ==========

# Time range for X posts
# Note: X API v2 Basic tier only allows 7 days for search_recent_tweets
# For 6 months, you need Academic Research access
X_DAYS_BACK = 7  # Free tier: 7 days, Academic: up to 6 months


def initialize_x_client():
    """Initialize X/Twitter API client with authentication."""
    if not X_AVAILABLE:
        logger.warning("X/Twitter API not available (tweepy not installed). Skipping...")
        return None

    try:
        # X API v2 credentials
        bearer_token = os.getenv('X_BEARER_TOKEN')
        api_key = os.getenv('X_API_KEY')
        api_secret = os.getenv('X_API_SECRET')
        access_token = os.getenv('X_ACCESS_TOKEN')
        access_token_secret = os.getenv('X_ACCESS_TOKEN_SECRET')

        if not bearer_token and not (api_key and api_secret):
            logger.warning("X API credentials not found in environment variables.")
            logger.info("Please set X_BEARER_TOKEN or (X_API_KEY and X_API_SECRET)")
            return None

        # Initialize client with v2 API
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
    """
    Search X for posts matching the query.

    Args:
        client: Tweepy client instance
        query: Search query string
        max_results: Maximum number of results to return (max 100 per request)

    Returns:
        List of tweet dictionaries with metadata
    """
    if not client:
        return []

    try:
        # Search recent tweets (v2 API)
        tweets = client.search_recent_tweets(
            query=query,
            max_results=min(max_results, 100),
            tweet_fields=['created_at', 'public_metrics', 'author_id', 'lang'],
            expansions=['author_id'],
            user_fields=['username', 'name', 'verified']
        )

        if not tweets.data:
            return []

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
        logger.info("Waiting 15 minutes before retrying...")
        time.sleep(900)  # Wait 15 minutes
        raise  # Let retry mechanism handle it
    except Exception as e:
        logger.error(f"Error searching X: {e}")
        return []


def fetch_x_data_for_company(client, ticker: str, company_name: str, ceo_name: str, analyzer) -> Dict[str, Any]:
    """
    Fetch X posts from official company and CEO accounts from the last 24 hours.

    Args:
        client: Tweepy client instance
        ticker: Stock ticker symbol
        company_name: Company name
        ceo_name: CEO name
        analyzer: VADER sentiment analyzer

    Returns:
        Dictionary with company posts and CEO posts
    """
    logger.info(f"Fetching X data for {ticker} ({company_name})...")

    company_posts = []
    ceo_posts = []

    # Calculate threshold time (X_DAYS_BACK days ago)
    from datetime import timedelta
    now = datetime.now(tz=None)
    threshold_time = now - timedelta(days=X_DAYS_BACK)

    # Get official Twitter handles
    company_handle = COMPANY_X_HANDLES.get(ticker)
    ceo_handle = CEO_X_HANDLES.get(ticker)

    # Search for posts FROM official company account
    if company_handle:
        try:
            # Build query to get posts FROM the official company account
            company_query = f'from:{company_handle} -is:retweet lang:en'

            logger.info(f"  Searching X for posts from @{company_handle}: {company_query}")
            company_results = search_x_posts(client, company_query, max_results=100)

            # Filter posts from last X_DAYS_BACK days
            filtered_results = []
            for post in company_results:
                if post.get('created_at'):
                    # Parse created_at timestamp (ISO format)
                    post_time = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    # Normalize to naive datetime
                    if post_time.tzinfo is not None:
                        post_time = post_time.replace(tzinfo=None)
                    if post_time >= threshold_time:
                        filtered_results.append(post)

            company_results = filtered_results
            logger.info(f"  Found {len(company_results)} posts from @{company_handle} in last 24 hours")

            if company_results:
                # Analyze sentiment for each post
                for post in company_results:
                    sentiment_data = analyze_sentiment(post['text'], analyzer)
                    post['sentiment'] = sentiment_data['sentiment']
                    post['compound_score'] = sentiment_data['compound_score']
                    post['positive_score'] = sentiment_data['positive_score']
                    post['negative_score'] = sentiment_data['negative_score']
                    post['topics'] = extract_topics(post['text'])

                company_posts = company_results
                logger.info(f"  ✅ Found {len(company_posts)} posts from official @{company_handle} account")
            else:
                logger.info(f"  No posts from @{company_handle} in last 24 hours")

            # Rate limiting
            time.sleep(3)

        except Exception as e:
            logger.error(f"Error fetching posts from @{company_handle}: {e}")
            import traceback
            traceback.print_exc()
    else:
        logger.info(f"  No official X handle configured for {ticker}")

    # Search for posts FROM official CEO account
    if ceo_handle:
        try:
            # Build query to get posts FROM the official CEO account
            ceo_query = f'from:{ceo_handle} -is:retweet lang:en'

            logger.info(f"  Searching X for posts from CEO @{ceo_handle}: {ceo_query}")
            ceo_results = search_x_posts(client, ceo_query, max_results=100)

            # Filter posts from last 24 hours
            filtered_results = []
            for post in ceo_results:
                if post.get('created_at'):
                    # Parse created_at timestamp (ISO format)
                    post_time = datetime.fromisoformat(post['created_at'].replace('Z', '+00:00'))
                    # Normalize to naive datetime
                    if post_time.tzinfo is not None:
                        post_time = post_time.replace(tzinfo=None)
                    if post_time >= threshold_time:
                        filtered_results.append(post)

            ceo_results = filtered_results
            logger.info(f"  Found {len(ceo_results)} posts from CEO @{ceo_handle} in last 24 hours")

            if ceo_results:
                # Analyze sentiment for each post
                for post in ceo_results:
                    sentiment_data = analyze_sentiment(post['text'], analyzer)
                    post['sentiment'] = sentiment_data['sentiment']
                    post['compound_score'] = sentiment_data['compound_score']
                    post['positive_score'] = sentiment_data['positive_score']
                    post['negative_score'] = sentiment_data['negative_score']
                    post['topics'] = extract_topics(post['text'])

                ceo_posts = ceo_results
                logger.info(f"  ✅ Found {len(ceo_posts)} posts from CEO @{ceo_handle}")
            else:
                logger.info(f"  No posts from CEO @{ceo_handle} in last 24 hours")

            # Rate limiting
            time.sleep(3)

        except Exception as e:
            logger.error(f"Error fetching posts from CEO @{ceo_handle}: {e}")
            import traceback
            traceback.print_exc()
    else:
        logger.info(f"  No official CEO X handle configured for {ticker}")

    # Compute overall bullish score (1 to 10) from average compound sentiment
    all_scores = [post.get('compound_score', 0) for post in (company_posts + ceo_posts)]
    if all_scores:
        avg_compound = sum(all_scores) / len(all_scores)
        # Map avg_compound (-1..1) to bullish_score (1..10)
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
        'total_company_posts': len(company_posts),
        'total_ceo_posts': len(ceo_posts),
        'bullish_score': bullish_score,
        'average_sentiment': sum(all_scores) / len(all_scores) if all_scores else None,
        'overall_sentiment': 'bullish' if bullish_score and bullish_score > 5 else 'bearish' if bullish_score else 'neutral',
        'fetch_timestamp': datetime.now().isoformat(),
        'time_range_hours': 24,
        'data_source': 'Official company and CEO X/Twitter accounts only'
    }


def fetch_x_data():
    """Fetch X data for all companies and save to files."""
    if not X_AVAILABLE:
        logger.warning("X/Twitter scraping not available (tweepy not installed). Skipping...")
        return

    logger.info("=" * 60)
    logger.info("FETCHING X/TWITTER DATA")
    logger.info("=" * 60)
    logger.info(f"Time range: Past {X_DAYS_BACK} days (X API Basic tier limitation)")

    # Initialize X client
    client = initialize_x_client()
    if not client:
        logger.warning("X client not available. Skipping X data collection.")
        return

    # Timestamp for file naming
    now = datetime.now()
    date_str = now.strftime('%Y%m%d_%H%M%S')

    # Initialize sentiment analyzer
    analyzer = SentimentIntensityAnalyzer()

    # Load companies data
    if not os.path.exists(COMPANIES_CSV_PATH):
        logger.error(f"Companies file not found: {COMPANIES_CSV_PATH}")
        return

    companies_df = pd.read_csv(COMPANIES_CSV_PATH)
    logger.info(f"Loaded {len(companies_df)} companies")

    # Load CEO data from most recent CEO report
    ceo_data_map = {}
    ceo_reports = sorted(Path(CEO_REPORTS_DIR).glob("ceo_summary_*.csv"))
    if ceo_reports:
        latest_ceo_report = ceo_reports[-1]
        logger.info(f"Loading CEO data from {latest_ceo_report}")
        ceo_df = pd.read_csv(latest_ceo_report)
        for _, row in ceo_df.iterrows():
            ceo_data_map[row['ticker']] = row['ceo_name']
    else:
        logger.warning("No CEO reports found. Will search without CEO names.")

    # Fetch X data for each company
    all_results = []
    total_companies = len(companies_df)

    for index, row in companies_df.iterrows():
        ticker = row['ticker']
        company_name = row['company_name']
        ceo_name = ceo_data_map.get(ticker, "Not found")

        logger.info(f"Processing {index + 1}/{total_companies}: {ticker}")

        try:
            result = fetch_x_data_for_company(client, ticker, company_name, ceo_name, analyzer)
            all_results.append(result)
            # Save combined raw data and summary per company with timestamp
            company_file = os.path.join(X_DATA_DIR, f"{ticker}_x_posts_{date_str}.json")
            with open(company_file, 'w') as f:
                json.dump(result, f, indent=2)
            logger.info(f"✅ Saved X data and summary for {ticker} to {company_file}")
            # Rate limiting between companies
            time.sleep(10)

        except Exception as e:
            logger.error(f"Failed to fetch X data for {ticker}: {e}")
            continue



# ========== SECTOR METRICS CALCULATION FUNCTIONS ==========

def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """Calculate RSI (Relative Strength Index) for a price series."""
    if len(prices) < period + 1:
        return None

    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None


def calculate_macd(prices: pd.Series) -> Dict[str, float]:
    """Calculate MACD (Moving Average Convergence Divergence)."""
    if len(prices) < 26:
        return {'macd': None, 'signal': None, 'histogram': None}

    exp1 = prices.ewm(span=12, adjust=False).mean()
    exp2 = prices.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal

    return {
        'macd': macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else None,
        'signal': signal.iloc[-1] if not pd.isna(signal.iloc[-1]) else None,
        'histogram': histogram.iloc[-1] if not pd.isna(histogram.iloc[-1]) else None
    }


def calculate_cagr(prices: pd.Series) -> float:
    """Calculate CAGR (Compound Annual Growth Rate)."""
    if len(prices) < 2:
        return None

    start_value = prices.iloc[0]
    end_value = prices.iloc[-1]

    if start_value <= 0 or end_value <= 0:
        return None

    # Calculate years (approximate based on days)
    years = len(prices) / 252  # Trading days per year

    if years <= 0:
        return None

    cagr = (pow(end_value / start_value, 1 / years) - 1) * 100
    return cagr


def calculate_volatility(prices: pd.Series, period: int = 252) -> float:
    """Calculate annualized volatility (standard deviation of returns)."""
    if len(prices) < 2:
        return None

    returns = prices.pct_change().dropna()
    if len(returns) == 0:
        return None

    # Annualized volatility
    volatility = returns.std() * np.sqrt(period)
    return volatility * 100  # Return as percentage


def calculate_beta(prices: pd.Series, market_prices: pd.Series) -> float:
    """Calculate beta (systematic risk relative to market)."""
    if len(prices) < 2 or len(market_prices) < 2:
        return None

    # Align the series by index
    aligned = pd.DataFrame({'stock': prices, 'market': market_prices}).dropna()

    if len(aligned) < 2:
        return None

    stock_returns = aligned['stock'].pct_change().dropna()
    market_returns = aligned['market'].pct_change().dropna()

    if len(stock_returns) < 2 or len(market_returns) < 2:
        return None

    # Calculate covariance and variance
    covariance = np.cov(stock_returns, market_returns)[0, 1]
    market_variance = np.var(market_returns)

    if market_variance == 0:
        return None

    beta = covariance / market_variance
    return beta


def calculate_sharpe_ratio(prices: pd.Series, risk_free_rate: float = 0.04) -> float:
    """Calculate Sharpe ratio (risk-adjusted returns)."""
    if len(prices) < 2:
        return None

    returns = prices.pct_change().dropna()
    if len(returns) == 0:
        return None

    # Annualized return
    total_return = (prices.iloc[-1] / prices.iloc[0]) - 1
    years = len(prices) / 252
    annualized_return = (pow(1 + total_return, 1 / years) - 1) if years > 0 else 0

    # Annualized volatility
    volatility = returns.std() * np.sqrt(252)

    if volatility == 0:
        return None

    sharpe = (annualized_return - risk_free_rate) / volatility
    return sharpe


def calculate_momentum_score(prices: pd.Series) -> Dict[str, float]:
    """Calculate momentum indicators for different time periods."""
    if len(prices) < 2:
        return {'1m': None, '3m': None, '6m': None, '1y': None}

    momentum = {}

    # 1-month momentum (last 21 trading days)
    if len(prices) >= 21:
        momentum['1m'] = ((prices.iloc[-1] / prices.iloc[-21]) - 1) * 100
    else:
        momentum['1m'] = None

    # 3-month momentum (last 63 trading days)
    if len(prices) >= 63:
        momentum['3m'] = ((prices.iloc[-1] / prices.iloc[-63]) - 1) * 100
    else:
        momentum['3m'] = None

    # 6-month momentum (last 126 trading days)
    if len(prices) >= 126:
        momentum['6m'] = ((prices.iloc[-1] / prices.iloc[-126]) - 1) * 100
    else:
        momentum['6m'] = None

    # 1-year momentum
    momentum['1y'] = ((prices.iloc[-1] / prices.iloc[0]) - 1) * 100

    return momentum


def get_company_metrics(ticker: str, market_prices: Optional[pd.Series] = None) -> Dict[str, Any]:
    """
    Fetch comprehensive metrics for a single company.

    Args:
        ticker: Stock ticker symbol
        market_prices: Optional market benchmark prices (e.g., SPY) for beta calculation

    Returns:
        Dictionary with financial and technical metrics
    """
    metrics = {
        'ticker': ticker,
        'sector': None,
        'industry': None,
        'market_cap': None,
        'revenue': None,
        'gross_margin': None,
        'net_margin': None,
        'free_cash_flow': None,
        'eps': None,
        'pe_ratio': None,
        'ps_ratio': None,
        'pb_ratio': None,
        'rsi': None,
        'macd': None,
        'macd_signal': None,
        'macd_histogram': None,
        'cagr': None,
        'volatility': None,
        'beta': None,
        'sharpe_ratio': None,
        'momentum_1m': None,
        'momentum_3m': None,
        'momentum_6m': None,
        'momentum_1y': None,
        'roe': None,
        'roa': None,
        'roic': None,
        'debt_to_equity': None,
        'current_ratio': None,
        'quick_ratio': None,
        'interest_coverage': None,
        'error': None
    }

    try:
        # Fetch company info
        stock = yf.Ticker(ticker)
        info = stock.info

        # Basic info
        metrics['sector'] = info.get('sector', 'Unknown')
        metrics['industry'] = info.get('industry', 'Unknown')
        metrics['market_cap'] = info.get('marketCap')

        # Valuation ratios
        metrics['pe_ratio'] = info.get('trailingPE') or info.get('forwardPE')
        metrics['ps_ratio'] = info.get('priceToSalesTrailing12Months')
        metrics['pb_ratio'] = info.get('priceToBook')

        # EPS
        metrics['eps'] = info.get('trailingEps') or info.get('forwardEps')

        # Efficiency ratios from info
        metrics['roe'] = info.get('returnOnEquity')
        if metrics['roe']:
            metrics['roe'] = metrics['roe'] * 100  # Convert to percentage
        metrics['roa'] = info.get('returnOnAssets')
        if metrics['roa']:
            metrics['roa'] = metrics['roa'] * 100  # Convert to percentage

        # Debt metrics from info
        metrics['debt_to_equity'] = info.get('debtToEquity')
        metrics['current_ratio'] = info.get('currentRatio')
        metrics['quick_ratio'] = info.get('quickRatio')

        # Get financial statements
        financials = stock.financials
        if not financials.empty:
            # Revenue (Total Revenue)
            if 'Total Revenue' in financials.index:
                metrics['revenue'] = financials.loc['Total Revenue'].iloc[0]

            # Gross Margin
            if 'Gross Profit' in financials.index and 'Total Revenue' in financials.index:
                gross_profit = financials.loc['Gross Profit'].iloc[0]
                revenue = financials.loc['Total Revenue'].iloc[0]
                if revenue and revenue != 0:
                    metrics['gross_margin'] = (gross_profit / revenue) * 100

            # Net Margin
            if 'Net Income' in financials.index and 'Total Revenue' in financials.index:
                net_income = financials.loc['Net Income'].iloc[0]
                revenue = financials.loc['Total Revenue'].iloc[0]
                if revenue and revenue != 0:
                    metrics['net_margin'] = (net_income / revenue) * 100

        # Calculate interest coverage ratio
        if not financials.empty:
            if 'EBIT' in financials.index and 'Interest Expense' in financials.index:
                ebit = financials.loc['EBIT'].iloc[0]
                interest_expense = financials.loc['Interest Expense'].iloc[0]
                if interest_expense and interest_expense != 0:
                    metrics['interest_coverage'] = ebit / abs(interest_expense)

        # Get balance sheet for ROIC calculation
        balance_sheet = stock.balance_sheet
        if not balance_sheet.empty and not financials.empty:
            # ROIC = NOPAT / Invested Capital
            # NOPAT = Net Income + Interest Expense * (1 - Tax Rate)
            # Invested Capital = Total Debt + Total Equity
            try:
                if 'Net Income' in financials.index:
                    net_income = financials.loc['Net Income'].iloc[0]
                    interest_expense = financials.loc['Interest Expense'].iloc[0] if 'Interest Expense' in financials.index else 0
                    tax_rate = 0.21  # Approximate corporate tax rate

                    nopat = net_income + (abs(interest_expense) * (1 - tax_rate)) if interest_expense else net_income

                    # Get invested capital
                    total_debt = balance_sheet.loc['Total Debt'].iloc[0] if 'Total Debt' in balance_sheet.index else 0
                    total_equity = balance_sheet.loc['Total Equity Gross Minority Interest'].iloc[0] if 'Total Equity Gross Minority Interest' in balance_sheet.index else None
                    if total_equity is None:
                        total_equity = balance_sheet.loc['Stockholders Equity'].iloc[0] if 'Stockholders Equity' in balance_sheet.index else 0

                    invested_capital = total_debt + total_equity if total_equity else None

                    if invested_capital and invested_capital != 0:
                        metrics['roic'] = (nopat / invested_capital) * 100
            except Exception as e:
                logger.debug(f"Could not calculate ROIC for {ticker}: {e}")

        # Get cash flow statement
        cash_flow = stock.cashflow
        if not cash_flow.empty:
            # Free Cash Flow
            if 'Free Cash Flow' in cash_flow.index:
                metrics['free_cash_flow'] = cash_flow.loc['Free Cash Flow'].iloc[0]
            elif 'Operating Cash Flow' in cash_flow.index and 'Capital Expenditure' in cash_flow.index:
                ocf = cash_flow.loc['Operating Cash Flow'].iloc[0]
                capex = cash_flow.loc['Capital Expenditure'].iloc[0]
                if ocf and capex:
                    metrics['free_cash_flow'] = ocf + capex  # capex is negative

        # Get price history for technical indicators
        hist = stock.history(period="1y")
        if not hist.empty and 'Close' in hist.columns:
            close_prices = hist['Close']

            # RSI
            metrics['rsi'] = calculate_rsi(close_prices)

            # MACD
            macd_data = calculate_macd(close_prices)
            metrics['macd'] = macd_data['macd']
            metrics['macd_signal'] = macd_data['signal']
            metrics['macd_histogram'] = macd_data['histogram']

            # CAGR
            metrics['cagr'] = calculate_cagr(close_prices)

            # Volatility
            metrics['volatility'] = calculate_volatility(close_prices)

            # Beta (if market prices provided)
            if market_prices is not None:
                metrics['beta'] = calculate_beta(close_prices, market_prices)

            # Sharpe Ratio
            metrics['sharpe_ratio'] = calculate_sharpe_ratio(close_prices)

            # Momentum scores
            momentum = calculate_momentum_score(close_prices)
            metrics['momentum_1m'] = momentum['1m']
            metrics['momentum_3m'] = momentum['3m']
            metrics['momentum_6m'] = momentum['6m']
            metrics['momentum_1y'] = momentum['1y']

        return metrics

    except Exception as e:
        logger.warning(f"Error fetching metrics for {ticker}: {e}")
        metrics['error'] = str(e)
        return metrics


def get_company_news(ticker: str, days: Optional[int] = None) -> List[Dict[str, Any]]:
    """
    Fetch recent news articles for a company using yfinance.

    Args:
        ticker: Stock ticker symbol
        days: Only return articles from the past N days (default: None, returns all available)

    Returns:
        List of news articles with title, publisher, link, and publish time
    """
    try:
        stock = yf.Ticker(ticker)
        news = stock.news

        if not news:
            logger.warning(f"No news found for {ticker}")
            return []

        # Calculate date cutoff if days filter is specified
        date_cutoff = None
        if days is not None:
            date_cutoff = datetime.now() - timedelta(days=days)

        # Format and clean news data - fetch ALL available articles
        formatted_news = []
        for article in news:
            # Handle new yfinance structure where content is nested
            content = article.get('content', article)

            # Extract provider information
            provider = content.get('provider', {})
            publisher_name = provider.get('displayName', 'N/A') if isinstance(provider, dict) else 'N/A'

            # Extract canonical URL
            canonical_url = content.get('canonicalUrl', {})
            article_url = canonical_url.get('url', 'N/A') if isinstance(canonical_url, dict) else 'N/A'

            # Extract thumbnail
            thumbnail_data = content.get('thumbnail', {})
            thumbnail_url = None
            if isinstance(thumbnail_data, dict):
                resolutions = thumbnail_data.get('resolutions', [])
                if resolutions and isinstance(resolutions, list):
                    thumbnail_url = resolutions[0].get('url') if len(resolutions) > 0 else None

            # Parse publish date
            pub_date = content.get('pubDate')
            publish_time = pub_date if pub_date else None

            # Apply date filter if specified
            if date_cutoff and publish_time:
                try:
                    # Parse ISO format date string
                    article_date = datetime.fromisoformat(publish_time.replace('Z', '+00:00'))
                    # Make date_cutoff timezone-aware if article_date is timezone-aware
                    if article_date.tzinfo is not None:
                        from datetime import timezone
                        date_cutoff_aware = date_cutoff.replace(tzinfo=timezone.utc)
                        if article_date < date_cutoff_aware:
                            continue  # Skip articles older than cutoff
                    else:
                        if article_date.replace(tzinfo=None) < date_cutoff:
                            continue
                except (ValueError, AttributeError):
                    # If date parsing fails, include the article anyway
                    pass

            formatted_article = {
                'title': content.get('title', 'N/A'),
                'publisher': publisher_name,
                'link': article_url,
                'publish_time': publish_time,
                'content_type': content.get('contentType', 'N/A'),
                'summary': content.get('summary', ''),
                'thumbnail': thumbnail_url
            }
            formatted_news.append(formatted_article)

        if days:
            logger.info(f"Fetched {len(formatted_news)} news articles for {ticker} from the past {days} days (out of {len(news)} total available)")
        else:
            logger.info(f"Fetched {len(formatted_news)} news articles for {ticker}")
        return formatted_news

    except Exception as e:
        logger.error(f"Error fetching news for {ticker}: {e}")
        return []


def filter_news_with_llm(ticker: str, articles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Filter news articles using Gemini LLM to keep only factual company-related news.
    Excludes subjective opinions and articles not directly related to the company.

    Args:
        ticker: Stock ticker symbol
        articles: List of news articles to filter

    Returns:
        Filtered list of news articles
    """
    if not GEMINI_AVAILABLE:
        logger.warning("Google Gemini not available. Returning all articles without filtering.")
        return articles

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Returning all articles without filtering.")
        return articles

    if not articles:
        return articles

    try:
        # Configure Gemini API
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')
        filtered_articles = []

        for article in articles:
            title = article.get('title', '')
            summary = article.get('summary', '')
            publisher = article.get('publisher', '')

            # Create prompt for Gemini
            prompt = f"""You are an expert in news analysis. Your job is to identify news that is factual. Skip any articles that express opinions.

Analyze this article about {ticker}:

Article Title: {title}
Publisher: {publisher}
Summary: {summary}

STRICT CRITERIA - The article is FACTUAL only if it reports:
- Concrete company actions (product launches, acquisitions, partnerships, layoffs)
- Financial results (earnings reports, revenue, guidance)
- Executive changes (CEO appointments, board changes)
- Regulatory actions (lawsuits, investigations, regulatory filings)
- Operational events (factory openings, supply chain disruptions)

IMMEDIATELY REJECT if the article contains:
- Investment recommendations ("should you buy", "best stock", "top pick")
- Price predictions ("stock could reach", "target price", "will rally")
- Subjective assessments ("undervalued", "overvalued", "opportunity")
- Analyst opinions or ratings changes
- Comparative analysis ("better than", "vs competitor")
- Questions in the title (often indicates opinion pieces)
- Words like "could", "should", "might", "rally", "continue", "opportunity"

Respond with ONLY "YES" if purely factual, or "NO" if it contains any opinions.
Then on a new line, provide a brief 1-sentence reason."""

            response = model.generate_content(
                prompt,
                generation_config=genai.types.GenerationConfig(
                    max_output_tokens=100,
                    temperature=0.3,
                )
            )

            response_text = response.text.strip()
            lines = response_text.split('\n')
            decision = lines[0].strip().upper()

            if decision == "YES":
                # Add filter reason to article metadata
                reason = lines[1] if len(lines) > 1 else "Meets factual news criteria"
                article['filter_reason'] = reason
                article['filtered_by_llm'] = True
                filtered_articles.append(article)
                logger.debug(f"✓ Included: {title[:60]}... - {reason}")
            else:
                reason = lines[1] if len(lines) > 1 else "Does not meet criteria"
                logger.debug(f"✗ Excluded: {title[:60]}... - {reason}")

            # Rate limiting
            time.sleep(0.5)

        logger.info(f"Filtered {len(articles)} articles down to {len(filtered_articles)} for {ticker}")
        return filtered_articles

    except Exception as e:
        logger.error(f"Error filtering news with LLM: {e}")
        logger.warning("Returning all articles without filtering due to error.")
        return articles


def fetch_news_data(ticker: str, days: int = 1, filter_with_llm: bool = True) -> Dict[str, Any]:
    """
    Fetch latest news for a ticker and save to file.

    Uses LLM to filter out subjective/opinion articles and keep only factual company news.

    Args:
        ticker: Stock ticker symbol
        days: Number of days of news to fetch (default: 1)
        filter_with_llm: Whether to filter articles using LLM (default: True)

    Returns:
        Dictionary containing news articles and metadata
    """
    logger.info(f"Fetching news for {ticker} (past {days} day(s))...")

    # Fetch news using existing function
    news_articles = get_company_news(ticker, days=days)
    total_articles_fetched = len(news_articles)

    # Filter articles using LLM if enabled
    if filter_with_llm and news_articles:
        logger.info(f"Filtering {total_articles_fetched} articles using LLM...")
        news_articles = filter_news_with_llm(ticker, news_articles)

    # Timestamp for file naming
    now = datetime.now()
    fetch_timestamp = now.isoformat()
    date_str = now.strftime('%Y%m%d_%H%M%S')

    total_articles = len(news_articles)

    # Prepare result
    result = {
        'ticker': ticker,
        'articles': news_articles,
        'total_articles': total_articles,
        'total_articles_before_filter': total_articles_fetched,
        'filtered_with_llm': filter_with_llm,
        'days_range': days,
        'fetch_timestamp': fetch_timestamp
    }

    # Save to file
    news_file = os.path.join(
        NEWS_DATA_DIR,
        f"{ticker}_news_{date_str}.json"
    )

    with open(news_file, 'w') as f:
        json.dump(result, f, indent=2)

    if filter_with_llm:
        logger.info(f"✅ Saved {total_articles} filtered news articles for {ticker} (from {total_articles_fetched} total) to {news_file}")
    else:
        logger.info(f"✅ Saved {total_articles} news articles for {ticker} to {news_file}")

    return result


def fetch_all_news(tickers: List[str] = None, days: int = 1, filter_with_llm: bool = True) -> Dict[str, Any]:
    """
    Fetch news for all target tickers.

    Args:
        tickers: List of ticker symbols (default: TARGET_TICKERS)
        days: Number of days of news to fetch (default: 1)
        filter_with_llm: Whether to filter articles using LLM (default: True)

    Returns:
        Dictionary with results for each ticker
    """
    if tickers is None:
        tickers = TARGET_TICKERS

    logger.info("=" * 60)
    logger.info(f"FETCHING NEWS FOR {len(tickers)} TICKERS")
    if filter_with_llm:
        logger.info("LLM filtering: ENABLED (factual company news only)")
    else:
        logger.info("LLM filtering: DISABLED (all articles)")
    logger.info("=" * 60)

    results = {
        'tickers_processed': [],
        'total_articles': 0,
        'total_articles_before_filter': 0,
        'errors': []
    }

    for ticker in tickers:
        try:
            result = fetch_news_data(ticker, days=days, filter_with_llm=filter_with_llm)
            results['tickers_processed'].append(ticker)
            results['total_articles'] += result['total_articles']
            results['total_articles_before_filter'] += result.get('total_articles_before_filter', result['total_articles'])
        except Exception as e:
            logger.error(f"Error fetching news for {ticker}: {e}")
            results['errors'].append({'ticker': ticker, 'error': str(e)})

    logger.info("")
    logger.info("=" * 60)
    logger.info("NEWS FETCH SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Tickers processed: {len(results['tickers_processed'])}/{len(tickers)}")
    if filter_with_llm:
        logger.info(f"Total articles after filtering: {results['total_articles']}")
        logger.info(f"Total articles before filtering: {results['total_articles_before_filter']}")
        logger.info(f"Filter rate: {100 * (1 - results['total_articles'] / max(results['total_articles_before_filter'], 1)):.1f}% excluded")
    else:
        logger.info(f"Total articles fetched: {results['total_articles']}")
    logger.info(f"Errors: {len(results['errors'])}")
    logger.info("=" * 60)

    return results

def interpret_news_with_llm(ticker: str, news_articles: List[Dict[str, Any]]) -> str:
    """
    Generate comprehensive news interpretation using Gemini 2.5 Flash LLM.

    Considers sector trends, company fundamentals, market conditions, and provides
    BUY/HOLD/SELL recommendation.

    Args:
        ticker: Stock ticker symbol
        news_articles: List of news articles to interpret

    Returns:
        Interpretation text for investors
    """
    if not GEMINI_AVAILABLE:
        logger.warning("Google Gemini not available. Cannot generate news interpretation.")
        return "News interpretation unavailable - Google Generative AI not configured."

    api_key = os.getenv('GEMINI_API_KEY')
    if not api_key:
        logger.warning("GEMINI_API_KEY not set. Cannot generate news interpretation.")
        return "News interpretation unavailable - Gemini API key not configured."

    if not news_articles:
        return f"No recent news available for {ticker}."

    try:
        # Get company information
        stock = yf.Ticker(ticker)
        info = stock.info
        sector = info.get('sector', 'Unknown')
        industry = info.get('industry', 'Unknown')

        # Get latest sector metrics if available
        sector_metrics_files = sorted([f for f in os.listdir(SECTOR_METRICS_DIR) if f.startswith('sector_metrics_')])
        sector_context = "Sector metrics not available."
        if sector_metrics_files:
            latest_sector_file = os.path.join(SECTOR_METRICS_DIR, sector_metrics_files[-1])
            with open(latest_sector_file, 'r') as f:
                sector_data = json.load(f)
                if sector in sector_data.get('sectors', {}):
                    sector_info = sector_data['sectors'][sector]
                    sector_context = f"Sector: {sector}, Quality Score: {sector_info.get('quality_score', 'N/A'):.1f}/100, " \
                                   f"3M Momentum: {sector_info.get('avg_momentum_3m', 'N/A'):.1f}%, " \
                                   f"ROE: {sector_info.get('avg_roe', 'N/A'):.1f}%"

        # Get latest company metrics
        company_metrics_files = sorted([f for f in os.listdir(SECTOR_METRICS_DIR) if f.startswith('company_metrics_')])
        company_context = "Company fundamentals not available."
        if company_metrics_files:
            latest_company_file = os.path.join(SECTOR_METRICS_DIR, company_metrics_files[-1])
            with open(latest_company_file, 'r') as f:
                company_data = json.load(f)
                company_metrics = next((c for c in company_data if c['ticker'] == ticker), None)
                if company_metrics:
                    company_context = f"P/E: {company_metrics.get('pe_ratio', 'N/A')}, " \
                                    f"ROE: {company_metrics.get('roe', 'N/A'):.1f}%, " \
                                    f"3M Return: {company_metrics.get('momentum_3m', 'N/A'):.1f}%, " \
                                    f"Volatility: {company_metrics.get('volatility', 'N/A'):.1f}%"

        # Get market index data (NASDAQ)
        try:
            nasdaq = yf.Ticker("^IXIC")
            nasdaq_hist = nasdaq.history(period="1mo")
            nasdaq_change = ((nasdaq_hist['Close'].iloc[-1] / nasdaq_hist['Close'].iloc[0]) - 1) * 100
            market_context = f"NASDAQ 1-month: {nasdaq_change:+.1f}%"
        except:
            market_context = "Market data not available."

        # Compile news summaries
        news_summaries = []
        for i, article in enumerate(news_articles[:5], 1):  # Limit to 5 most recent
            news_summaries.append(f"{i}. {article['title']} ({article['publisher']})")
            if article.get('summary'):
                news_summaries.append(f"   Summary: {article['summary'][:150]}...")

        news_text = "\n".join(news_summaries)

        # Build the Deep Alpha system prompt for Gemini with sector-aware pillar guidance
        prompt = f"""SYSTEM INSTRUCTION:
You are a Deep Alpha Analyst (DAA) applying the full Deep Alpha Stock Evaluation Framework (Pillars A-G). Your objective is to rigorously determine if a recent news event is mere market 'noise' or if it fundamentally alters the company's long-term value, competitive moat, and conviction index. Based on this analysis, you must generate content suitable for a "Latest News & Investment Analysis" card, providing a clear **Rating** and actionable **Key Takeaways**.

**PRIMARY RULE:** You MUST dynamically select the relevant metrics for Pillars A-F based on the specified {sector} from the list below.

--- INPUT DATA ---
COMPANY: {ticker}
SECTOR: {sector} (E.g., Technology, Energy/Defense/Materials, Consumer/Services, Finance, Healthcare)
INDUSTRY: {industry}

NEWS:
{news_text}

CONTEXTUAL DATA:
AI INFRASTRUCTURE LAYER: {ai_layer} (E.g., Compute, Interconnect, Energy, Materials, N/A)
CURRENT CONVICTION QUADRANT: {conviction_quadrant} (E.g., Strategic Compounder, High-Growth Challenger)
COMPANY FUNDAMENTALS: {company_context}
SECTOR METRICS: {sector_context}
MARKET CONDITIONS: {market_context}
TECHNICAL DATA (REQUIRED for Pillar G):
- Current RSI (14-day): {rsi_value}
- 50-day SMA vs. 200-day SMA Position: {sma_position} (E.g., 50 above 200)
- Recent Volume Change (vs 30-day avg): {volume_change}

--- TASK: DEEP ALPHA PILLAR ASSESSMENT (All 7 Pillars) ---
Interpret the news by systematically assessing its impact on the following seven pillars. The model MUST reference the most appropriate metrics for the given sector in its analysis.

ALWAYS weave in the following investigative checks when relevant, citing concrete data where possible:
- Explain why sector growth is accelerating (government policy, national strategy, secular demand) when the industry is in an explosive phase.
- Comment on technological feasibility or pace of innovation driving the thesis.
- Evaluate leverage and liquidity to confirm debt remains manageable under the updated outlook.
- Highlight backlog or committed revenue visibility and whether it is expanding.
- Discuss valuation (P/E, P/S, EV/Sales) across bull/base/bear framing and whether the stock has recently come down from all-time highs.
- Assess leadership credibility, including recent executive commentary or insider selling activity.
- Surface material deals/partnerships/M&A announced alongside the news.
- Note hiring momentum and whether talent deployment matches stated strategy.
- Briefly situate the company inside the ecosystem (what it builds, whom it serves) using company disclosures or website positioning.
- Call out risks (operational, regulatory/tariff, execution) that could derail the scenario.

**1. Pillar A (Fundamentals & Growth):**
* **Tech/AI:** 3-year/5-year **CAGR**, **R&D Intensity**, Forward EPS.
* **Energy/Defense:** Projected Margin on Backlog, CapEx for Resource Expansion, **Contract Length/Stability**.
* **Consumer:** **Same-Store Sales Growth (SSS)**, Inventory Turnover, Marketing ROI.
* **Finance:** **Net Interest Margin (NIM)**, Loan Growth Rate, Return on Equity (ROE).
* **Healthcare:** **Clinical Trial Phase Progression**, Success Rates, Revenue from Blockbusters.

**2. Pillar B (Valuation & Ratios):**
* **Tech/AI:** **PEG Ratio**, Revenue Multiples (P/S, EV/Sales).
* **Energy/Defense:** **P/B (Book Value)**, Free Cash Flow Yield (FCFY), EV/EBITDA.
* **Consumer:** EV/Sales, **Debt/EBITDA** (Debt management).
* **Finance:** **Price-to-Tangible Book Value (P/TBV)**, Loan Loss Reserves vs. NPLs.
* **Healthcare:** P/S, Sum-of-the-parts (SOTP) Valuation based on pipeline NPV.

**3. Pillar C (Competitive Moat):**
* **Tech/AI:** **Ecosystem Lock-in**, **Developer Dependency**, IP Depth.
* **Energy/Defense:** **Resource Independence/Control**, Regulatory/Permitting Barriers to Entry.
* **Consumer:** **Brand Strength/Loyalty**, Supply Chain/Logistical Advantage.
* **Finance:** Scale of Deposit Base, **Regulatory Barriers**, Fee Income vs. Net Interest Income.
* **Healthcare:** **Patent Expiration/Cliffs**, Drug Uniqueness, Manufacturing Scalability.

**4. Pillar D (Strategic Relevance/Policy):**
* **Tech/AI:** **Export Control Exposure**, CHIPS Act/Government Subsidies, China/US Decoupling.
* **Energy/Defense:** **National Security Mandates**, **DOE/DoD Project Flow**, Resource Scarcity.
* **Consumer:** **Interest Rate Sensitivity**, Labor Law changes, Consumer Confidence Index link.
* **Finance:** **Tier 1 Capital Ratio requirements**, Systemically Important Financial Institution (SIFI) regulation, Rate Hike/Cut Policy.
* **Healthcare:** **FDA Approval Timelines/PDUFA Dates**, Healthcare Policy Changes (e.g., pricing legislation).

**5. Pillar E (Demand Visibility):**
* **Tech/AI:** **New Design Wins**, Backlog/Book-to-Bill ratio.
* **Energy/Defense:** **Long-term Contract Signings**, Backlog Stability.
* **Consumer:** **Booking/Reservation Trends**, Same-Store Sales Guidance.
* **Finance:** Loan Application Volume, Mortgage Origination Trends.
* **Healthcare:** Phase 3 Trial Readouts, Commercialization Timelines.

**6. Pillar F (AI Supply Chain Lens):**
* **All Sectors:** Measures the company's current or potential exposure to AI-driven demand/efficiency gains/risks. Focus on **Substitution Risk** from AI.

**7. Pillar G (Technical Analysis):**
* Analyzes the news-driven stock reaction: Overbought/Oversold (RSI), Trend Confirmation/Reversal (SMAs), and supporting **Volume**.

--- REQUIRED OUTPUT ---
Generate the analysis in the **strict JSON format** below. The entire response must be a single JSON object.

```json
{
  "rating_buy_hold_sell": "[BUY/HOLD/SELL]",
  "sentiment_confidence": "[High/Medium/Low]",
  "key_takeaways": [
    {
      "type": "Fundamental Impact (Pillars A/B/E)",
      "summary": "Focus on material changes to growth rates, profitability, or demand visibility metrics."
    },
    {
      "type": "Strategic Moat & Policy Shift (Pillars C/D/F)",
      "summary": "Focus on changes to competitive position, policy tailwinds, or AI/Sector vulnerability."
    },
    {
      "type": "Technical Noise Filter (Pillar G)",
      "summary": "Focus on whether the reaction is exaggerated (RSI/Volume) or a sustained move."
    }
  ],
  "investment_conclusion": {
    "paragraph": "A concise 150-200 word summary for investors. Integrate the impact on 2-3 specific Deep Alpha Pillars (A-F) and state the implied shift in the Scenario Modeling Framework (Bull, Base, or Bear). Explain why the news is *not* noise, or conversely, why it is simply noise.",
    "reasoning_justification": "A 1-2 sentence justification for the rating, explicitly referencing the Conviction Index drivers (Expected CAGR, Moat Strength, and/or Valuation Multiple)."
  },
  "next_step_focus": {
    "title": "Next Step: Monitoring Key Alpha Drivers",
    "monitor_points": [
      "The next earnings report's updated guidance for 5-year CAGR.",
      "Competitor reactions impacting the company's Competitive Moat (Pillar C).",
      "Official government announcements regarding relevant Policy Tailwinds (Pillar D)."
    ]
  }
}
```

"""

        # Configure Gemini API
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Retry logic with exponential backoff
        max_retries = 3
        retry_delay = 2  # seconds

        for attempt in range(max_retries):
            try:
                # Generate content
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=800,
                        temperature=0.7,
                    )
                )

                interpretation = response.text.strip()

                # Validate that we got a meaningful response
                if len(interpretation) < 50:
                    raise ValueError(f"Response too short ({len(interpretation)} chars), likely incomplete")

                logger.info(f"✅ Generated news interpretation for {ticker} using Gemini 2.5 Flash (attempt {attempt + 1})")
                return interpretation

            except Exception as api_error:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {ticker}: {api_error}")

                if attempt < max_retries - 1:
                    import time
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    raise

    except Exception as e:
        logger.error(f"❌ All {max_retries} attempts failed for {ticker}: {e}")
        return f"Error generating interpretation after {max_retries} attempts: {str(e)}"


def save_news_interpretation(ticker: str, news_file_path: str) -> Optional[str]:
    """
    Generate and save news interpretation for a ticker.
    Ensures 1:1 mapping with news file by using exact same timestamp.

    Args:
        ticker: Stock ticker symbol
        news_file_path: Path to the news JSON file

    Returns:
        Path to saved interpretation file, or None if failed
    """
    try:
        # Load news data
        with open(news_file_path, 'r') as f:
            news_data = json.load(f)

        news_articles = news_data.get('articles', [])
        if not news_articles:
            logger.warning(f"No articles found in {news_file_path}")
            return None

        # Check if interpretation already exists
        news_filename = os.path.basename(news_file_path)
        interpretation_filename = news_filename.replace('_news_', '_news_interpretation_')
        interpretation_path = os.path.join(NEWS_INTERPRETATION_DIR, interpretation_filename)

        if os.path.exists(interpretation_path):
            logger.info(f"Interpretation already exists: {interpretation_path}")
            return interpretation_path

        # Generate interpretation
        logger.info(f"Generating news interpretation for {ticker}...")
        interpretation_text = interpret_news_with_llm(ticker, news_articles)

        # Save interpretation with 1:1 mapping to news file
        interpretation_data = {
            'ticker': ticker,
            'interpretation': interpretation_text,
            'news_file': news_filename,
            'news_timestamp': news_data.get('fetch_timestamp'),
            'interpretation_timestamp': datetime.now().isoformat(),
            'num_articles_analyzed': len(news_articles),
            'articles': news_articles  # Include articles for reference
        }

        with open(interpretation_path, 'w') as f:
            json.dump(interpretation_data, f, indent=2)

        logger.info(f"✅ Saved news interpretation to {interpretation_path}")
        return interpretation_path

    except Exception as e:
        logger.error(f"Error saving news interpretation for {ticker}: {e}")
        return None


def get_latest_news_file(ticker: str) -> Optional[str]:
    """
    Get the latest news file for a ticker.

    Args:
        ticker: Stock ticker symbol

    Returns:
        Path to latest news file, or None if not found
    """
    try:
        news_files = sorted([
            f for f in os.listdir(NEWS_DATA_DIR)
            if f.startswith(f"{ticker}_news_") and f.endswith('.json')
        ])

        if news_files:
            return os.path.join(NEWS_DATA_DIR, news_files[-1])
        return None

    except Exception as e:
        logger.error(f"Error finding news file for {ticker}: {e}")
        return None


def ensure_news_interpretations_exist() -> Dict[str, int]:
    """
    Check all news files and ensure interpretations exist for files with articles.
    Regenerates missing interpretations with retry logic.

    Returns:
        Dictionary with stats: {'checked': N, 'generated': M, 'failed': K}
    """
    stats = {'checked': 0, 'generated': 0, 'failed': 0, 'skipped_no_articles': 0}

    try:
        # Get all news files
        news_files = [f for f in os.listdir(NEWS_DATA_DIR) if '_news_' in f and f.endswith('.json')]

        for news_file in news_files:
            stats['checked'] += 1
            news_path = os.path.join(NEWS_DATA_DIR, news_file)

            # Check if interpretation exists
            interpretation_filename = news_file.replace('_news_', '_news_interpretation_')
            interpretation_path = os.path.join(NEWS_INTERPRETATION_DIR, interpretation_filename)

            if os.path.exists(interpretation_path):
                continue  # Interpretation already exists

            # Check if news file has articles
            try:
                with open(news_path, 'r') as f:
                    news_data = json.load(f)

                articles = news_data.get('articles', [])
                if not articles or len(articles) == 0:
                    stats['skipped_no_articles'] += 1
                    continue  # No articles, skip

                # Extract ticker from filename
                ticker = news_file.split('_news_')[0]

                # Generate interpretation
                logger.info(f"📰 Generating missing interpretation for {ticker} ({news_file})...")
                result = save_news_interpretation(ticker, news_path)

                if result:
                    stats['generated'] += 1
                    logger.info(f"✅ Successfully generated interpretation for {ticker}")
                else:
                    stats['failed'] += 1
                    logger.warning(f"❌ Failed to generate interpretation for {ticker}")

                # Rate limit to avoid API throttling
                import time
                time.sleep(1)

            except Exception as e:
                stats['failed'] += 1
                logger.error(f"Error processing {news_file}: {e}")

        logger.info("")
        logger.info("=" * 60)
        logger.info("INTERPRETATION CHECK COMPLETE")
        logger.info("=" * 60)
        logger.info(f"Files checked: {stats['checked']}")
        logger.info(f"Interpretations generated: {stats['generated']}")
        logger.info(f"Files skipped (no articles): {stats['skipped_no_articles']}")
        logger.info(f"Failed: {stats['failed']}")

        return stats

    except Exception as e:
        logger.error(f"Error ensuring interpretations exist: {e}")
        return stats


def aggregate_sector_sentiment() -> Dict[str, Dict[str, Any]]:
    """
    Aggregate sentiment from X/Twitter data by sector.

    Returns:
        Dictionary mapping sectors to sentiment metrics
    """
    logger.info("Aggregating sector sentiment from social media...")

    sector_sentiment = {}

    # Load company-to-sector mapping
    if not os.path.exists(COMPANIES_CSV_PATH):
        logger.warning("Companies file not found, cannot map sentiment to sectors")
        return {}

    companies_df = pd.read_csv(COMPANIES_CSV_PATH)

    # Get company metrics to map tickers to sectors
    ticker_to_sector = {}
    for _, row in companies_df.iterrows():
        ticker = row['ticker']
        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            sector = info.get('sector', 'Unknown')
            if sector and sector != 'Unknown':
                ticker_to_sector[ticker] = sector
        except:
            continue

    # Load X/Twitter data files
    x_data_files = list(Path(X_DATA_DIR).glob("*_x_posts.json"))

    if not x_data_files:
        logger.warning("No X/Twitter data files found")
        return {}

    # Aggregate sentiment by sector
    for x_file in x_data_files:
        try:
            with open(x_file, 'r') as f:
                x_data = json.load(f)

            ticker = x_data.get('ticker')
            sector = ticker_to_sector.get(ticker)

            if not sector:
                continue

            if sector not in sector_sentiment:
                sector_sentiment[sector] = {
                    'total_posts': 0,
                    'company_posts': 0,
                    'ceo_posts': 0,
                    'bullish_count': 0,
                    'bearish_count': 0,
                    'neutral_count': 0,
                    'avg_compound_score': [],
                    'companies': []
                }

            sector_sentiment[sector]['companies'].append(ticker)
            sector_sentiment[sector]['total_posts'] += x_data.get('total_company_posts', 0) + x_data.get('total_ceo_posts', 0)
            sector_sentiment[sector]['company_posts'] += x_data.get('total_company_posts', 0)
            sector_sentiment[sector]['ceo_posts'] += x_data.get('total_ceo_posts', 0)

            # Aggregate sentiment from company posts
            for post in x_data.get('company_posts', []):
                sentiment = post.get('sentiment', 'neutral')
                if sentiment == 'bullish':
                    sector_sentiment[sector]['bullish_count'] += 1
                elif sentiment == 'bearish':
                    sector_sentiment[sector]['bearish_count'] += 1
                else:
                    sector_sentiment[sector]['neutral_count'] += 1

                if 'compound_score' in post:
                    sector_sentiment[sector]['avg_compound_score'].append(post['compound_score'])

            # Aggregate sentiment from CEO posts
            for post in x_data.get('ceo_posts', []):
                sentiment = post.get('sentiment', 'neutral')
                if sentiment == 'bullish':
                    sector_sentiment[sector]['bullish_count'] += 1
                elif sentiment == 'bearish':
                    sector_sentiment[sector]['bearish_count'] += 1
                else:
                    sector_sentiment[sector]['neutral_count'] += 1

                if 'compound_score' in post:
                    sector_sentiment[sector]['avg_compound_score'].append(post['compound_score'])

        except Exception as e:
            logger.debug(f"Error processing {x_file}: {e}")
            continue

    # Calculate average compound scores and sentiment ratios
    for sector, data in sector_sentiment.items():
        if data['avg_compound_score']:
            data['avg_compound_score'] = sum(data['avg_compound_score']) / len(data['avg_compound_score'])
        else:
            data['avg_compound_score'] = 0.0

        # Calculate sentiment percentages
        total_sentiment_posts = data['bullish_count'] + data['bearish_count'] + data['neutral_count']
        if total_sentiment_posts > 0:
            data['bullish_pct'] = (data['bullish_count'] / total_sentiment_posts) * 100
            data['bearish_pct'] = (data['bearish_count'] / total_sentiment_posts) * 100
            data['neutral_pct'] = (data['neutral_count'] / total_sentiment_posts) * 100
        else:
            data['bullish_pct'] = 0.0
            data['bearish_pct'] = 0.0
            data['neutral_pct'] = 0.0

        # Calculate net sentiment (bullish - bearish)
        data['net_sentiment'] = data['bullish_pct'] - data['bearish_pct']

        data['num_companies'] = len(set(data['companies']))

    logger.info(f"✅ Aggregated sentiment for {len(sector_sentiment)} sectors")
    return sector_sentiment


def compare_company_to_sector(company_metrics: Dict[str, Any], sector_stats: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare a company's metrics to its sector benchmarks.

    Args:
        company_metrics: Dictionary of company metrics
        sector_stats: Dictionary of sector aggregate statistics

    Returns:
        Dictionary with comparison results and rankings
    """
    comparison = {
        'ticker': company_metrics.get('ticker'),
        'sector': company_metrics.get('sector'),
        'comparisons': {},
        'outliers': [],
        'strengths': [],
        'weaknesses': []
    }

    # Define metrics to compare (company_key: sector_key)
    metrics_to_compare = {
        'roe': 'avg_roe',
        'roa': 'avg_roa',
        'roic': 'avg_roic',
        'net_margin': 'avg_net_margin',
        'gross_margin': 'avg_gross_margin',
        'cagr': 'avg_cagr',
        'momentum_3m': 'avg_momentum_3m',
        'pe_ratio': 'avg_pe_ratio',
        'ps_ratio': 'avg_ps_ratio',
        'pb_ratio': 'avg_pb_ratio',
        'debt_to_equity': 'avg_debt_to_equity',
        'current_ratio': 'avg_current_ratio',
        'beta': 'avg_beta',
        'volatility': 'avg_volatility',
        'sharpe_ratio': 'avg_sharpe_ratio',
    }

    for company_key, sector_key in metrics_to_compare.items():
        company_value = company_metrics.get(company_key)
        sector_value = sector_stats.get(sector_key)

        if company_value is not None and sector_value is not None:
            # Calculate percentage difference from sector average
            if sector_value != 0:
                pct_diff = ((company_value - sector_value) / abs(sector_value)) * 100
            else:
                pct_diff = 0

            comparison['comparisons'][company_key] = {
                'company_value': company_value,
                'sector_avg': sector_value,
                'difference': company_value - sector_value,
                'pct_difference': pct_diff
            }

            # Identify significant outliers (>30% difference)
            if abs(pct_diff) > 30:
                comparison['outliers'].append({
                    'metric': company_key,
                    'pct_difference': pct_diff
                })

            # Identify strengths and weaknesses
            # Higher is better for these metrics
            if company_key in ['roe', 'roa', 'roic', 'net_margin', 'gross_margin', 'cagr',
                               'momentum_3m', 'current_ratio', 'sharpe_ratio']:
                if pct_diff > 20:
                    comparison['strengths'].append(company_key)
                elif pct_diff < -20:
                    comparison['weaknesses'].append(company_key)

            # Lower is better for these metrics
            elif company_key in ['pe_ratio', 'ps_ratio', 'pb_ratio', 'debt_to_equity', 'volatility', 'beta']:
                if pct_diff < -20:
                    comparison['strengths'].append(company_key)
                elif pct_diff > 20:
                    comparison['weaknesses'].append(company_key)

    # Calculate overall performance score relative to sector
    score = 0
    total_metrics = 0

    # Profitability score
    for metric in ['roe', 'roa', 'roic', 'net_margin']:
        if metric in comparison['comparisons']:
            pct_diff = comparison['comparisons'][metric]['pct_difference']
            score += min(max(pct_diff / 10, -5), 5)  # Cap at +/-5 points per metric
            total_metrics += 1

    # Growth score
    for metric in ['cagr', 'momentum_3m']:
        if metric in comparison['comparisons']:
            pct_diff = comparison['comparisons'][metric]['pct_difference']
            score += min(max(pct_diff / 10, -5), 5)
            total_metrics += 1

    # Valuation score (inverse - lower is better)
    for metric in ['pe_ratio', 'ps_ratio']:
        if metric in comparison['comparisons']:
            pct_diff = comparison['comparisons'][metric]['pct_difference']
            score -= min(max(pct_diff / 10, -5), 5)  # Subtract because lower is better
            total_metrics += 1

    # Risk score (inverse - lower is better)
    for metric in ['volatility']:
        if metric in comparison['comparisons']:
            pct_diff = comparison['comparisons'][metric]['pct_difference']
            score -= min(max(pct_diff / 10, -5), 5)
            total_metrics += 1

    # Normalize to 0-100 scale
    if total_metrics > 0:
        # Score ranges from -5*total to +5*total, normalize to 0-100
        max_score = 5 * total_metrics
        comparison['relative_performance_score'] = ((score + max_score) / (2 * max_score)) * 100
    else:
        comparison['relative_performance_score'] = 50  # Neutral if no data

    # Classify performance
    if comparison['relative_performance_score'] >= 70:
        comparison['classification'] = 'Sector Leader'
    elif comparison['relative_performance_score'] >= 55:
        comparison['classification'] = 'Above Average'
    elif comparison['relative_performance_score'] >= 45:
        comparison['classification'] = 'Average'
    elif comparison['relative_performance_score'] >= 30:
        comparison['classification'] = 'Below Average'
    else:
        comparison['classification'] = 'Sector Laggard'

    return comparison


def calculate_sector_momentum_with_sentiment(
    sector_stats: Dict[str, Dict[str, Any]],
    sector_sentiment: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Calculate sector momentum combining price action and social media sentiment.

    Args:
        sector_stats: Dictionary of sector statistics
        sector_sentiment: Dictionary of sector sentiment data

    Returns:
        Dictionary with momentum analysis for each sector
    """
    sector_momentum = {}

    for sector, stats in sector_stats.items():
        momentum_data = {
            'sector': sector,
            'price_momentum_1m': stats.get('avg_momentum_1m'),
            'price_momentum_3m': stats.get('avg_momentum_3m'),
            'price_momentum_6m': stats.get('avg_momentum_6m'),
            'price_momentum_1y': stats.get('avg_momentum_1y'),
            'sentiment_score': None,
            'net_sentiment': None,
            'combined_momentum_score': None,
            'momentum_trend': None,
            'signal': None
        }

        # Add sentiment data if available
        if sector in sector_sentiment:
            sent_data = sector_sentiment[sector]
            momentum_data['sentiment_score'] = sent_data.get('avg_compound_score', 0)
            momentum_data['net_sentiment'] = sent_data.get('net_sentiment', 0)
            momentum_data['total_posts'] = sent_data.get('total_posts', 0)

        # Calculate combined momentum score (price + sentiment)
        price_score = 0
        price_count = 0

        # Weight recent momentum more heavily
        if momentum_data['price_momentum_1m'] is not None:
            price_score += momentum_data['price_momentum_1m'] * 0.4
            price_count += 0.4
        if momentum_data['price_momentum_3m'] is not None:
            price_score += momentum_data['price_momentum_3m'] * 0.3
            price_count += 0.3
        if momentum_data['price_momentum_6m'] is not None:
            price_score += momentum_data['price_momentum_6m'] * 0.2
            price_count += 0.2
        if momentum_data['price_momentum_1y'] is not None:
            price_score += momentum_data['price_momentum_1y'] * 0.1
            price_count += 0.1

        if price_count > 0:
            weighted_price_momentum = price_score / price_count
        else:
            weighted_price_momentum = 0

        # Combine price momentum with sentiment (70% price, 30% sentiment)
        if momentum_data['sentiment_score'] is not None:
            # Scale sentiment from -1 to 1 to percentage like price momentum
            sentiment_contribution = momentum_data['sentiment_score'] * 100
            momentum_data['combined_momentum_score'] = (
                weighted_price_momentum * 0.7 + sentiment_contribution * 0.3
            )
        else:
            momentum_data['combined_momentum_score'] = weighted_price_momentum

        # Determine momentum trend
        if (momentum_data['price_momentum_3m'] is not None and
            momentum_data['price_momentum_6m'] is not None):
            if momentum_data['price_momentum_3m'] > momentum_data['price_momentum_6m']:
                momentum_data['momentum_trend'] = 'Accelerating'
            elif momentum_data['price_momentum_3m'] < momentum_data['price_momentum_6m']:
                momentum_data['momentum_trend'] = 'Decelerating'
            else:
                momentum_data['momentum_trend'] = 'Stable'

        # Generate trading signal
        score = momentum_data['combined_momentum_score']
        if score is not None:
            if score > 10:
                momentum_data['signal'] = 'Strong Buy'
            elif score > 5:
                momentum_data['signal'] = 'Buy'
            elif score > -5:
                momentum_data['signal'] = 'Hold'
            elif score > -10:
                momentum_data['signal'] = 'Sell'
            else:
                momentum_data['signal'] = 'Strong Sell'

        sector_momentum[sector] = momentum_data

    return sector_momentum


def calculate_sector_correlations_and_strength(metrics_df: pd.DataFrame, market_prices: Optional[pd.Series] = None) -> Dict[str, Any]:
    """
    Calculate inter-sector correlations and relative strength metrics.

    Args:
        metrics_df: DataFrame with company metrics including sector
        market_prices: Optional market benchmark prices for relative strength calculation

    Returns:
        Dictionary with correlation matrix and relative strength indicators
    """
    logger.info("Calculating sector correlations and relative strength...")

    result = {
        'correlation_matrix': {},
        'relative_strength': {},
        'sector_pairs': []
    }

    # Group companies by sector and calculate average returns
    sectors = metrics_df['sector'].unique()
    sectors = [s for s in sectors if s != 'Unknown' and pd.notna(s)]

    sector_returns = {}

    for sector in sectors:
        sector_companies = metrics_df[metrics_df['sector'] == sector]

        # Collect momentum data for correlation
        momentum_3m = sector_companies['momentum_3m'].dropna()
        momentum_6m = sector_companies['momentum_6m'].dropna()
        momentum_1y = sector_companies['momentum_1y'].dropna()

        if len(momentum_3m) > 0:
            sector_returns[sector] = {
                '3m': momentum_3m.mean(),
                '6m': momentum_6m.mean() if len(momentum_6m) > 0 else None,
                '1y': momentum_1y.mean() if len(momentum_1y) > 0 else None,
                'volatility': sector_companies['volatility'].mean(),
                'sharpe': sector_companies['sharpe_ratio'].mean()
            }

    # Calculate correlation matrix between sectors
    sectors_with_data = list(sector_returns.keys())

    for i, sector1 in enumerate(sectors_with_data):
        if sector1 not in result['correlation_matrix']:
            result['correlation_matrix'][sector1] = {}

        for sector2 in sectors_with_data:
            if sector1 == sector2:
                result['correlation_matrix'][sector1][sector2] = 1.0
                continue

            # Calculate correlation based on available momentum data
            s1_data = []
            s2_data = []

            for period in ['3m', '6m', '1y']:
                if (sector_returns[sector1][period] is not None and
                    sector_returns[sector2][period] is not None):
                    s1_data.append(sector_returns[sector1][period])
                    s2_data.append(sector_returns[sector2][period])

            if len(s1_data) >= 2:
                # Simple correlation calculation
                correlation = np.corrcoef(s1_data, s2_data)[0, 1]
                result['correlation_matrix'][sector1][sector2] = float(correlation)

                # Track high correlation pairs
                if i < sectors_with_data.index(sector2) and abs(correlation) > 0.7:
                    result['sector_pairs'].append({
                        'sector1': sector1,
                        'sector2': sector2,
                        'correlation': float(correlation),
                        'relationship': 'Positive' if correlation > 0 else 'Negative'
                    })

    # Calculate relative strength vs market (if market data available)
    if market_prices is not None and not market_prices.empty:
        # Calculate market momentum
        market_returns = {
            '1m': ((market_prices.iloc[-1] / market_prices.iloc[-21]) - 1) * 100 if len(market_prices) >= 21 else None,
            '3m': ((market_prices.iloc[-1] / market_prices.iloc[-63]) - 1) * 100 if len(market_prices) >= 63 else None,
            '6m': ((market_prices.iloc[-1] / market_prices.iloc[-126]) - 1) * 100 if len(market_prices) >= 126 else None,
            '1y': ((market_prices.iloc[-1] / market_prices.iloc[0]) - 1) * 100
        }

        for sector in sectors_with_data:
            returns = sector_returns[sector]
            rs_data = {}

            # Calculate relative strength for each period
            for period in ['3m', '6m', '1y']:
                if returns[period] is not None and market_returns[period] is not None:
                    # RS = Sector Return - Market Return
                    rs_data[f'rs_{period}'] = returns[period] - market_returns[period]

            # Calculate composite relative strength (weighted average)
            if rs_data:
                weights = {'rs_1y': 0.2, 'rs_6m': 0.3, 'rs_3m': 0.5}  # More weight to recent
                weighted_rs = sum(rs_data.get(k, 0) * v for k, v in weights.items() if k in rs_data)
                total_weight = sum(v for k, v in weights.items() if k in rs_data)

                if total_weight > 0:
                    composite_rs = weighted_rs / total_weight
                else:
                    composite_rs = 0

                rs_data['composite_rs'] = composite_rs

                # Classify strength
                if composite_rs > 5:
                    rs_data['classification'] = 'Strong Outperformer'
                elif composite_rs > 2:
                    rs_data['classification'] = 'Outperformer'
                elif composite_rs > -2:
                    rs_data['classification'] = 'Market Performer'
                elif composite_rs > -5:
                    rs_data['classification'] = 'Underperformer'
                else:
                    rs_data['classification'] = 'Strong Underperformer'

                result['relative_strength'][sector] = rs_data

    # Sort sector pairs by correlation strength
    result['sector_pairs'] = sorted(
        result['sector_pairs'],
        key=lambda x: abs(x['correlation']),
        reverse=True
    )

    logger.info(f"✅ Calculated correlations for {len(sectors_with_data)} sectors")
    return result


def calculate_sector_quality_score(sector_data: pd.DataFrame) -> float:
    """
    Calculate a composite quality score for a sector based on multiple metrics.
    Score ranges from 0-100, with higher being better.

    Factors:
    - Profitability (ROE, ROA, margins)
    - Growth (CAGR, momentum)
    - Financial health (debt ratios, liquidity)
    - Valuation (P/E, P/S ratios)
    - Risk-adjusted returns (Sharpe ratio, volatility)
    """
    score = 0
    max_score = 100

    # Profitability score (30 points)
    profitability_score = 0
    if sector_data['roe'].notna().any():
        avg_roe = sector_data['roe'].mean()
        profitability_score += min(avg_roe / 20 * 10, 10) if avg_roe > 0 else 0
    if sector_data['net_margin'].notna().any():
        avg_margin = sector_data['net_margin'].mean()
        profitability_score += min(avg_margin / 20 * 10, 10) if avg_margin > 0 else 0
    if sector_data['roic'].notna().any():
        avg_roic = sector_data['roic'].mean()
        profitability_score += min(avg_roic / 15 * 10, 10) if avg_roic > 0 else 0

    score += profitability_score

    # Growth score (25 points)
    growth_score = 0
    if sector_data['cagr'].notna().any():
        avg_cagr = sector_data['cagr'].mean()
        growth_score += min(max(avg_cagr, -10) / 30 * 15 + 7.5, 15)
    if sector_data['momentum_3m'].notna().any():
        avg_momentum = sector_data['momentum_3m'].mean()
        growth_score += min(max(avg_momentum, -20) / 40 * 10 + 5, 10)

    score += growth_score

    # Financial health score (25 points)
    health_score = 0
    if sector_data['debt_to_equity'].notna().any():
        avg_de = sector_data['debt_to_equity'].mean()
        # Lower is better, penalize high debt
        health_score += max(10 - (avg_de / 200 * 10), 0) if avg_de >= 0 else 5
    if sector_data['current_ratio'].notna().any():
        avg_current = sector_data['current_ratio'].mean()
        # Ideal range is 1.5-3.0
        if 1.5 <= avg_current <= 3.0:
            health_score += 10
        elif avg_current > 1.0:
            health_score += 5
    if sector_data['interest_coverage'].notna().any():
        avg_coverage = sector_data['interest_coverage'].mean()
        health_score += min(avg_coverage / 10 * 5, 5) if avg_coverage > 0 else 0

    score += health_score

    # Risk-adjusted returns (20 points)
    risk_score = 0
    if sector_data['sharpe_ratio'].notna().any():
        avg_sharpe = sector_data['sharpe_ratio'].mean()
        risk_score += min(max(avg_sharpe + 1, 0) / 3 * 10, 10)
    if sector_data['volatility'].notna().any():
        avg_vol = sector_data['volatility'].mean()
        # Lower volatility is better
        risk_score += max(10 - (avg_vol / 50 * 10), 0)

    score += risk_score

    return min(score, max_score)


def calculate_sector_metrics() -> Dict[str, Any]:
    """
    Calculate aggregate metrics for each sector.

    Returns:
        Dictionary with sector-level aggregated metrics
    """
    logger.info("=" * 60)
    logger.info("CALCULATING SECTOR METRICS")
    logger.info("=" * 60)

    # Load companies
    if not os.path.exists(COMPANIES_CSV_PATH):
        logger.error(f"Companies file not found: {COMPANIES_CSV_PATH}")
        return {}

    companies_df = pd.read_csv(COMPANIES_CSV_PATH)
    logger.info(f"Loaded {len(companies_df)} companies")

    # Fetch market benchmark (SPY) for beta calculations
    logger.info("Fetching market benchmark (SPY)...")
    market_prices = None
    try:
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="1y")
        if not spy_hist.empty and 'Close' in spy_hist.columns:
            market_prices = spy_hist['Close']
            logger.info("✅ Market benchmark loaded")
    except Exception as e:
        logger.warning(f"Could not fetch market benchmark: {e}")

    # Collect metrics for all companies
    all_metrics = []
    total = len(companies_df)

    for index, row in tqdm(companies_df.iterrows(), total=total, desc="Fetching company metrics"):
        ticker = row['ticker']

        # Skip tickers with special characters
        if '.' in ticker or '-' in ticker:
            continue

        metrics = get_company_metrics(ticker, market_prices)
        all_metrics.append(metrics)

        # Rate limiting
        time.sleep(0.3)

    # Convert to DataFrame for easier aggregation
    metrics_df = pd.DataFrame(all_metrics)

    # Remove rows with unknown sector
    metrics_df = metrics_df[metrics_df['sector'] != 'Unknown']
    metrics_df = metrics_df[metrics_df['sector'].notna()]

    logger.info(f"Successfully collected metrics for {len(metrics_df)} companies")

    # Group by sector and calculate aggregates
    sector_stats = {}

    for sector in metrics_df['sector'].unique():
        sector_data = metrics_df[metrics_df['sector'] == sector]

        # Helper function to calculate mean, skipping None/NaN values
        def safe_mean(series):
            clean = series.dropna()
            return float(clean.mean()) if len(clean) > 0 else None

        def safe_median(series):
            clean = series.dropna()
            return float(clean.median()) if len(clean) > 0 else None

        def safe_sum(series):
            clean = series.dropna()
            return float(clean.sum()) if len(clean) > 0 else None

        sector_stats[sector] = {
            # Basic info
            'num_companies': len(sector_data),
            'total_market_cap': safe_sum(sector_data['market_cap']),
            'avg_market_cap': safe_mean(sector_data['market_cap']),

            # Revenue and profitability
            'total_revenue': safe_sum(sector_data['revenue']),
            'avg_revenue': safe_mean(sector_data['revenue']),
            'avg_gross_margin': safe_mean(sector_data['gross_margin']),
            'median_gross_margin': safe_median(sector_data['gross_margin']),
            'avg_net_margin': safe_mean(sector_data['net_margin']),
            'median_net_margin': safe_median(sector_data['net_margin']),

            # Cash flow
            'total_free_cash_flow': safe_sum(sector_data['free_cash_flow']),
            'avg_free_cash_flow': safe_mean(sector_data['free_cash_flow']),

            # Valuation metrics
            'avg_pe_ratio': safe_mean(sector_data['pe_ratio']),
            'median_pe_ratio': safe_median(sector_data['pe_ratio']),
            'avg_ps_ratio': safe_mean(sector_data['ps_ratio']),
            'median_ps_ratio': safe_median(sector_data['ps_ratio']),
            'avg_pb_ratio': safe_mean(sector_data['pb_ratio']),
            'median_pb_ratio': safe_median(sector_data['pb_ratio']),

            # Earnings
            'avg_eps': safe_mean(sector_data['eps']),
            'median_eps': safe_median(sector_data['eps']),

            # Efficiency ratios
            'avg_roe': safe_mean(sector_data['roe']),
            'median_roe': safe_median(sector_data['roe']),
            'avg_roa': safe_mean(sector_data['roa']),
            'median_roa': safe_median(sector_data['roa']),
            'avg_roic': safe_mean(sector_data['roic']),
            'median_roic': safe_median(sector_data['roic']),

            # Debt and liquidity
            'avg_debt_to_equity': safe_mean(sector_data['debt_to_equity']),
            'median_debt_to_equity': safe_median(sector_data['debt_to_equity']),
            'avg_current_ratio': safe_mean(sector_data['current_ratio']),
            'median_current_ratio': safe_median(sector_data['current_ratio']),
            'avg_quick_ratio': safe_mean(sector_data['quick_ratio']),
            'median_quick_ratio': safe_median(sector_data['quick_ratio']),
            'avg_interest_coverage': safe_mean(sector_data['interest_coverage']),
            'median_interest_coverage': safe_median(sector_data['interest_coverage']),

            # Technical indicators
            'avg_rsi': safe_mean(sector_data['rsi']),
            'median_rsi': safe_median(sector_data['rsi']),
            'avg_macd': safe_mean(sector_data['macd']),

            # Performance and growth
            'avg_cagr': safe_mean(sector_data['cagr']),
            'median_cagr': safe_median(sector_data['cagr']),
            'avg_momentum_1m': safe_mean(sector_data['momentum_1m']),
            'avg_momentum_3m': safe_mean(sector_data['momentum_3m']),
            'avg_momentum_6m': safe_mean(sector_data['momentum_6m']),
            'avg_momentum_1y': safe_mean(sector_data['momentum_1y']),

            # Risk metrics
            'avg_volatility': safe_mean(sector_data['volatility']),
            'median_volatility': safe_median(sector_data['volatility']),
            'avg_beta': safe_mean(sector_data['beta']),
            'median_beta': safe_median(sector_data['beta']),
            'avg_sharpe_ratio': safe_mean(sector_data['sharpe_ratio']),
            'median_sharpe_ratio': safe_median(sector_data['sharpe_ratio']),

            # Quality score
            'quality_score': calculate_sector_quality_score(sector_data)
        }

    # === NEW ADVANCED ANALYTICS ===

    # 1. Aggregate sector sentiment from X/Twitter data
    logger.info("")
    sector_sentiment = aggregate_sector_sentiment()

    # 2. Calculate sector momentum with sentiment
    logger.info("")
    sector_momentum = calculate_sector_momentum_with_sentiment(sector_stats, sector_sentiment)

    # 3. Calculate sector correlations and relative strength
    logger.info("")
    correlation_analysis = calculate_sector_correlations_and_strength(metrics_df, market_prices)

    # Save individual company metrics
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    company_metrics_file = os.path.join(SECTOR_METRICS_DIR, f"company_metrics_{timestamp}.json")

    metrics_df.to_json(company_metrics_file, orient='records', indent=2)
    logger.info(f"✅ Saved company metrics to: {company_metrics_file}")

    # Save sector aggregates with all new analytics
    sector_file = os.path.join(SECTOR_METRICS_DIR, f"sector_metrics_{timestamp}.json")

    sector_summary = {
        'fetch_timestamp': datetime.now().isoformat(),
        'total_companies_analyzed': len(metrics_df),
        'total_sectors': len(sector_stats),
        'sectors': sector_stats,
        'sentiment_analysis': sector_sentiment,
        'momentum_analysis': sector_momentum,
        'correlation_analysis': correlation_analysis
    }

    with open(sector_file, 'w') as f:
        json.dump(sector_summary, f, indent=2)

    logger.info(f"✅ Saved sector metrics to: {sector_file}")

    # Print summary
    logger.info("")
    logger.info("=" * 60)
    logger.info("SECTOR METRICS SUMMARY")
    logger.info("=" * 60)

    # Sort by quality score
    for sector, stats in sorted(sector_stats.items(), key=lambda x: x[1]['quality_score'] if x[1]['quality_score'] else 0, reverse=True):
        logger.info(f"\n{sector}:")
        logger.info(f"  Companies: {stats['num_companies']}")
        logger.info(f"  Quality Score: {stats['quality_score']:.1f}/100" if stats['quality_score'] else "  Quality Score: N/A")
        logger.info("")

        # Profitability
        logger.info("  Profitability:")
        logger.info(f"    ROE: {stats['avg_roe']:.2f}%" if stats['avg_roe'] else "    ROE: N/A")
        logger.info(f"    ROA: {stats['avg_roa']:.2f}%" if stats['avg_roa'] else "    ROA: N/A")
        logger.info(f"    ROIC: {stats['avg_roic']:.2f}%" if stats['avg_roic'] else "    ROIC: N/A")
        logger.info(f"    Net Margin: {stats['avg_net_margin']:.2f}%" if stats['avg_net_margin'] else "    Net Margin: N/A")

        # Growth
        logger.info("  Growth:")
        logger.info(f"    CAGR: {stats['avg_cagr']:.2f}%" if stats['avg_cagr'] else "    CAGR: N/A")
        logger.info(f"    3M Momentum: {stats['avg_momentum_3m']:.2f}%" if stats['avg_momentum_3m'] else "    3M Momentum: N/A")

        # Valuation
        logger.info("  Valuation:")
        logger.info(f"    P/E: {stats['avg_pe_ratio']:.2f}" if stats['avg_pe_ratio'] else "    P/E: N/A")
        logger.info(f"    P/S: {stats['avg_ps_ratio']:.2f}" if stats['avg_ps_ratio'] else "    P/S: N/A")

        # Financial Health
        logger.info("  Financial Health:")
        logger.info(f"    Debt/Equity: {stats['avg_debt_to_equity']:.2f}" if stats['avg_debt_to_equity'] else "    Debt/Equity: N/A")
        logger.info(f"    Current Ratio: {stats['avg_current_ratio']:.2f}" if stats['avg_current_ratio'] else "    Current Ratio: N/A")

        # Risk Metrics
        logger.info("  Risk:")
        logger.info(f"    Beta: {stats['avg_beta']:.2f}" if stats['avg_beta'] else "    Beta: N/A")
        logger.info(f"    Volatility: {stats['avg_volatility']:.2f}%" if stats['avg_volatility'] else "    Volatility: N/A")
        logger.info(f"    Sharpe Ratio: {stats['avg_sharpe_ratio']:.2f}" if stats['avg_sharpe_ratio'] else "    Sharpe Ratio: N/A")

    # Display sentiment analysis
    if sector_sentiment:
        logger.info("")
        logger.info("=" * 60)
        logger.info("SECTOR SENTIMENT ANALYSIS")
        logger.info("=" * 60)

        for sector, sent_data in sorted(sector_sentiment.items(), key=lambda x: x[1]['net_sentiment'], reverse=True)[:5]:
            logger.info(f"\n{sector}:")
            logger.info(f"  Total Posts: {sent_data['total_posts']}")
            logger.info(f"  Net Sentiment: {sent_data['net_sentiment']:.1f}%")
            logger.info(f"  Bullish: {sent_data['bullish_pct']:.1f}% | Bearish: {sent_data['bearish_pct']:.1f}% | Neutral: {sent_data['neutral_pct']:.1f}%")
            logger.info(f"  Compound Score: {sent_data['avg_compound_score']:.3f}")

    # Display momentum signals
    if sector_momentum:
        logger.info("")
        logger.info("=" * 60)
        logger.info("SECTOR MOMENTUM SIGNALS")
        logger.info("=" * 60)

        for sector, mom_data in sorted(sector_momentum.items(), key=lambda x: x[1]['combined_momentum_score'] or 0, reverse=True)[:5]:
            logger.info(f"\n{sector}:")
            logger.info(f"  Combined Momentum Score: {mom_data['combined_momentum_score']:.2f}%")
            logger.info(f"  Signal: {mom_data['signal']}")
            logger.info(f"  Trend: {mom_data['momentum_trend']}")
            logger.info(f"  3M Price: {mom_data['price_momentum_3m']:.2f}%" if mom_data['price_momentum_3m'] else "  3M Price: N/A")

    # Display correlation insights
    if correlation_analysis and correlation_analysis['sector_pairs']:
        logger.info("")
        logger.info("=" * 60)
        logger.info("HIGH CORRELATION SECTOR PAIRS")
        logger.info("=" * 60)

        for pair in correlation_analysis['sector_pairs'][:5]:
            logger.info(f"\n{pair['sector1']} <-> {pair['sector2']}")
            logger.info(f"  Correlation: {pair['correlation']:.2f} ({pair['relationship']})")

    # Display relative strength leaders
    if correlation_analysis and correlation_analysis['relative_strength']:
        logger.info("")
        logger.info("=" * 60)
        logger.info("SECTOR RELATIVE STRENGTH (vs SPY)")
        logger.info("=" * 60)

        for sector, rs_data in sorted(correlation_analysis['relative_strength'].items(), key=lambda x: x[1]['composite_rs'], reverse=True)[:5]:
            logger.info(f"\n{sector}:")
            logger.info(f"  Composite RS: {rs_data['composite_rs']:.2f}%")
            logger.info(f"  Classification: {rs_data['classification']}")
            if 'rs_3m' in rs_data:
                logger.info(f"  3M RS: {rs_data['rs_3m']:.2f}%")

    logger.info("")
    logger.info("=" * 60)
    logger.info("SECTOR METRICS CALCULATION COMPLETED")
    logger.info("=" * 60)
    logger.info(f"✅ Complete analysis saved to: {sector_file}")

    return sector_summary


def calculate_industry_benchmarks() -> Dict[str, Dict[str, float]]:
    """
    Calculate industry benchmark P/E and P/S ratios by fetching data from representative companies.
    Uses a broader sample of companies per industry to compute median benchmarks.

    Returns:
        Dictionary mapping industry names to benchmark metrics (pe, ps)
    """
    logger.info("Calculating industry benchmarks from market data...")

    # Define representative companies for each industry
    # These are well-known, established companies used to calculate benchmarks
    industry_representatives = {
        'Semiconductors': ['NVDA', 'AMD', 'INTC', 'TXN', 'QCOM', 'MU', 'ADI', 'MCHP', 'NXPI', 'MRVL'],
        'Software - Infrastructure': ['ORCL', 'CRM', 'NOW', 'TEAM', 'SNOW', 'DDOG', 'NET', 'MDB', 'ZS', 'PANW'],
        'Software': ['MSFT', 'ADBE', 'INTU', 'WDAY', 'ANSS', 'CDNS', 'SNPS'],
        'Hardware': ['AAPL', 'HPE', 'HPQ', 'NTAP', 'STX', 'WDC'],
        'Internet Services': ['GOOGL', 'META', 'AMZN', 'NFLX'],
        'Financial Services': ['JPM', 'BAC', 'WFC', 'C', 'GS', 'MS', 'BLK', 'SCHW'],
        'Healthcare': ['UNH', 'JNJ', 'PFE', 'ABBV', 'TMO', 'ABT', 'MRK', 'LLY'],
        'Energy': ['XOM', 'CVX', 'COP', 'SLB', 'EOG', 'MPC', 'PSX'],
        'Consumer': ['WMT', 'HD', 'MCD', 'NKE', 'SBUX', 'TGT', 'LOW'],

        # Mining & Materials industries
        'Other Industrial Metals & Mining': ['FCX', 'NEM', 'AA', 'X', 'CLF', 'STLD'],
        'Other Precious Metals & Mining': ['NEM', 'GOLD', 'AEM', 'KGC', 'AU', 'RGLD', 'WPM'],
        'Gold': ['NEM', 'GOLD', 'AEM', 'KGC', 'AU', 'FNV', 'RGLD', 'WPM', 'AGI'],
        'Copper': ['FCX', 'SCCO', 'TRQ'],
        'Aluminum': ['AA', 'CENX'],
        'Specialty Chemicals': ['ALB', 'DD', 'DOW', 'LYB', 'APD', 'EMN', 'FMC', 'CE', 'PPG']
    }

    benchmarks = {}

    for industry, tickers in industry_representatives.items():
        logger.info(f"Processing {industry}...")

        pe_values = []
        ps_values = []

        for ticker in tickers:
            try:
                stock = yf.Ticker(ticker)
                info = stock.info

                # Get P/E ratio (prefer trailing, fallback to forward)
                pe = info.get('trailingPE')
                if pe is None or pe < 0:
                    pe = info.get('forwardPE')

                # Get P/S ratio
                ps = info.get('priceToSalesTrailing12Months')
                if ps is None or ps < 0:
                    market_cap = info.get('marketCap')
                    revenue = info.get('totalRevenue')
                    if market_cap and revenue and revenue > 0:
                        ps = market_cap / revenue

                # Only include valid positive values
                if pe and 0 < pe < 500:  # Filter out extreme outliers
                    pe_values.append(pe)
                if ps and 0 < ps < 100:  # Filter out extreme outliers
                    ps_values.append(ps)

                time.sleep(0.1)  # Rate limiting

            except Exception as e:
                logger.warning(f"Failed to fetch data for {ticker}: {e}")
                continue

        # Calculate median (more robust than mean for financial ratios)
        if pe_values:
            median_pe = float(np.median(pe_values))
        else:
            median_pe = None

        if ps_values:
            median_ps = float(np.median(ps_values))
        else:
            median_ps = None

        benchmarks[industry] = {
            'pe': median_pe,
            'ps': median_ps,
            'sample_size_pe': len(pe_values),
            'sample_size_ps': len(ps_values)
        }

        pe_str = f"{median_pe:.1f}" if median_pe else "N/A"
        ps_str = f"{median_ps:.1f}" if median_ps else "N/A"
        logger.info(f"  {industry}: P/E={pe_str}, P/S={ps_str} (samples: {len(pe_values)}/{len(ps_values)})")

    # Save to file
    output_dir = Path("data/structured")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_file = output_dir / "industry_benchmarks.json"

    with open(output_file, 'w') as f:
        json.dump({
            'generated_at': datetime.now().isoformat(),
            'benchmarks': benchmarks,
            'note': 'Industry benchmark P/E and P/S ratios computed from median values of representative companies'
        }, f, indent=2)

    logger.info(f"✅ Industry benchmarks saved to {output_file}")

    return benchmarks


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("FINANCIAL DATA FETCH PIPELINE STARTED")
    logger.info("=" * 60)
    logger.info(f"Target tickers: {', '.join(TARGET_TICKERS)}")
    logger.info("")

    # Step 1: Fetch company information from SEC
    companies_df = fetch_company_info_from_sec()

    if companies_df.empty:
        logger.error("Failed to fetch company information. Exiting.")
        exit(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("COMPANY INFORMATION FETCHED")
    logger.info("=" * 60)
    logger.info(f"Total companies: {len(companies_df)}")
    logger.info("")

    # Step 2: Fetch CEO profiles
    fetch_ceo_profiles(companies_df)

    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING FINANCIAL DATA")
    logger.info("=" * 60)

    # Step 3: Fetch financial statements, prices, and filings
    # Filter out tickers with dots or dashes that yfinance might not handle well
    companies_df = companies_df[~companies_df['ticker'].str.contains(r'\.|\-')]

    for index, row in tqdm(companies_df.iterrows(), total=companies_df.shape[0], desc="Processing Companies"):
        ticker = row['ticker']
        cik = str(row['cik'])

        # Fetch and Save Data
        fetch_financial_statements(ticker)
        earnings_records = fetch_quarterly_earnings(ticker)
        store_quarterly_earnings_in_neo4j(ticker, row.get('company_name'), earnings_records)
        fetch_stock_prices(ticker)
        fetch_10k_filings(ticker, cik)

        # Rate limit to be respectful to APIs
        time.sleep(0.5)

    # Step 4: Fetch market indices
    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING MARKET INDICES")
    logger.info("=" * 60)
    fetch_market_indices()

    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING REDDIT DATA")
    logger.info("=" * 60)

    # Step 4: Fetch Reddit data
    fetch_reddit_data()

    logger.info("")
    logger.info("=" * 60)
    logger.info("FETCHING X/TWITTER DATA")
    logger.info("=" * 60)

    # Step 5: Fetch X/Twitter data
    fetch_x_data()

    logger.info("")
    logger.info("=" * 60)
    logger.info("CALCULATING SECTOR METRICS")
    logger.info("=" * 60)

    # Step 6: Calculate sector metrics
    try:
        calculate_sector_metrics()
        logger.info("✅ Sector metrics calculation completed")
    except Exception as e:
        logger.error(f"Failed to calculate sector metrics: {e}")
        import traceback
        traceback.print_exc()

    logger.info("")
    logger.info("=" * 60)
    logger.info("CALCULATING INDUSTRY BENCHMARKS")
    logger.info("=" * 60)

    # Step 7: Calculate industry benchmarks
    try:
        calculate_industry_benchmarks()
        logger.info("✅ Industry benchmarks calculation completed")
    except Exception as e:
        logger.error(f"Failed to calculate industry benchmarks: {e}")
        import traceback
        traceback.print_exc()

    logger.info("")
    logger.info("=" * 60)
    logger.info("DATA FETCHING PIPELINE COMPLETED")
    logger.info("=" * 60)
    logger.info("Check the 'data' directory for all fetched data.")
    logger.info("  - Financials: data/structured/financials")
    logger.info("  - Sector Metrics: data/structured/sector_metrics")
    logger.info("  - Industry Benchmarks: data/structured/industry_benchmarks.json")


def fetch_x_data_only():
    """
    Fetch only X/Twitter data for all target companies.
    Useful when you want to update X data without re-fetching everything else.

    Usage:
        python -c "from fetch_data import fetch_x_data_only; fetch_x_data_only()"
    """
    logger.info("=" * 60)
    logger.info("FETCHING X/TWITTER DATA ONLY")
    logger.info("=" * 60)
    logger.info(f"Target tickers: {', '.join(TARGET_TICKERS)}")
    logger.info("")

    # Check if companies.csv exists
    if not os.path.exists(COMPANIES_CSV_PATH):
        logger.error(f"Companies file not found: {COMPANIES_CSV_PATH}")
        logger.info("Run the full fetch_data.py pipeline first to generate company information.")
        return

    # Fetch X data
    fetch_x_data()

    logger.info("")
    logger.info("=" * 60)
    logger.info("X DATA FETCHING COMPLETED")
    logger.info("=" * 60)
    logger.info("Check data/unstructured/x/ for the generated files")
