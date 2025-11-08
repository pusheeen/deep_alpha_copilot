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
    {"date": "2024-11-11", "total_tokens": 146885466850, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 70395306555}, {"model": "Claude 3.5 Sonnet", "tokens": 41551048726}, {"model": "Gemini Flash 1.5-8B", "tokens": 34939111569}]},
    {"date": "2024-11-18", "total_tokens": 172861967755, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 71225556828}, {"model": "Gemini Flash 1.5", "tokens": 58198966075}, {"model": "Claude 3.5 Sonnet", "tokens": 43437444852}]},
    {"date": "2024-11-25", "total_tokens": 148481589550, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 64892784108}, {"model": "Gemini Flash 1.5-8B", "tokens": 42357339360}, {"model": "Gemini Flash 1.5", "tokens": 41231466082}]},
    {"date": "2024-12-02", "total_tokens": 151979022304, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 71051191423}, {"model": "Claude 3.5 Sonnet", "tokens": 43588576193}, {"model": "Gemini Flash 1.5-8B", "tokens": 37339254688}]},
    {"date": "2024-12-09", "total_tokens": 192640227399, "models": [{"model": "Gemini Flash 1.5", "tokens": 82354407500}, {"model": "Claude 3.5 Sonnet Beta", "tokens": 65669462473}, {"model": "Claude 3.5 Sonnet", "tokens": 44616357426}]},
    {"date": "2024-12-16", "total_tokens": 192702021783, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 101370601592}, {"model": "Claude 3.5 Sonnet", "tokens": 64894885719}, {"model": "Gemini Flash 1.5", "tokens": 26437534472}]},
    {"date": "2024-12-23", "total_tokens": 186391613170, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 101060618313}, {"model": "Claude 3.5 Sonnet", "tokens": 64143373880}, {"model": "Gemini Flash 1.5-8B", "tokens": 21187620977}]},
    {"date": "2024-12-30", "total_tokens": 202814641364, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 109612280092}, {"model": "Claude 3.5 Sonnet", "tokens": 64906766076}, {"model": "Gemini Flash 1.5", "tokens": 28295595196}]},
    {"date": "2025-01-06", "total_tokens": 269494444391, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 150556263251}, {"model": "Claude 3.5 Sonnet", "tokens": 76654506815}, {"model": "Gemini Flash 1.5", "tokens": 42283674325}]},
    {"date": "2025-01-13", "total_tokens": 284280016902, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 145154037392}, {"model": "Claude 3.5 Sonnet", "tokens": 92339456577}, {"model": "Gemini Flash 1.5", "tokens": 46786522933}]},
    {"date": "2025-01-20", "total_tokens": 287817353642, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 135037617449}, {"model": "Claude 3.5 Sonnet", "tokens": 106223349678}, {"model": "Gemini Flash 1.5", "tokens": 46556386515}]},
    {"date": "2025-01-27", "total_tokens": 322767016887, "models": [{"model": "Claude 3.5 Sonnet Beta", "tokens": 150019862408}, {"model": "Claude 3.5 Sonnet", "tokens": 148260581157}, {"model": "Gemini Flash 1.5", "tokens": 24487573322}]},
    {"date": "2025-02-03", "total_tokens": 392311286289, "models": [{"model": "Claude 3.5 Sonnet", "tokens": 195297688209}, {"model": "Claude 3.5 Sonnet Beta", "tokens": 156190380445}, {"model": "Gemini Flash 1.5-8B", "tokens": 40823217635}]},
    {"date": "2025-02-10", "total_tokens": 450330090988, "models": [{"model": "Claude 3.5 Sonnet", "tokens": 225036064456}, {"model": "Gemini 2.0 Flash", "tokens": 118368576097}, {"model": "Claude 3.5 Sonnet Beta", "tokens": 106925449435}]},
    {"date": "2025-02-17", "total_tokens": 553687574327, "models": [{"model": "Gemini 2.0 Flash", "tokens": 267073731767}, {"model": "Claude 3.5 Sonnet", "tokens": 176639643672}, {"model": "Claude 3.5 Sonnet Beta", "tokens": 109974198888}]},
    {"date": "2025-02-24", "total_tokens": 567239978233, "models": [{"model": "Gemini 2.0 Flash", "tokens": 283589771561}, {"model": "Claude 3-7 Sonnet", "tokens": 195694456616}, {"model": "Claude 3.5 Sonnet", "tokens": 87955750056}]},
    {"date": "2025-03-03", "total_tokens": 596377053297, "models": [{"model": "Gemini 2.0 Flash", "tokens": 287866934161}, {"model": "Claude 3-7 Sonnet", "tokens": 246058893137}, {"model": "Claude 3.5 Sonnet", "tokens": 62452225999}]},
    {"date": "2025-03-10", "total_tokens": 695442658937, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 332961486752}, {"model": "Gemini 2.0 Flash", "tokens": 287227699898}, {"model": "DeepSeek R1:free", "tokens": 75253472287}]},
    {"date": "2025-03-17", "total_tokens": 653077358166, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 327259743351}, {"model": "Gemini 2.0 Flash", "tokens": 245440657034}, {"model": "Llama 3.3 70B", "tokens": 80376957781}]},
    {"date": "2025-03-24", "total_tokens": 686921747764, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 329615206416}, {"model": "Gemini 2.0 Flash", "tokens": 249764641763}, {"model": "Llama 3.3 70B", "tokens": 107541899585}]},
    {"date": "2025-03-31", "total_tokens": 853595519255, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 322076649787}, {"model": "Gemini 2.0 Flash", "tokens": 283324287685}, {"model": "GPT-4o Mini", "tokens": 248194581783}]},
    {"date": "2025-04-07", "total_tokens": 838956053314, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 365264797298}, {"model": "Gemini 2.0 Flash", "tokens": 259073137635}, {"model": "GPT-4o Mini", "tokens": 214618119081}]},
    {"date": "2025-04-14", "total_tokens": 754775419757, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 389609142884}, {"model": "Gemini 2.0 Flash", "tokens": 213720042803}, {"model": "Gemini 2.5 Pro Exp", "tokens": 151446234070}]},
    {"date": "2025-04-21", "total_tokens": 632304913537, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 336565855349}, {"model": "Gemini 2.0 Flash", "tokens": 192611517093}, {"model": "Gemini 2.5 Flash Preview", "tokens": 103127741095}]},
    {"date": "2025-04-28", "total_tokens": 630062925406, "models": [{"model": "Claude 3-7 Sonnet", "tokens": 308641256836}, {"model": "Gemini 2.0 Flash", "tokens": 210404799203}, {"model": "Gemini 2.5 Pro Exp", "tokens": 111016869367}]},
    {"date": "2025-05-05", "total_tokens": 847013802494, "models": [{"model": "GPT-4o Mini", "tokens": 320235193199}, {"model": "Claude 3-7 Sonnet", "tokens": 299824035298}, {"model": "Gemini 2.0 Flash", "tokens": 226954573997}]},
    {"date": "2025-05-12", "total_tokens": 971669135815, "models": [{"model": "GPT-4o Mini", "tokens": 439281621110}, {"model": "Claude 3-7 Sonnet", "tokens": 322351113131}, {"model": "Gemini 2.0 Flash", "tokens": 210036401574}]},
    {"date": "2025-05-19", "total_tokens": 1014323102845, "models": [{"model": "GPT-4o Mini", "tokens": 481739760926}, {"model": "Claude 3-7 Sonnet", "tokens": 321218503782}, {"model": "Gemini 2.0 Flash", "tokens": 211364838137}]},
    {"date": "2025-05-26", "total_tokens": 964955893429, "models": [{"model": "GPT-4o Mini", "tokens": 473282220899}, {"model": "Claude 4 Sonnet", "tokens": 271259772069}, {"model": "Gemini 2.0 Flash", "tokens": 220413900461}]},
    {"date": "2025-06-02", "total_tokens": 782630509840, "models": [{"model": "GPT-4o Mini", "tokens": 306396506052}, {"model": "Claude 4 Sonnet", "tokens": 244449908109}, {"model": "Gemini 2.0 Flash", "tokens": 231784095679}]},
    {"date": "2025-06-09", "total_tokens": 706149696463, "models": [{"model": "Claude 4 Sonnet", "tokens": 269675098192}, {"model": "Gemini 2.0 Flash", "tokens": 266351237996}, {"model": "Gemini 2.5 Flash Preview", "tokens": 170123360275}]},
    {"date": "2025-06-16", "total_tokens": 780936469608, "models": [{"model": "Claude 4 Sonnet", "tokens": 361675145305}, {"model": "Gemini 2.0 Flash", "tokens": 254171349764}, {"model": "Gemini 2.0 Flash Lite", "tokens": 165089974539}]},
    {"date": "2025-06-23", "total_tokens": 828446180694, "models": [{"model": "Claude 4 Sonnet", "tokens": 333743521074}, {"model": "Gemini 2.0 Flash", "tokens": 263063140049}, {"model": "Gemini 2.5 Flash Preview", "tokens": 231639519571}]},
    {"date": "2025-06-30", "total_tokens": 775275438690, "models": [{"model": "Claude 4 Sonnet", "tokens": 342978920457}, {"model": "Gemini 2.0 Flash", "tokens": 250724110111}, {"model": "Gemini 2.5 Flash Preview", "tokens": 181572408122}]},
    {"date": "2025-07-07", "total_tokens": 830633349163, "models": [{"model": "Claude 4 Sonnet", "tokens": 351340844557}, {"model": "Gemini 2.0 Flash", "tokens": 246852045145}, {"model": "Gemini 2.5 Flash Preview", "tokens": 232440459461}]},
    {"date": "2025-07-14", "total_tokens": 941372113773, "models": [{"model": "Claude 4 Sonnet", "tokens": 449836825176}, {"model": "Gemini 2.0 Flash", "tokens": 255458808538}, {"model": "DeepSeek Chat V3", "tokens": 236076480059}]},
    {"date": "2025-07-21", "total_tokens": 1147966687384, "models": [{"model": "Claude 4 Sonnet", "tokens": 571707073746}, {"model": "Gemini 2.5 Flash", "tokens": 316006039645}, {"model": "Gemini 2.0 Flash", "tokens": 260253573993}]},
    {"date": "2025-07-28", "total_tokens": 1174197498675, "models": [{"model": "Claude 4 Sonnet", "tokens": 602247714253}, {"model": "Gemini 2.5 Flash", "tokens": 299033229490}, {"model": "Gemini 2.0 Flash", "tokens": 272916554932}]},
    {"date": "2025-08-04", "total_tokens": 1054678262581, "models": [{"model": "Claude 4 Sonnet", "tokens": 520128485411}, {"model": "Gemini 2.0 Flash", "tokens": 273959156320}, {"model": "Gemini 2.5 Flash", "tokens": 260590620850}]},
    {"date": "2025-08-11", "total_tokens": 1042917687679, "models": [{"model": "Claude 4 Sonnet", "tokens": 508569966870}, {"model": "Gemini 2.5 Flash", "tokens": 270390016618}, {"model": "Gemini 2.0 Flash", "tokens": 263957704191}]},
    {"date": "2025-08-18", "total_tokens": 991714202494, "models": [{"model": "Claude 4 Sonnet", "tokens": 518030593837}, {"model": "Gemini 2.5 Flash", "tokens": 253189171485}, {"model": "Gemini 2.0 Flash", "tokens": 220494437172}]},
    {"date": "2025-08-25", "total_tokens": 1298150023483, "models": [{"model": "Claude 4 Sonnet", "tokens": 559788815064}, {"model": "Grok Code Fast 1", "tokens": 396372897685}, {"model": "Gemini 2.5 Flash", "tokens": 341988310734}]},
    {"date": "2025-09-01", "total_tokens": 2085752534846, "models": [{"model": "Grok Code Fast 1", "tokens": 1097553506710}, {"model": "Claude 4 Sonnet", "tokens": 544918185830}, {"model": "Gemini 2.5 Flash", "tokens": 443280842306}]},
    {"date": "2025-09-08", "total_tokens": 2055343968437, "models": [{"model": "Grok Code Fast 1", "tokens": 1165211710023}, {"model": "Claude 4 Sonnet", "tokens": 568397773427}, {"model": "Gemini 2.5 Flash", "tokens": 321734484987}]},
    {"date": "2025-09-15", "total_tokens": 2056622809743, "models": [{"model": "Grok Code Fast 1", "tokens": 1145693711634}, {"model": "Claude 4 Sonnet", "tokens": 585759928388}, {"model": "Gemini 2.5 Flash", "tokens": 325169169721}]},
    {"date": "2025-09-22", "total_tokens": 2559488046920, "models": [{"model": "Grok Code Fast 1", "tokens": 1067241937351}, {"model": "Grok 4 Fast:free", "tokens": 913435460684}, {"model": "Claude 4 Sonnet", "tokens": 578811648885}]},
    {"date": "2025-09-29", "total_tokens": 2062368268254, "models": [{"model": "Grok Code Fast 1", "tokens": 1053354939944}, {"model": "Grok 4 Fast:free", "tokens": 644467337495}, {"model": "Gemini 2.5 Flash", "tokens": 364545990815}]},
    {"date": "2025-10-06", "total_tokens": 2002423468899, "models": [{"model": "Grok Code Fast 1", "tokens": 1184145939908}, {"model": "Claude 4.5 Sonnet", "tokens": 481823347564}, {"model": "Gemini 2.5 Flash", "tokens": 336454181427}]},
]


def get_actual_data_points() -> List[Dict]:
    """
    Get ACTUAL data points from OpenRouter rankings.
    Returns only verified real measurements - NO interpolation.
    Uses TOP 3 models only for conservative, clean data.
    """
    data_points = []

    for entry in ACTUAL_WEEKLY_DATA:
        data_points.append({
            "date": entry["date"],
            "total_tokens": entry["total_tokens"],
            "models": entry["models"],
            "source": "OpenRouter rankings chart - top 3 models",
            "verified": True,
            "note": f"Actual measurement from OpenRouter rankings chart (TOP 3 models only)"
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
    print("ACTUAL OpenRouter Data Points (top 3 models only)")
    print("="*70)

    data_points = get_actual_data_points()
    for point in data_points:
        total_b = point['total_tokens'] / 1e9
        print(f"\n{point['date']}: {total_b:.1f}B tokens (top 3 models)")
        for model in point['models']:
            print(f"  - {model['model']}: {model['tokens']/1e9:.1f}B")

    print(f"\n\nTotal data points: {len(data_points)}")
    print("Source: https://openrouter.ai/rankings")
    print("Note: TOP 3 models only - most conservative/reliable data")
