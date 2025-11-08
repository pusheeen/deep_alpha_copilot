import os
import re
import json
import time
import csv
import logging
import requests
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
from datetime import datetime
from .utils import retry_on_failure, CEO_REPORTS_DIR, CEO_PROFILE_DIR

logger = logging.getLogger(__name__)

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def search_linkedin_profile(ceo_name: str, company_name: str) -> dict:
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
        clean_name = re.sub(r'\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s*', '', ceo_name).strip()
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        search_query = f"{clean_name} {company_name} CEO LinkedIn"
        search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

        response = requests.get(search_url, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com/in/' in href:
                    match = re.search(r'(https://[a-z]+\.linkedin\.com/in/[^&\s]+)', href)
                    if match:
                        linkedin_url = match.group(1)
                        linkedin_url = re.sub(r'["\'].*$', '', linkedin_url)
                        linkedin_data["linkedin_url"] = linkedin_url
                        logger.info(f"Found LinkedIn URL: {linkedin_url}")
                        break

        if linkedin_data["linkedin_url"] != "Not found":
            time.sleep(2)
            try:
                profile_response = requests.get(linkedin_data["linkedin_url"], headers=headers, timeout=15)
                if profile_response.status_code == 200:
                    profile_soup = BeautifulSoup(profile_response.content, 'html.parser')
                    page_text = profile_soup.get_text()
                    education_patterns = [
                        r'(University|College|Institute|School) of [A-Z][a-z\s]+',
                        r'(Harvard|Stanford|MIT|Yale|Princeton|Berkeley|Cambridge|Oxford)[^,\.]*',
                        r'(Bachelor|Master|MBA|PhD|B\.S\.|M\.S\.|B\.A\.|M\.A\.)[^,\.]{0,50}'
                    ]
                    for pattern in education_patterns:
                        matches = re.findall(pattern, page_text, re.IGNORECASE)
                        if matches:
                            linkedin_data["education"] = ', '.join(matches[:2])
                            break

                    experience_pattern = r'(Chief|Senior|Vice President|Director|Manager|Head of)[^\.]{0,100}'
                    experience_matches = re.findall(experience_pattern, page_text)
                    if experience_matches:
                        linkedin_data["past_experience"] = experience_matches[:5]

                    year_patterns = re.findall(r'(20\d{2})\s*-\s*Present', page_text, re.IGNORECASE)
                    if year_patterns:
                        start_year = int(year_patterns[0])
                        current_year = datetime.now().year
                        years = current_year - start_year
                        linkedin_data["start_date"] = str(start_year)
                        linkedin_data["tenure_duration"] = f"{years} year{'s' if years != 1 else ''}"
            except Exception as e:
                logger.warning(f"Could not scrape LinkedIn profile: {e}")
        time.sleep(2)
    except Exception as e:
        logger.warning(f"LinkedIn search failed: {e}")

    return linkedin_data

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def query_ceo_info_by_ticker(ticker: str, company_name: str) -> dict:
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

        try:
            stock = yf.Ticker(ticker)
            info = stock.info
            if hasattr(stock, 'get_officers') and callable(stock.get_officers):
                officers = stock.get_officers()
                if officers is not None and not officers.empty:
                    for idx, officer in officers.iterrows():
                        title = officer.get('title', '').lower()
                        if 'chief executive officer' in title or 'ceo' in title or title == 'ceo':
                            ceo_data["ceo_name"] = officer.get('name', 'Not found')
                            ceo_data["ceo_title"] = officer.get('title', 'Chief Executive Officer')
                            if 'age' in officer:
                                ceo_data["age"] = officer.get('age')
                            if 'totalPay' in officer:
                                ceo_data["total_pay"] = officer.get('totalPay')
                            logger.info(f"Found CEO {ceo_data['ceo_name']} via yfinance officers")
                            break

            if ceo_data["ceo_name"] == "Not found":
                if 'companyOfficers' in info and info['companyOfficers']:
                    for officer in info['companyOfficers']:
                        title = officer.get('title', '').lower()
                        if 'chief executive officer' in title or 'ceo' in title:
                            ceo_data["ceo_name"] = officer.get('name', 'Not found')
                            ceo_data["ceo_title"] = officer.get('title', 'Chief Executive Officer')
                            if 'age' in officer:
                                ceo_data["age"] = officer['age']
                            if 'yearBorn' in officer:
                                ceo_data["year_born"] = officer['yearBorn']
                            if 'totalPay' in officer:
                                ceo_data["total_pay"] = officer['totalPay']
                            logger.info(f"Found CEO {ceo_data['ceo_name']} via yfinance info")
                            break

            if ceo_data["ceo_name"] == "Not found":
                for field in ['ceo', 'CEO', 'chiefExecutiveOfficer']:
                    if field in info and info[field]:
                        ceo_data["ceo_name"] = info[field]
                        ceo_data["ceo_title"] = "Chief Executive Officer"
                        logger.info(f"Found CEO {ceo_data['ceo_name']} via yfinance {field} field")
                        break
        except Exception as e:
            logger.warning(f"yfinance lookup failed for {ticker}: {e}")

        if ceo_data["ceo_name"] != "Not found":
            logger.info(f"Searching LinkedIn for {ceo_data['ceo_name']}")
            linkedin_data = search_linkedin_profile(ceo_data["ceo_name"], company_name)
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
            result = query_ceo_info_by_ticker(ticker, company_name)
            results.append(result)
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

        if index < len(companies_df) - 1:
            time.sleep(5)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
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

    logger.info("=" * 60)
    logger.info("CEO BATCH PROCESSING COMPLETED")
    logger.info("=" * 60)
    logger.info(f"Total companies: {len(companies_df)}")
    logger.info(f"Successful: {successful_count}")
    logger.info(f"Failed: {failed_count}")
    logger.info(f"Success rate: {successful_count/len(companies_df)*100:.1f}%")
    logger.info(f"JSON report: {json_filename}")
    logger.info(f"CSV report: {csv_filename}")
