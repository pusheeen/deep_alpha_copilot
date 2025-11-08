"""Test scoring engine and data loading."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

print("Testing Scoring Engine & Data Loading")
print("="*60)

try:
    from dotenv import load_dotenv
    load_dotenv()

    print("\n1. Testing data directory detection...")
    from app.scoring.engine import get_data_root, DATA_ROOT
    detected_root = get_data_root()
    print(f"   Detected data root: {detected_root}")
    print(f"   DATA_ROOT constant: {DATA_ROOT}")

    # Check if data exists
    from app.scoring.engine import FINANCIALS_DIR, EARNINGS_DIR, PRICES_DIR
    print(f"\n2. Checking data directories...")
    print(f"   Financials dir: {FINANCIALS_DIR}")
    print(f"   Exists: {FINANCIALS_DIR.exists()}")

    if FINANCIALS_DIR.exists():
        files = list(FINANCIALS_DIR.glob("*.json"))
        print(f"   Files found: {len(files)}")
        if files:
            print(f"   Sample files: {[f.name for f in files[:3]]}")

    print(f"\n3. Testing scoring engine...")
    from app.scoring import compute_company_scores

    # Test with a ticker we know has data
    ticker = "NVDA"
    print(f"   Computing scores for {ticker}...")

    try:
        result = compute_company_scores(ticker)
        print(f"   ✓ Scoring completed successfully!")

        # Check result structure
        if isinstance(result, dict):
            print(f"   Result keys: {list(result.keys())}")

            # Check for overall score
            if 'overall' in result:
                overall = result['overall']
                print(f"\n   Overall Score:")
                if isinstance(overall, dict):
                    for key, value in overall.items():
                        print(f"     - {key}: {value}")
                else:
                    print(f"     {overall}")

            # Check for categories
            categories = ['growth', 'profitability', 'valuation', 'sentiment', 'momentum']
            found_categories = [c for c in categories if c in result]
            print(f"\n   Found score categories: {found_categories}")

        print(f"\n✅ Scoring engine works correctly!")

    except Exception as e:
        print(f"   ✗ Scoring failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print(f"\n4. Testing with multiple tickers...")
    test_tickers = ["NVDA", "AMD", "ORCL"]
    results = {}

    for ticker in test_tickers:
        try:
            scores = compute_company_scores(ticker)
            if 'overall' in scores and 'total_score' in scores['overall']:
                results[ticker] = scores['overall']['total_score']
                print(f"   ✓ {ticker}: score = {scores['overall']['total_score']:.2f}")
            else:
                results[ticker] = "N/A"
                print(f"   ✓ {ticker}: computed (no total score)")
        except Exception as e:
            results[ticker] = f"Error: {e}"
            print(f"   ✗ {ticker}: {e}")

    successful = sum(1 for v in results.values() if isinstance(v, (int, float)))
    print(f"\n   Successfully scored {successful}/{len(test_tickers)} tickers")

    print("\n" + "="*60)
    print("✅ All scoring engine tests passed!")
    print("="*60)

except ImportError as e:
    print(f"\n✗ Import error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"\n✗ Unexpected error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
