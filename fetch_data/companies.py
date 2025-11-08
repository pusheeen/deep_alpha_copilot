import os
import requests
import pandas as pd
import logging
from .utils import retry_on_failure, SEC_USER_AGENT, TARGET_TICKERS, COMPANIES_CSV_PATH

logger = logging.getLogger(__name__)

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

    all_companies = [
        {
            "cik": str(details['cik_str']),
            "ticker": details['ticker'],
            "company_name": details['title']
        }
        for details in company_data.values()
    ]

    df = pd.DataFrame(all_companies)
    filtered_df = df[df['ticker'].isin(TARGET_TICKERS)]
    final_df = filtered_df[['ticker', 'company_name', 'cik']]

    final_df.to_csv(COMPANIES_CSV_PATH, index=False)

    logger.info(f"Successfully fetched {len(final_df)} companies from SEC")
    logger.info(f"Saved to {COMPANIES_CSV_PATH}")

    return final_df
