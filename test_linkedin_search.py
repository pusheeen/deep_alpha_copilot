#!/usr/bin/env python3
"""
Test script to debug LinkedIn profile search
"""

import requests
from bs4 import BeautifulSoup
import re
import time

def test_google_search(ceo_name, company_name):
    """Test Google search for LinkedIn profile"""
    print(f"\n{'='*60}")
    print(f"Testing search for: {ceo_name} at {company_name}")
    print(f"{'='*60}")

    clean_name = re.sub(r'\b(Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.)\s*', '', ceo_name).strip()

    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }

    # Try Google search
    print(f"\n1. Trying Google search...")
    search_query = f"{clean_name} {company_name} CEO LinkedIn"
    search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
    print(f"Search URL: {search_url}")

    try:
        response = requests.get(search_url, headers=headers, timeout=15)
        print(f"Status code: {response.status_code}")
        print(f"Response length: {len(response.content)} bytes")

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for LinkedIn URLs
            linkedin_urls = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com/in/' in href:
                    match = re.search(r'(https://[a-z]+\.linkedin\.com/in/[^&\s"\']+)', href)
                    if match:
                        url = match.group(1)
                        linkedin_urls.append(url)

            if linkedin_urls:
                print(f"✅ Found {len(linkedin_urls)} LinkedIn URLs:")
                for url in linkedin_urls[:3]:
                    print(f"  - {url}")
            else:
                print("❌ No LinkedIn URLs found")
                print("\nDebugging - First 500 chars of response:")
                print(response.text[:500])
    except Exception as e:
        print(f"❌ Error: {e}")

    # Try DuckDuckGo search
    print(f"\n2. Trying DuckDuckGo search...")
    ddg_url = f"https://duckduckgo.com/html/?q={search_query.replace(' ', '+')}"
    print(f"Search URL: {ddg_url}")

    try:
        response = requests.get(ddg_url, headers=headers, timeout=15)
        print(f"Status code: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')

            # Look for LinkedIn URLs
            linkedin_urls = []
            for link in soup.find_all('a', href=True):
                href = link['href']
                if 'linkedin.com/in/' in href:
                    # DuckDuckGo uses redirect URLs
                    match = re.search(r'linkedin\.com/in/([^/&\s"\']+)', href)
                    if match:
                        username = match.group(1)
                        url = f"https://www.linkedin.com/in/{username}"
                        linkedin_urls.append(url)

            if linkedin_urls:
                print(f"✅ Found {len(linkedin_urls)} LinkedIn URLs:")
                for url in linkedin_urls[:3]:
                    print(f"  - {url}")
            else:
                print("❌ No LinkedIn URLs found")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Try constructing URL directly
    print(f"\n3. Trying direct URL construction...")
    # Convert "Jen-Hsun Huang" -> "jen-hsun-huang"
    username = clean_name.lower().replace(' ', '-').replace('.', '')
    username = re.sub(r'[^a-z-]', '', username)
    constructed_url = f"https://www.linkedin.com/in/{username}"
    print(f"Constructed URL: {constructed_url}")

    try:
        response = requests.head(constructed_url, headers=headers, timeout=10, allow_redirects=True)
        print(f"Status code: {response.status_code}")
        if response.status_code == 200:
            print(f"✅ Profile exists!")
        elif response.status_code == 999:
            print("⚠️  LinkedIn returned 999 (rate limiting/bot detection)")
        else:
            print(f"❌ Profile not found or blocked")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    # Test with Jensen Huang (NVIDIA CEO)
    test_google_search("Mr. Jen-Hsun  Huang", "NVIDIA CORP")

    time.sleep(3)

    # Test with Hock Tan (Broadcom CEO)
    test_google_search("Mr. Hock E. Tan", "Broadcom Inc.")
