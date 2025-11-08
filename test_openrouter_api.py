#!/usr/bin/env python3
import os
import requests
from dotenv import load_dotenv
import json
from datetime import datetime, timedelta

load_dotenv()

api_key = os.getenv('OPENROUTER_API_KEY')

headers = {
    'Authorization': f'Bearer {api_key}',
    'HTTP-Referer': 'https://github.com/yinglu1985/deep_alpha_copilot',
    'X-Title': 'Deep Alpha Copilot'
}

# Based on OpenRouter docs, the platform stats show:
# - 1.06 trillion tokens per week (current)
# - 8.4 trillion tokens per month
# - 57x year-on-year growth
# - 2.8x year-to-date growth

print("OpenRouter Platform-Wide Statistics:")
print("=" * 60)
print("Current (Nov 2025): ~1.06 trillion tokens/week")
print("                    ~8.4 trillion tokens/month")
print("                    ~151 billion tokens/day")
print("\nGrowth Metrics:")
print("  Year-over-year: 57x growth")
print("  Year-to-date: 2.8x growth")
print("\n" + "=" * 60)

# Try different endpoints to find actual usage data
endpoints = [
    'https://openrouter.ai/api/v1/auth/key',
    'https://openrouter.ai/api/v1/activity',
    'https://openrouter.ai/api/v1/stats',
    'https://openrouter.ai/api/v1/analytics',
    'https://openrouter.ai/api/v1/credits',
    'https://openrouter.ai/api/v1/generations',
]

for endpoint in endpoints:
    try:
        print(f"\nTesting: {endpoint}")
        print('-' * 60)
        response = requests.get(endpoint, headers=headers, timeout=10)
        print(f"Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(json.dumps(data, indent=2)[:800])
        elif response.status_code == 404:
            print("❌ Not found")
        else:
            print(f"Response: {response.text[:300]}")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")
