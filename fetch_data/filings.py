import os
import logging
import time
import requests
from .utils import retry_on_failure, FILINGS_10K_DIR, SEC_USER_AGENT

logger = logging.getLogger(__name__)

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

                form_code = form.replace('-', '')
                file_path = os.path.join(FILINGS_10K_DIR, f"{ticker}_{form_code}_{year}.html")
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(doc_response.text)

                filing_count += 1
            except requests.exceptions.RequestException as e:
                logger.error(f"    Error downloading filing {doc_url}: {e}")

    logger.info(f"✅ Finished fetching filings for {ticker}")
