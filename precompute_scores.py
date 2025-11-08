
import json
import os
from pathlib import Path
import sys

# Add the project root to the Python path
project_root = Path(__file__).resolve().parents[1]
sys.path.append(str(project_root))

from app.scoring.engine import compute_company_scores, ScoreComputationError, safe_json_serialize

# Get the data root directory using the same logic as the scoring engine
def get_data_root() -> Path:
    """
    Get data directory based on environment.
    """
    if data_root_env := os.getenv("DATA_ROOT"):
        path = Path(data_root_env)
        return path
    if os.getenv("K_SERVICE"):
        path = Path("/tmp/data")
        return path
    if Path("/app/data").exists():
        path = Path("/app/data")
        return path
    return project_root / "data"

DATA_ROOT = get_data_root()
PRECOMPUTED_FILE = DATA_ROOT / "structured" / "precomputed_scores.json"

SUPPORTED_TICKERS = [
    "NVDA", "MU", "AVGO", "TSM", "VRT", "SMCI", "INOD", "RR", "IREN",
    "CIFR", "RIOT", "OKLO", "SMR", "CCJ", "VST", "NXE", "EOSE", "QS"
]

def precompute_all_scores():
    """
    Compute scores for all supported tickers and save them to a JSON file.
    """
    print("🚀 Starting pre-computation of scores for all supported tickers...")
    all_scores = {}
    
    for ticker in SUPPORTED_TICKERS:
        print(f"Computing scores for {ticker}...")
        try:
            scores = compute_company_scores(ticker)
            # The result from compute_company_scores is a complex dictionary
            # that may contain non-serializable numpy types.
            # We need to sanitize it before saving to JSON.
            sanitized_scores = safe_json_serialize(scores)
            all_scores[ticker] = sanitized_scores
            print(f"✅ Successfully computed scores for {ticker}")
        except ScoreComputationError as e:
            print(f"❌ Error computing scores for {ticker}: {e}")
        except Exception as e:
            print(f"❌ An unexpected error occurred for {ticker}: {e}")

    # Ensure the directory exists
    PRECOMPUTED_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Save the pre-computed scores to the file
    with open(PRECOMPUTED_FILE, 'w') as f:
        json.dump(all_scores, f, indent=2)
        
    print(f"\n✨ Pre-computation complete!")
    print(f"Saved scores for {len(all_scores)} tickers to {PRECOMPUTED_FILE}")

if __name__ == "__main__":
    precompute_all_scores()
