#!/usr/bin/env python3
"""
Script to fetch and save historical token usage from OpenRouter API.
"""

from dotenv import load_dotenv
load_dotenv()

from .token_usage import fetch_and_save_token_usage
import sys

def main():
    """Main function to fetch and save token usage."""
    days = int(sys.argv[1]) if len(sys.argv) > 1 else 90  # Default to 3 months
    
    print(f"\n{'='*60}")
    print(f"🔄 Fetching OpenRouter Token Usage (last {days} days)")
    print(f"{'='*60}\n")
    
    try:
        filepath = fetch_and_save_token_usage(days=days)
        print(f"\n✅ Success! Token usage data saved to: {filepath}\n")
    except Exception as e:
        print(f"\n❌ Error: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()

