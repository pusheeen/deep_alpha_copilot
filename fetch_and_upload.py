"""
Fetch data locally and upload to BigQuery.
This script runs fetch_data.py and then uploads all generated JSON files to BigQuery.
Sends email notification with summary upon completion.
"""

import os
import json
import pandas as pd
from pathlib import Path
from dotenv import load_dotenv
from bigquery_uploader import BigQueryUploader
from email_notifier import EmailNotifier
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Initialize BigQuery uploader
PROJECT_ID = os.getenv("GCP_PROJECT_ID")
if not PROJECT_ID:
    logger.error("GCP_PROJECT_ID not found in environment")
    exit(1)

uploader = BigQueryUploader(PROJECT_ID)
notifier = EmailNotifier()

# Statistics tracker
stats = {
    'ceo_profiles': {'new': 0, 'skipped': 0},
    'quarterly_earnings': {'new': 0, 'skipped': 0},
    'financial_statements': {'new': 0},
    'stock_prices': {'new': 0, 'skipped': 0},
    'sector_metrics': {'new': 0},
    'company_metrics': {'new': 0},
    'reddit_posts': {'new': 0},
    'x_posts': {'new': 0},
}

errors = []

def upload_all_data():
    """Upload all locally generated JSON files to BigQuery."""

    logger.info("="*60)
    logger.info("UPLOADING DATA TO BIGQUERY")
    logger.info("="*60)

    # 1. Upload CEO Profiles
    ceo_dir = Path("data/ceo_profiles")
    if ceo_dir.exists():
        for file in ceo_dir.glob("*_ceo_profile.json"):
            try:
                with open(file) as f:
                    data = json.load(f)
                    result = uploader.upload_ceo_profile(data)
                    if result:
                        stats['ceo_profiles']['new'] += 1
                    else:
                        stats['ceo_profiles']['skipped'] += 1
            except Exception as e:
                errors.append(f"Error uploading CEO profile from {file.name}: {e}")
                logger.error(errors[-1])

    # 2. Upload Quarterly Earnings
    earnings_dir = Path("data/structured/earnings")
    if earnings_dir.exists():
        for file in earnings_dir.glob("*_quarterly_earnings.json"):
            ticker = file.stem.replace("_quarterly_earnings", "")
            try:
                with open(file) as f:
                    data = json.load(f)
                    new_count, skipped_count = uploader.upload_quarterly_earnings(ticker, data)
                    stats['quarterly_earnings']['new'] += new_count
                    stats['quarterly_earnings']['skipped'] += skipped_count
            except Exception as e:
                errors.append(f"Error uploading earnings for {ticker}: {e}")
                logger.error(errors[-1])

    # 3. Upload Financial Statements
    financials_dir = Path("data/structured/financials")
    if financials_dir.exists():
        for file in financials_dir.glob("*_financials.json"):
            ticker = file.stem.replace("_financials", "")
            try:
                with open(file) as f:
                    data = json.load(f)
                    new_count = uploader.upload_financial_statements(ticker, data)
                    stats['financial_statements']['new'] += new_count
            except Exception as e:
                errors.append(f"Error uploading financials for {ticker}: {e}")
                logger.error(errors[-1])

    # 4. Upload Stock Prices
    prices_dir = Path("data/structured/prices")
    if prices_dir.exists():
        for file in prices_dir.glob("*_prices.csv"):
            ticker = file.stem.replace("_prices", "")
            try:
                df = pd.read_csv(file, index_col=0, parse_dates=True)
                new_count, skipped_count = uploader.upload_stock_prices(ticker, df)
                stats['stock_prices']['new'] += new_count
                stats['stock_prices']['skipped'] += skipped_count
            except Exception as e:
                errors.append(f"Error uploading prices for {ticker}: {e}")
                logger.error(errors[-1])

    # 5. Upload Sector Metrics
    sector_metrics_dir = Path("data/structured/sector_metrics")
    if sector_metrics_dir.exists():
        # Get the most recent sector metrics file
        sector_files = list(sector_metrics_dir.glob("sector_metrics_*.json"))
        if sector_files:
            latest_file = max(sector_files, key=lambda x: x.stat().st_mtime)
            try:
                with open(latest_file) as f:
                    data = json.load(f)
                    count = uploader.upload_sector_metrics(data)
                    stats['sector_metrics']['new'] += count
            except Exception as e:
                errors.append(f"Error uploading sector metrics: {e}")
                logger.error(errors[-1])

        # Upload company metrics if available
        company_files = list(sector_metrics_dir.glob("company_metrics_*.json"))
        if company_files:
            latest_file = max(company_files, key=lambda x: x.stat().st_mtime)
            try:
                with open(latest_file) as f:
                    data = json.load(f)
                    count = uploader.upload_company_metrics(data)
                    stats['company_metrics']['new'] += count
            except Exception as e:
                errors.append(f"Error uploading company metrics: {e}")
                logger.error(errors[-1])

    # 6. Upload Reddit Posts
    reddit_dir = Path("data/unstructured/reddit")
    if reddit_dir.exists():
        for file in reddit_dir.glob("*_reddit_posts_*.json"):
            ticker = file.stem.split("_reddit_posts")[0]
            try:
                with open(file) as f:
                    data = json.load(f)
                    new_count = uploader.upload_reddit_posts(ticker, data)
                    stats['reddit_posts']['new'] += new_count
            except Exception as e:
                errors.append(f"Error uploading Reddit posts for {ticker}: {e}")
                logger.error(errors[-1])

    # 7. Upload X Posts
    x_dir = Path("data/unstructured/x")
    if x_dir.exists():
        for file in x_dir.glob("*_x_posts_*.json"):
            ticker = file.stem.split("_x_posts")[0]
            try:
                with open(file) as f:
                    data = json.load(f)
                    new_count = uploader.upload_x_posts(ticker, data)
                    stats['x_posts']['new'] += new_count
            except Exception as e:
                errors.append(f"Error uploading X posts for {ticker}: {e}")
                logger.error(errors[-1])

    logger.info("="*60)
    logger.info("BIGQUERY UPLOAD COMPLETED")
    logger.info("="*60)


if __name__ == "__main__":
    import subprocess
    import sys

    # Step 1: Run fetch_data.py to generate local files
    logger.info("="*60)
    logger.info("STEP 1: FETCHING DATA LOCALLY")
    logger.info("="*60)

    result = subprocess.run([sys.executable, "fetch_data.py"],
                          capture_output=False,
                          text=True)

    if result.returncode != 0:
        logger.error("fetch_data.py failed")
        errors.append("fetch_data.py execution failed")

    # Step 2: Upload all data to BigQuery
    logger.info("")
    logger.info("="*60)
    logger.info("STEP 2: UPLOADING TO BIGQUERY")
    logger.info("="*60)

    upload_all_data()

    logger.info("")
    logger.info("="*60)
    logger.info("✅ PIPELINE COMPLETED!")
    logger.info("="*60)
    logger.info(f"Data saved locally in data/ directory")
    logger.info(f"Data uploaded to BigQuery project: {PROJECT_ID}")
    logger.info("="*60)

    # Step 3: Send email notification
    logger.info("")
    logger.info("Sending email notification...")
    notifier.send_summary_email(stats, errors if errors else None)
    logger.info("="*60)
