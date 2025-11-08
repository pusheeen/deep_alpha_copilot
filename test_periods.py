#!/usr/bin/env python3
"""Test all price history periods."""
import requests
import json

periods = ['1d', '1w', '1m', '6m', '1y', '2y', 'max']

print("Testing all price history periods for NVDA:")
print("=" * 70)

for period in periods:
    try:
        response = requests.get(f"http://localhost:8000/api/price-history/NVDA?period={period}")
        data = response.json()

        if data['status'] == 'success':
            price_data = data['data']['price_data']
            if price_data:
                first_date = price_data[0]['date']
                last_date = price_data[-1]['date']
                print(f"{period:>4}: {len(price_data):>5} data points, {first_date} to {last_date}")
            else:
                print(f"{period:>4}: NO DATA")
        else:
            print(f"{period:>4}: ERROR - {data.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"{period:>4}: ERROR - {str(e)}")

print("=" * 70)
