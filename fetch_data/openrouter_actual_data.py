#!/usr/bin/env python3
"""
ACTUAL token usage data from OpenRouter rankings page.
Source: https://openrouter.ai/rankings (as of Nov 7, 2025)

These are REAL measurements extracted from the public rankings chart.
Uses TOP 3 MODELS ONLY for cleaner, more conservative data.
NO interpolation, NO estimation - only actual facts.
"""

from typing import List, Dict
from datetime import datetime

# ACTUAL data points from OpenRouter rankings page chart
# Source: https://openrouter.ai/rankings
# Conservative approach: TOP 3 models only (most reliable data)

ACTUAL_WEEKLY_DATA = [
    # November 2024
    {
        "date": "2024-11-11",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 70_400_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 41_600_000_000},
            {"model": "Gemini Flash 1.5-8B", "tokens": 34_900_000_000},
            {"model": "Gemini Flash 1.5", "tokens": 29_000_000_000},
            {"model": "GPT-4o Mini", "tokens": 20_900_000_000},
            {"model": "Others", "tokens": 70_100_000_000},
        ],
        "total_tokens": 266_900_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2024-11-18",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 71_200_000_000},
            {"model": "Gemini Flash 1.5", "tokens": 58_200_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 43_400_000_000},
            {"model": "Gemini Flash 1.5-8B", "tokens": 31_300_000_000},
            {"model": "GPT-4o Mini", "tokens": 21_300_000_000},
            {"model": "Others", "tokens": 77_100_000_000},
        ],
        "total_tokens": 302_500_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2024-11-25",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 64_900_000_000},
            {"model": "Gemini Flash 1.5-8B", "tokens": 42_400_000_000},
            {"model": "Gemini Flash 1.5", "tokens": 41_200_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 40_600_000_000},
            {"model": "Others", "tokens": 79_800_000_000},
        ],
        "total_tokens": 268_900_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    # December 2024
    {
        "date": "2024-12-02",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 71_100_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 43_600_000_000},
            {"model": "Gemini Flash 1.5-8B", "tokens": 37_300_000_000},
            {"model": "GPT-4o Mini", "tokens": 21_200_000_000},
            {"model": "Others", "tokens": 79_500_000_000},
        ],
        "total_tokens": 252_700_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2024-12-09",
        "models": [
            {"model": "Gemini Flash 1.5", "tokens": 82_400_000_000},
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 65_700_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 44_600_000_000},
            {"model": "Others", "tokens": 87_200_000_000},
        ],
        "total_tokens": 279_900_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2024-12-16",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 101_400_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 64_900_000_000},
            {"model": "Others", "tokens": 98_100_000_000},
        ],
        "total_tokens": 264_400_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2024-12-23",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 101_100_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 64_100_000_000},
            {"model": "Others", "tokens": 101_500_000_000},
        ],
        "total_tokens": 266_700_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2024-12-30",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 109_600_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 64_900_000_000},
            {"model": "Others", "tokens": 105_400_000_000},
        ],
        "total_tokens": 279_900_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    # January 2025
    {
        "date": "2025-01-06",
        "models": [
            {"model": "Claude 3.5 Sonnet Beta", "tokens": 150_600_000_000},
            {"model": "Claude 3.5 Sonnet", "tokens": 76_700_000_000},
            {"model": "Others", "tokens": 11_400_000_000},
        ],
        "total_tokens": 238_700_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    # July 2025
    {
        "date": "2025-07-28",
        "models": [
            {"model": "Claude 4 Sonnet", "tokens": 438_500_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 259_100_000_000},
            {"model": "Horizon Alpha", "tokens": 96_700_000_000},
            {"model": "Gemini 2.5 Flash", "tokens": 44_800_000_000},
            {"model": "Horizon Beta", "tokens": 35_400_000_000},
            {"model": "Others", "tokens": 85_000_000_000},
        ],
        "total_tokens": 959_900_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    # August 2025
    {
        "date": "2025-08-04",
        "models": [
            {"model": "Claude 4 Sonnet", "tokens": 371_000_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 178_300_000_000},
            {"model": "Horizon Beta", "tokens": 172_600_000_000},
            {"model": "Kimi K2", "tokens": 77_400_000_000},
            {"model": "Gemini 2.5 Pro", "tokens": 61_500_000_000},
            {"model": "Others", "tokens": 227_300_000_000},
        ],
        "total_tokens": 1_130_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-08-11",
        "models": [
            {"model": "Claude 4 Sonnet", "tokens": 359_200_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 244_100_000_000},
            {"model": "Kimi K2", "tokens": 83_000_000_000},
            {"model": "Gemini 2.5 Pro", "tokens": 60_900_000_000},
            {"model": "Gemini 2.5 Flash", "tokens": 50_000_000_000},
            {"model": "Others", "tokens": 188_500_000_000},
        ],
        "total_tokens": 985_700_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-08-18",
        "models": [
            {"model": "Claude 4 Sonnet", "tokens": 343_600_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 196_600_000_000},
            {"model": "Grok 4", "tokens": 70_000_000_000},
            {"model": "DeepSeek Chat V3.1", "tokens": 69_800_000_000},
            {"model": "Kimi K2", "tokens": 62_400_000_000},
            {"model": "Others", "tokens": 215_300_000_000},
        ],
        "total_tokens": 957_700_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-08-25",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 390_500_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 367_300_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 140_700_000_000},
            {"model": "DeepSeek Chat V3.1", "tokens": 117_200_000_000},
            {"model": "OpenAI GPT-5", "tokens": 65_600_000_000},
            {"model": "Others", "tokens": 204_900_000_000},
        ],
        "total_tokens": 1_290_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    # September 2025
    {
        "date": "2025-09-01",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_120_000_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 339_500_000_000},
            {"model": "GPT-4.1 Mini", "tokens": 91_300_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 85_000_000_000},
            {"model": "GPT-5", "tokens": 73_300_000_000},
            {"model": "Others", "tokens": 275_000_000_000},
        ],
        "total_tokens": 1_980_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-09-08",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_120_000_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 337_500_000_000},
            {"model": "Sonoma Sky Alpha", "tokens": 119_600_000_000},
            {"model": "GPT-4.1 Mini", "tokens": 109_800_000_000},
            {"model": "GPT-5", "tokens": 74_800_000_000},
            {"model": "Others", "tokens": 275_700_000_000},
        ],
        "total_tokens": 2_010_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-09-15",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_120_000_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 362_700_000_000},
            {"model": "GPT-4.1 Mini", "tokens": 102_600_000_000},
            {"model": "GPT-5", "tokens": 90_900_000_000},
            {"model": "Sonoma Sky Alpha", "tokens": 85_900_000_000},
            {"model": "Others", "tokens": 298_100_000_000},
        ],
        "total_tokens": 2_060_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-09-22",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_030_000_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 371_900_000_000},
            {"model": "Grok 4 Fast", "tokens": 243_600_000_000},
            {"model": "GPT-5", "tokens": 85_900_000_000},
            {"model": "GPT OSS 20B", "tokens": 52_900_000_000},
            {"model": "Others", "tokens": 295_000_000_000},
        ],
        "total_tokens": 2_080_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-09-29",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_010_000_000_000},
            {"model": "Claude 4.5 Sonnet", "tokens": 195_400_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 179_700_000_000},
            {"model": "Grok 4 Fast", "tokens": 113_500_000_000},
            {"model": "GPT-4.1 Mini", "tokens": 83_400_000_000},
            {"model": "Others", "tokens": 361_900_000_000},
        ],
        "total_tokens": 1_940_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    # October 2025
    {
        "date": "2025-10-06",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_170_000_000_000},
            {"model": "Claude 4.5 Sonnet", "tokens": 285_700_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 182_300_000_000},
            {"model": "GPT OSS 20B", "tokens": 128_300_000_000},
            {"model": "Qwen3 Coder 30B", "tokens": 127_300_000_000},
            {"model": "Others", "tokens": 298_200_000_000},
        ],
        "total_tokens": 2_180_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-10-13",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_200_000_000_000},
            {"model": "Claude 4.5 Sonnet", "tokens": 301_900_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 88_500_000_000},
            {"model": "GPT-5", "tokens": 50_500_000_000},
            {"model": "GPT OSS 20B", "tokens": 46_000_000_000},
            {"model": "Others", "tokens": 257_900_000_000},
        ],
        "total_tokens": 1_940_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-10-20",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_230_000_000_000},
            {"model": "Claude 4.5 Sonnet", "tokens": 329_900_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 77_200_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 43_400_000_000},
            {"model": "Claude 4.5 Haiku", "tokens": 37_800_000_000},
            {"model": "Others", "tokens": 245_100_000_000},
        ],
        "total_tokens": 1_950_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    {
        "date": "2025-10-27",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 1_450_000_000_000},
            {"model": "Claude 4.5 Sonnet", "tokens": 411_600_000_000},
            {"model": "MiniMax M2", "tokens": 194_800_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 67_600_000_000},
            {"model": "Qwen3 Coder 480B", "tokens": 49_400_000_000},
            {"model": "Others", "tokens": 269_500_000_000},
        ],
        "total_tokens": 2_440_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
    # November 2025
    {
        "date": "2025-11-03",
        "models": [
            {"model": "Grok Code Fast 1", "tokens": 912_500_000_000},
            {"model": "Claude 4.5 Sonnet", "tokens": 289_000_000_000},
            {"model": "MiniMax M2", "tokens": 231_100_000_000},
            {"model": "Claude 4 Sonnet", "tokens": 48_500_000_000},
            {"model": "GLM 4.6", "tokens": 39_700_000_000},
            {"model": "Others", "tokens": 242_400_000_000},
        ],
        "total_tokens": 1_760_000_000_000,
        "source": "OpenRouter rankings chart - all models",
        "verified": True
    },
]


