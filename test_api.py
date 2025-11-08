"""Test API endpoints locally."""

import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_endpoint(method, endpoint, description, expected_status=200, data=None):
    """Test a single endpoint."""
    url = f"{BASE_URL}{endpoint}"
    print(f"\nTesting: {description}")
    print(f"  {method} {endpoint}")

    try:
        if method == "GET":
            response = requests.get(url, timeout=30)
        elif method == "POST":
            response = requests.post(url, json=data, timeout=30)
        else:
            print(f"  ✗ Unsupported method: {method}")
            return False

        print(f"  Status: {response.status_code}")

        if response.status_code == expected_status:
            print(f"  ✓ SUCCESS")

            # Try to parse JSON response
            try:
                data = response.json()
                # Print first few keys if it's a dict
                if isinstance(data, dict):
                    keys = list(data.keys())[:5]
                    print(f"  Response keys: {keys}")
                    if 'status' in data:
                        print(f"  Status field: {data['status']}")
            except:
                # Not JSON, show first 100 chars
                text = response.text[:100]
                print(f"  Response: {text}...")

            return True
        else:
            print(f"  ✗ FAILED - Expected {expected_status}, got {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return False

    except requests.exceptions.ConnectionError:
        print(f"  ✗ CONNECTION ERROR - Server not running?")
        return False
    except requests.exceptions.Timeout:
        print(f"  ✗ TIMEOUT - Request took too long")
        return False
    except Exception as e:
        print(f"  ✗ ERROR: {e}")
        return False

def main():
    print("="*60)
    print("Local API Testing Suite")
    print("="*60)

    # Test if server is running
    try:
        requests.get(BASE_URL, timeout=5)
        print("\n✓ Server is running at", BASE_URL)
    except:
        print(f"\n✗ Server not running at {BASE_URL}")
        print("Start server with: uvicorn app.main:app --reload --port 8000")
        sys.exit(1)

    results = []

    # Test endpoints
    results.append(test_endpoint(
        "GET", "/",
        "Home page (HTML)"
    ))

    results.append(test_endpoint(
        "GET", "/api/scores/NVDA",
        "Get scores for NVDA"
    ))

    results.append(test_endpoint(
        "GET", "/api/price-history/NVDA?period=1m",
        "Get price history for NVDA (1 month)"
    ))

    results.append(test_endpoint(
        "GET", "/api/valuation-metrics/NVDA",
        "Get valuation metrics for NVDA"
    ))

    results.append(test_endpoint(
        "GET", "/api/market-conditions",
        "Get market conditions"
    ))

    results.append(test_endpoint(
        "GET", "/api/latest-news/NVDA",
        "Get latest news for NVDA"
    ))

    # Test invalid ticker (should handle gracefully)
    results.append(test_endpoint(
        "GET", "/api/scores/INVALID_TICKER",
        "Test error handling (invalid ticker)",
        expected_status=200  # Should return error in JSON
    ))

    # Summary
    print("\n" + "="*60)
    print("Test Summary")
    print("="*60)
    total = len(results)
    passed = sum(results)
    failed = total - passed

    print(f"\nTotal tests: {total}")
    print(f"Passed: {passed} ✓")
    print(f"Failed: {failed} ✗")

    if failed == 0:
        print("\n✅ All tests passed!")
        return 0
    else:
        print(f"\n⚠️  {failed} test(s) failed")
        return 1

if __name__ == "__main__":
    sys.exit(main())
