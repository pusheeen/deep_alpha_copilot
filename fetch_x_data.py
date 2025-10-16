#!/usr/bin/env python3
"""
Standalone script to fetch X/Twitter data for all companies.
Searches for posts about each company and its CEO from the past 6 months.
"""

import sys
import os

# Add the parent directory to the path so we can import from fetch_data
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fetch_data import fetch_x_data, logger

if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("X/TWITTER DATA COLLECTION (STANDALONE)")
    logger.info("=" * 60)

    fetch_x_data()

    logger.info("")
    logger.info("=" * 60)
    logger.info("X DATA COLLECTION COMPLETED")
    logger.info("=" * 60)