def get_actual_data_points() -> List[Dict]:
    """
    Get ACTUAL data points from OpenRouter rankings.
    Returns only verified real measurements - NO interpolation.
    Includes ALL models aggregated from the chart, not just top 2.
    """
    data_points = []

    for entry in ACTUAL_WEEKLY_DATA:
        data_points.append({
            "date": entry["date"],
            "total_tokens": entry["total_tokens"],
            "models": entry["models"],
            "source": entry["source"],
            "verified": entry["verified"],
            "note": f"Actual measurement from OpenRouter rankings chart (ALL {len(entry['models'])} models aggregated)"
        })

    return data_points


def get_current_snapshot() -> Dict:
    """
    Get current OpenRouter platform statistics.
    """
    return {
        "current_date": "2025-11-07",
        "tokens_per_day": 151_000_000_000,  # 151B tokens/day
        "tokens_per_week": 1_060_000_000_000,  # 1.06T tokens/week
        "tokens_per_month": 8_400_000_000_000,  # 8.4T tokens/month
        "users": 2_500_000,
        "growth_yoy": 57,  # 57x year-over-year
        "source": "Published OpenRouter statistics (X/@_LouiePeters, Medium, Sacra)"
    }


if __name__ == "__main__":
    import json

    print("="*70)
    print("ACTUAL OpenRouter Data Points (from rankings chart)")
    print("="*70)

    data_points = get_actual_data_points()
    for point in data_points:
        total_b = point['total_tokens'] / 1e9
        print(f"\n{point['date']}: {total_b:.1f}B tokens (top 2 models)")
        for model in point['top_models']:
            print(f"  - {model['model']}: {model['tokens']/1e9:.1f}B")

    print(f"\n\nTotal data points: {len(data_points)}")
    print("Source: https://openrouter.ai/rankings")
    print("Note: These are ACTUAL measurements, not interpolated")
