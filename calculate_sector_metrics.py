#!/usr/bin/env python3
"""
Standalone script to calculate sector metrics.
"""

import sys
import os

# Add the parent directory to the path so we can import from fetch_data
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_data import calculate_sector_metrics, logger

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("SECTOR METRICS CALCULATION (STANDALONE)")
    logger.info("=" * 60)
    logger.info("")

    result = calculate_sector_metrics()

    if result:
        logger.info("")
        logger.info("=" * 60)
        logger.info("SECTOR METRICS CALCULATION COMPLETED SUCCESSFULLY!")
        logger.info("=" * 60)
    else:
        logger.error("Sector metrics calculation failed")
