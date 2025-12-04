#!/usr/bin/env python3
"""
Generate Deep Alpha news interpretations for tickers.
Uses Gemini 2.0 Flash Experimental LLM.
"""

import sys
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_data.news_analysis import save_news_interpretation
from fetch_data.utils import NEWS_DATA_DIR

def generate_interpretation_for_ticker(ticker: str):
    """Generate interpretation for a specific ticker."""
    print(f"\n{'='*60}")
    print(f"Generating Deep Alpha interpretation for {ticker}...")
    print(f"{'='*60}")
    
    # Find the latest news file for this ticker
    news_files = sorted(Path(NEWS_DATA_DIR).glob(f"{ticker}_*_news_*.json"))
    if not news_files:
        print(f"❌ No news file found for {ticker}")
        return None
    
    latest_news_file = news_files[-1]
    print(f"📰 Using news file: {latest_news_file.name}")
    
    try:
        result = save_news_interpretation(ticker, str(latest_news_file))
        if result:
            print(f"✅ Successfully generated interpretation for {ticker}")
            print(f"   Saved to: {result}")
            return result
        else:
            print(f"❌ Failed to generate interpretation for {ticker}")
            return None
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function."""
    print("="*60)
    print("DEEP ALPHA NEWS INTERPRETATION GENERATOR")
    print("="*60)
    print("LLM Model: Gemini 2.0 Flash Experimental")
    print("Framework: Deep Alpha 7-Pillar Stock Evaluation")
    print("="*60)
    
    # Get tickers from command line or use default
    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
    else:
        # Default to popular tickers
        tickers = ['NVDA', 'AMD', 'INTC', 'MU', 'GOOGL']
    
    print(f"\nTickers to process: {', '.join(tickers)}")
    
    results = {}
    for ticker in tickers:
        result = generate_interpretation_for_ticker(ticker)
        results[ticker] = result
    
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    successful = [t for t, r in results.items() if r]
    failed = [t for t, r in results.items() if not r]
    
    if successful:
        print(f"✅ Successfully generated: {', '.join(successful)}")
    if failed:
        print(f"❌ Failed: {', '.join(failed)}")
    
    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

