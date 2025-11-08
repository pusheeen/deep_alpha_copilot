import logging
import os
from dotenv import load_dotenv

# Load environment variables from .env (e.g., NEWS_API_KEY)
dotenv_path = os.path.join(os.path.dirname(__file__), '.env')
load_dotenv(dotenv_path)
import pandas as pd
from fetch_data.companies import fetch_company_info_from_sec
from fetch_data.ceo_profiles import fetch_ceo_profiles
from fetch_data.financials import fetch_financial_statements, fetch_quarterly_earnings
from fetch_data.prices import fetch_stock_prices
from fetch_data.filings import fetch_10k_filings
from fetch_data.market_indices import fetch_market_indices
from fetch_data.reddit import fetch_reddit_data
from fetch_data.twitter import fetch_x_data
from fetch_data.news import fetch_and_interpret_news
from fetch_data.sector_metrics import calculate_sector_metrics
from fetch_data.flow_data import fetch_combined_flow_data
from fetch_data.utils import FLOW_DATA_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    logging.info("Starting data fetching workflow...")

    # 1. Fetch company info
    companies_df = fetch_company_info_from_sec()
    if companies_df.empty:
        logging.error("No company data fetched. Aborting workflow.")
        return

    # Enrich companies with sector information via yfinance
    try:
        import yfinance as yf
        logging.info("Enriching companies DataFrame with sector information via yfinance...")
        companies_df['sector'] = companies_df['ticker'].apply(
            lambda t: yf.Ticker(t).info.get('sector')
        )
    except Exception as e:
        logging.warning(f"Could not fetch sector info for companies: {e}")

    # 2. Fetch CEO profiles
    fetch_ceo_profiles(companies_df)

    # 3. Fetch data for each company
    for _, row in companies_df.iterrows():
        ticker = row['ticker']
        cik = row['cik']

        fetch_financial_statements(ticker)
        fetch_quarterly_earnings(ticker)
        fetch_stock_prices(ticker)
        fetch_10k_filings(ticker, cik)
        fetch_combined_flow_data(ticker, FLOW_DATA_DIR)

    # 4. Fetch market-wide data
    fetch_market_indices()
    fetch_reddit_data()
    fetch_x_data(companies_df)
    fetch_and_interpret_news(companies_df)

    # 5. Fetch same-day sector news for all sectors
    try:
        from fetch_data.sector_news import fetch_sector_news
        import json, re
        from datetime import datetime
        from fetch_data.utils import NEWS_DATA_DIR

        # Directory for sector news JSON files
        sector_news_dir = os.path.join(os.path.dirname(NEWS_DATA_DIR), 'sector_news')
        os.makedirs(sector_news_dir, exist_ok=True)

        if 'sector' in companies_df.columns:
            unique_sectors = companies_df['sector'].dropna().unique()
            today = datetime.utcnow().date().isoformat()
            for sector in unique_sectors:
                if not sector:
                    continue
                try:
                    # Fetch a batch, then filter by same-day publish_time
                    articles = fetch_sector_news(sector, max_articles=100) or []
                    today_articles = [a for a in articles if a.get('publish_time', '').startswith(today)]
                    # Sanitize sector name for filename
                    safe_name = re.sub(r'[^a-zA-Z0-9_]', '_', sector)
                    filename = os.path.join(sector_news_dir, f"{safe_name}_news_{today}.json")
                    # Save filtered same-day articles
                    with open(filename, 'w') as f:
                        json.dump({
                            'sector': sector,
                            'fetch_date': today,
                            'total_articles': len(today_articles),
                            'articles': today_articles
                        }, f, indent=2)
                    logging.info(f"✅ Saved {len(today_articles)} same-day news articles for sector '{sector}' to {filename}")
                except Exception as e:
                    logging.error(f"Error fetching same-day sector news for {sector}: {e}")
    except ImportError:
        logging.warning("Sector news module not available. Skipping sector news fetch.")

    # 6. Calculate sector metrics
    calculate_sector_metrics()

    logging.info("Data fetching workflow completed.")

if __name__ == "__main__":
    main()