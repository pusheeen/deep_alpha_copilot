#!/usr/bin/env python3
"""
Scrape actual weekly token usage data from OpenRouter rankings page.
"""

import requests
from bs4 import BeautifulSoup
import json
import re
from datetime import datetime

def scrape_openrouter_weekly_data():
    """
    Scrape actual weekly token usage data from OpenRouter rankings page.
    Returns real measured data points.
    """
    url = "https://openrouter.ai/rankings"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
    }

    print(f"Fetching {url}...")
    response = requests.get(url, headers=headers, timeout=30)
    print(f"Status: {response.status_code}")

    if response.status_code != 200:
        print(f"Error: {response.status_code}")
        return None

    # Save the HTML for inspection
    with open('openrouter_rankings.html', 'w') as f:
        f.write(response.text)
    print("Saved HTML to openrouter_rankings.html")

    soup = BeautifulSoup(response.text, 'html.parser')

    # Look for Next.js data
    next_data = soup.find('script', id='__NEXT_DATA__')
    if next_data:
        print("\nFound __NEXT_DATA__!")
        try:
            data = json.loads(next_data.string)
            # Save for inspection
            with open('openrouter_next_data.json', 'w') as f:
                json.dump(data, f, indent=2)
            print("Saved Next.js data to openrouter_next_data.json")

            # Try to find the chart data
            if 'props' in data and 'pageProps' in data['props']:
                page_props = data['props']['pageProps']
                print(f"\nPage props keys: {list(page_props.keys())}")

                # Look for data that might contain the chart
                for key in page_props:
                    value = page_props[key]
                    if isinstance(value, (dict, list)):
                        print(f"\n{key} type: {type(value)}")
                        if isinstance(value, list) and len(value) > 0:
                            print(f"  First item: {value[0] if len(str(value[0])) < 200 else str(value[0])[:200]}")
                        elif isinstance(value, dict):
                            print(f"  Keys: {list(value.keys())[:10]}")

                return page_props
        except Exception as e:
            print(f"Error parsing Next.js data: {e}")
    else:
        print("No __NEXT_DATA__ found")

    # Look for data in script tags
    print("\nLooking for data in script tags...")
    scripts = soup.find_all('script')
    for i, script in enumerate(scripts):
        if script.string and 'token' in script.string.lower():
            # Check if it contains array-like data
            if re.search(r'\[\s*\{.*"date"', script.string[:500], re.DOTALL | re.IGNORECASE):
                print(f"\nFound potential data in script {i}:")
                print(script.string[:1000])
                with open(f'script_{i}.txt', 'w') as f:
                    f.write(script.string)

    return None

if __name__ == "__main__":
    data = scrape_openrouter_weekly_data()
    if data:
        print("\n" + "="*70)
        print("Successfully extracted data!")
        print("="*70)
