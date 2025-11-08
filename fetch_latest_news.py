#!/usr/bin/env python3
"""
Script to fetch and update news for all companies and sectors using fetch_data/news.py
"""
import logging
import os
import time
from dotenv import load_dotenv
import pandas as pd

# Load environment variables
load_dotenv()

from fetch_data.news import fetch_and_interpret_news
from fetch_data.sector_news import fetch_sector_news

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def main():
    logging.info("=" * 70)
    logging.info("STARTING NEWS UPDATE WORKFLOW")
    logging.info("=" * 70)

    # Load companies
    companies_file = "data/companies.csv"
    if not os.path.exists(companies_file):
        logging.error(f"Companies file not found: {companies_file}")
        return

    companies_df = pd.read_csv(companies_file)
    logging.info(f"Loaded {len(companies_df)} companies\n")

    # 1. Fetch company news
    logging.info("=" * 70)
    logging.info("FETCHING COMPANY NEWS & AI INTERPRETATIONS")
    logging.info("=" * 70)
    fetch_and_interpret_news(companies_df)

    # 2. Fetch sector news
    logging.info("\n" + "=" * 70)
    logging.info("FETCHING SECTOR NEWS")
    logging.info("=" * 70)

    sectors = [
        "Technology",
        "Semiconductors",
        "Energy",
        "Financials",
        "Healthcare",
        "Consumer Discretionary",
        "Industrials"
    ]

    for sector in sectors:
        try:
            logging.info(f"\nFetching news for {sector} sector...")
            articles = fetch_sector_news(sector, max_articles=20)
            if articles:
                logging.info(f"✅ Fetched {len(articles)} articles for {sector}")
            else:
                logging.warning(f"⚠️  No articles found for {sector}")
            time.sleep(2)  # Rate limiting
        except Exception as e:
            logging.error(f"❌ Error fetching {sector} sector news: {e}")
            import traceback
            traceback.print_exc()

    logging.info("\n" + "=" * 70)
    logging.info("✅ NEWS UPDATE COMPLETE!")
    logging.info("=" * 70)

if __name__ == "__main__":
    main()
