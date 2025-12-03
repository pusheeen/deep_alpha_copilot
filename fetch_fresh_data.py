#!/usr/bin/env python3
"""
Script to fetch fresh news and flow data for tickers.
"""

import os
import sys
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from fetch_data.flow_data import fetch_combined_flow_data
from fetch_data.utils import FLOW_DATA_DIR
from target_tickers import TARGET_TICKERS

def fetch_news_for_ticker(ticker: str):
    """Test fetching news for a ticker."""
    print(f"\n{'='*60}")
    print(f"Fetching news for {ticker}...")
    print(f"{'='*60}")
    
    try:
        from app.main import fetch_realtime_news
        result = fetch_realtime_news(ticker, window_hours=72, max_results=8)
        
        print(f"✅ News fetched successfully")
        print(f"   Articles found: {len(result.get('articles', []))}")
        print(f"   Summary: {result.get('summary', {}).get('headline', 'N/A')}")
        
        if result.get('articles'):
            print(f"\n   Top articles:")
            for i, article in enumerate(result['articles'][:3], 1):
                print(f"   {i}. {article.get('title', 'N/A')[:60]}...")
                print(f"      Source: {article.get('source', 'N/A')}")
                print(f"      Published: {article.get('published', 'N/A')}")
        else:
            print(f"   ⚠️  No articles found in last 72 hours")
            
        return result
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def fetch_flow_for_ticker(ticker: str):
    """Fetch flow data for a ticker."""
    print(f"\n{'='*60}")
    print(f"Fetching flow data for {ticker}...")
    print(f"{'='*60}")
    
    try:
        flow_dir = FLOW_DATA_DIR
        os.makedirs(flow_dir, exist_ok=True)
        
        result = fetch_combined_flow_data(ticker, flow_dir)
        
        print(f"✅ Flow data fetched successfully")
        print(f"   Institutional ownership: {result.get('institutional', {}).get('institutional_ownership_pct', 'N/A')}%")
        print(f"   Top holder: {result.get('institutional', {}).get('top_10_holders', [{}])[0].get('holder', 'N/A') if result.get('institutional', {}).get('top_10_holders') else 'N/A'}")
        
        if result.get('institutional_changes', {}).get('has_data'):
            changes = result['institutional_changes']
            print(f"   Net change: {changes.get('net_change_pct', 'N/A')}%")
            print(f"   Institutions increased: {changes.get('institutions_increased', 'N/A')}")
            print(f"   Institutions decreased: {changes.get('institutions_decreased', 'N/A')}")
        
        if result.get('retail', {}).get('metrics'):
            retail = result['retail']['metrics']
            print(f"   Retail participation: {retail.get('estimated_avg_retail_participation_pct', 'N/A')}%")
            print(f"   Net flow indicator: {retail.get('net_flow_indicator_pct', 'N/A')}%")
        
        return result
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    """Main function to fetch fresh data."""
    print("="*60)
    print("FETCHING FRESH DATA")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Get tickers from command line or use default
    if len(sys.argv) > 1:
        tickers = [t.upper() for t in sys.argv[1:]]
    else:
        # Default to NVDA for testing
        tickers = ['NVDA']
    
    print(f"\nTickers to process: {', '.join(tickers)}")
    
    for ticker in tickers:
        # Fetch news
        news_result = fetch_news_for_ticker(ticker)
        
        # Fetch flow data
        flow_result = fetch_flow_for_ticker(ticker)
        
        print(f"\n✅ Completed processing {ticker}")
    
    print(f"\n{'='*60}")
    print("DONE")
    print(f"{'='*60}")

if __name__ == "__main__":
    main()

