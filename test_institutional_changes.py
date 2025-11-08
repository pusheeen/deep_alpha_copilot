#!/usr/bin/env python3
"""
Test script to demonstrate institutional inflow/outflow tracking.
Simulates previous data and shows institutional changes.
"""

import logging
import json
import os
from datetime import datetime, timedelta
from fetch_data.flow_data import fetch_combined_flow_data, calculate_institutional_changes
from fetch_data.utils import FLOW_DATA_DIR

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_simulated_previous_data(ticker: str):
    """Create simulated previous institutional data for testing"""

    # Get current data first
    current_file = os.path.join(FLOW_DATA_DIR, f"{ticker}_institutional_flow_20251107.json")

    if not os.path.exists(current_file):
        print(f"Current data not found. Please run test_flow_data.py first.")
        return False

    with open(current_file, 'r') as f:
        current_data = json.load(f)

    # Simulate previous data (7 days ago) with some changes
    previous_date = (datetime.utcnow() - timedelta(days=7)).strftime('%Y%m%d')

    # Modify some holdings to simulate changes
    previous_data = current_data.copy()
    previous_data['timestamp'] = (datetime.utcnow() - timedelta(days=7)).isoformat()

    # Simulate institutional changes
    if 'top_10_holders' in previous_data and len(previous_data['top_10_holders']) > 0:
        # Vanguard increased position by 5%
        previous_data['top_10_holders'][0]['shares'] = int(previous_data['top_10_holders'][0]['shares'] * 0.95)
        previous_data['top_10_holders'][0]['value'] = int(previous_data['top_10_holders'][0]['value'] * 0.95)

        # BlackRock decreased position by 3%
        if len(previous_data['top_10_holders']) > 1:
            previous_data['top_10_holders'][1]['shares'] = int(previous_data['top_10_holders'][1]['shares'] * 1.03)
            previous_data['top_10_holders'][1]['value'] = int(previous_data['top_10_holders'][1]['value'] * 1.03)

        # FMR increased by 10%
        if len(previous_data['top_10_holders']) > 2:
            previous_data['top_10_holders'][2]['shares'] = int(previous_data['top_10_holders'][2]['shares'] * 0.90)
            previous_data['top_10_holders'][2]['value'] = int(previous_data['top_10_holders'][2]['value'] * 0.90)

    # Update total shares
    previous_data['total_institutional_shares'] = int(previous_data['total_institutional_shares'] * 0.97)
    previous_data['total_institutional_value'] = int(previous_data['total_institutional_value'] * 0.97)

    # Save simulated previous data
    previous_file = os.path.join(FLOW_DATA_DIR, f"{ticker}_institutional_flow_{previous_date}.json")
    with open(previous_file, 'w') as f:
        json.dump(previous_data, f, indent=2)

    print(f"✅ Created simulated previous data for {previous_date}")
    return True

def test_institutional_changes():
    """Test institutional change tracking"""
    test_ticker = "NVDA"

    print(f"\n{'='*60}")
    print(f"Testing Institutional Inflow/Outflow Tracking for {test_ticker}")
    print(f"{'='*60}\n")

    # Create simulated previous data
    if not create_simulated_previous_data(test_ticker):
        return False

    # Fetch new combined data (will compare with previous)
    print(f"\nFetching new flow data with institutional change tracking...\n")
    result = fetch_combined_flow_data(test_ticker, FLOW_DATA_DIR)

    # Display institutional changes
    changes = result.get('institutional_changes', {})

    print(f"\n{'='*60}")
    print("INSTITUTIONAL CHANGE TRACKING RESULTS")
    print(f"{'='*60}")

    if changes.get('has_comparison'):
        net_flow = changes['net_institutional_flow']

        print(f"\n📊 NET INSTITUTIONAL FLOW:")
        print(f"   Direction: {net_flow['direction'].upper()}")
        print(f"   Shares Change: {net_flow['shares_change']:,}")
        print(f"   Value Change: ${net_flow['value_change']:,}")
        print(f"   Current Total Shares: {net_flow['current_total_shares']:,}")
        print(f"   Previous Total Shares: {net_flow['previous_total_shares']:,}")

        summary = changes['summary']
        print(f"\n📈 SUMMARY:")
        print(f"   Total Holders Tracked: {summary['total_holders_tracked']}")
        print(f"   Holders Increased Positions: {summary['holders_increased']}")
        print(f"   Holders Decreased Positions: {summary['holders_decreased']}")

        if summary['top_5_buyers']:
            print(f"\n🟢 TOP 5 BUYERS (Increased Positions):")
            for i, buyer in enumerate(summary['top_5_buyers'], 1):
                print(f"   {i}. {buyer['holder']}")
                print(f"      • Bought: {buyer['shares_change']:,} shares ({buyer['pct_change']:+.2f}%)")
                print(f"      • Current: {buyer['current_shares']:,} shares")

        if summary['top_5_sellers']:
            print(f"\n🔴 TOP 5 SELLERS (Decreased Positions):")
            for i, seller in enumerate(summary['top_5_sellers'], 1):
                print(f"   {i}. {seller['holder']}")
                print(f"      • Sold: {abs(seller['shares_change']):,} shares ({seller['pct_change']:.2f}%)")
                print(f"      • Current: {seller['current_shares']:,} shares")

        print(f"\n📅 Comparison Period:")
        print(f"   Previous Data: {changes['comparison_date']}")
        print(f"   Current Data: {changes['current_date']}")

    else:
        print(f"⚠️  {changes.get('message', 'No comparison available')}")

    print(f"\n{'='*60}")
    print("✅ INSTITUTIONAL CHANGE TRACKING TEST COMPLETED!")
    print(f"{'='*60}\n")

    return True

if __name__ == "__main__":
    success = test_institutional_changes()
    exit(0 if success else 1)
