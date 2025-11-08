#!/usr/bin/env python3
"""
CLI wrapper to fetch OpenRouter model catalog and save to timestamped JSON files.
Uses modular fetch_data/token_usage.py implementation.
"""

from dotenv import load_dotenv
load_dotenv()

import json
import os
from datetime import datetime
import logging

from fetch_data.token_usage import fetch_openrouter_model_catalog

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Directory for token usage data
TOKEN_USAGE_DIR = "data/unstructured/token_usage"
os.makedirs(TOKEN_USAGE_DIR, exist_ok=True)


def save_model_catalog(catalog: dict):
    """Save model catalog to timestamped JSON file."""
    now = datetime.now()
    date_str = now.strftime('%Y%m%d_%H%M%S')

    filename = f"openrouter_model_catalog_{date_str}.json"
    filepath = os.path.join(TOKEN_USAGE_DIR, filename)

    with open(filepath, 'w') as f:
        json.dump(catalog, f, indent=2)

    logger.info(f"✅ Saved model catalog to {filepath}")
    return filepath


def main():
    """Main function to fetch and save model catalogs."""
    views = ['trending', 'popular', 'new']

    for view in views:
        catalog = fetch_openrouter_model_catalog(view)
        save_model_catalog(catalog)
        logger.info(f"Processed view: {view}")
        logger.info("")


if __name__ == "__main__":
    main()
