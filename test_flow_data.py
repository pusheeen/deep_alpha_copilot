#!/usr/bin/env python3
"""
Quick test script to verify flow data fetching works correctly.
"""

import logging
from fetch_data.flow_data import fetch_combined_flow_data
from fetch_data.utils import FLOW_DATA_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def test_flow_data():
    """Test fetching flow data for a single ticker"""
    test_ticker = "NVDA"

    print(f"\n{'='*60}")
    print(f"Testing Flow Data Fetching for {test_ticker}")
    print(f"{'='*60}\n")

    try:
        result = fetch_combined_flow_data(test_ticker, FLOW_DATA_DIR)

        print(f"\n✅ Successfully fetched flow data for {test_ticker}")
        print(f"\nData saved to: {FLOW_DATA_DIR}")

        # Display summary
        print(f"\n{'='*60}")
        print("INSTITUTIONAL DATA SUMMARY")
        print(f"{'='*60}")

        inst_data = result.get('institutional', {})
        print(f"Ticker: {inst_data.get('ticker')}")
        print(f"Institutional Ownership: {inst_data.get('institutional_ownership_pct')}%")
        print(f"Insider Ownership: {inst_data.get('insider_ownership_pct')}%")
        print(f"Number of Institutions: {inst_data.get('number_of_institutions')}")
        print(f"Total Institutional Value: ${inst_data.get('total_institutional_value', 0):,}")

        if inst_data.get('top_10_holders'):
            print(f"\nTop 5 Institutional Holders:")
            for i, holder in enumerate(inst_data['top_10_holders'][:5], 1):
                print(f"  {i}. {holder.get('holder')} - {holder.get('shares', 0):,} shares ({holder.get('pct_out', 0)}%)")

        print(f"\n{'='*60}")
        print("RETAIL FLOW DATA SUMMARY")
        print(f"{'='*60}")

        retail_data = result.get('retail', {})
        metrics = retail_data.get('metrics', {})
        interp = retail_data.get('interpretation', {})

        print(f"Ticker: {retail_data.get('ticker')}")
        print(f"Average Daily Volume: {metrics.get('average_daily_volume', 0):,}")
        print(f"Recent 30d Avg Volume: {metrics.get('recent_30d_avg_volume', 0):,}")
        print(f"Volume Trend: {metrics.get('volume_trend_pct')}%")
        print(f"Estimated Avg Retail Participation: {metrics.get('estimated_avg_retail_participation_pct')}%")
        print(f"Net Flow Indicator: {metrics.get('net_flow_indicator_pct')}%")
        print(f"Inflow Days: {metrics.get('inflow_days_count')}")
        print(f"Outflow Days: {metrics.get('outflow_days_count')}")

        print(f"\nInterpretation:")
        print(f"  Retail Trend: {interp.get('retail_trend')}")
        print(f"  Flow Direction: {interp.get('flow_direction')}")
        print(f"  Volume Pattern: {interp.get('volume_pattern')}")

        print(f"\n{'='*60}")
        print("✅ TEST PASSED - Flow data fetching working correctly!")
        print(f"{'='*60}\n")

        return True

    except Exception as e:
        print(f"\n❌ TEST FAILED - Error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_flow_data()
    exit(0 if success else 1)
