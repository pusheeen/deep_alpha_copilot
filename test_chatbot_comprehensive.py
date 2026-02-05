#!/usr/bin/env python3
"""
Comprehensive chatbot test suite.
Tests various query types to ensure the chatbot works correctly.
"""
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

# Test scenarios covering different query types
TEST_SCENARIOS = [
    {
        "name": "Momentum Query",
        "question": "What is the momentum of NVDA?",
        "expected_keywords": ["momentum", "NVDA", "technical", "score"],
        "ticker": "NVDA"
    },
    {
        "name": "Sentiment Query",
        "question": "What's the sentiment for AMD?",
        "expected_keywords": ["sentiment", "AMD"],
        "ticker": "AMD"
    },
    {
        "name": "Investment Recommendation",
        "question": "Should I buy MU?",
        "expected_keywords": ["buy", "MU", "recommendation", "score"],
        "ticker": "MU"
    },
    {
        "name": "News Query",
        "question": "What's the latest news about AVGO?",
        "expected_keywords": ["news", "AVGO", "latest"],
        "ticker": "AVGO"
    },
    {
        "name": "Financial Health Query",
        "question": "What is TSM's financial health?",
        "expected_keywords": ["financial", "TSM", "health", "score"],
        "ticker": "TSM"
    },
    {
        "name": "Risk Analysis",
        "question": "What are the risks for ORCL?",
        "expected_keywords": ["risk", "ORCL", "concern"],
        "ticker": "ORCL"
    },
    {
        "name": "General Company Query",
        "question": "Tell me about NVDA",
        "expected_keywords": ["NVDA", "score", "recommendation"],
        "ticker": "NVDA"
    },
    {
        "name": "Flow Data Query",
        "question": "What is the institutional flow for AMD?",
        "expected_keywords": ["flow", "AMD", "institutional"],
        "ticker": "AMD"
    }
]

def test_chat_query(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single chat query scenario."""
    print(f"\n{'='*60}")
    print(f"Testing: {scenario['name']}")
    print(f"Question: {scenario['question']}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "question": scenario["question"],
                "include_reasoning": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            answer = data.get('answer', '').lower()
            status = data.get('status', 'unknown')
            
            # Check if answer contains expected keywords
            found_keywords = []
            missing_keywords = []
            for keyword in scenario.get('expected_keywords', []):
                if keyword.lower() in answer:
                    found_keywords.append(keyword)
                else:
                    missing_keywords.append(keyword)
            
            # Check if ticker is mentioned (if applicable)
            ticker_mentioned = False
            if scenario.get('ticker'):
                ticker_mentioned = scenario['ticker'].upper() in answer.upper()
            
            # Determine success
            success = (
                status == 'success' and
                len(found_keywords) >= len(scenario.get('expected_keywords', [])) * 0.5 and  # At least 50% of keywords
                (not scenario.get('ticker') or ticker_mentioned)  # Ticker mentioned if expected
            )
            
            print(f"✅ Status: {status}")
            print(f"📝 Answer (first 200 chars): {answer[:200]}...")
            print(f"🔑 Found keywords: {found_keywords}")
            if missing_keywords:
                print(f"⚠️  Missing keywords: {missing_keywords}")
            if scenario.get('ticker'):
                print(f"📊 Ticker mentioned: {ticker_mentioned}")
            
            return {
                "success": success,
                "status": status,
                "answer_length": len(answer),
                "found_keywords": len(found_keywords),
                "total_keywords": len(scenario.get('expected_keywords', [])),
                "ticker_mentioned": ticker_mentioned if scenario.get('ticker') else None,
                "data": data
            }
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"Response: {response.text[:200]}")
            return {
                "success": False,
                "error": f"HTTP {response.status_code}",
                "response": response.text
            }
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server. Is it running?")
        return {"success": False, "error": "Connection refused"}
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out")
        return {"success": False, "error": "Timeout"}
    except Exception as e:
        print(f"❌ Error: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def main():
    """Run comprehensive chatbot tests."""
    print("🤖 Comprehensive Chatbot Test Suite")
    print("="*60)
    print(f"Testing against: {BASE_URL}")
    print("="*60)
    
    results = []
    for scenario in TEST_SCENARIOS:
        result = test_chat_query(scenario)
        results.append({
            "scenario": scenario["name"],
            **result
        })
        print()
    
    # Summary
    print("="*60)
    print("Test Summary")
    print("="*60)
    
    successful = sum(1 for r in results if r.get("success"))
    total = len(results)
    
    print(f"✅ Passed: {successful}/{total}")
    print(f"❌ Failed: {total - successful}/{total}")
    print()
    
    # Detailed results
    for result in results:
        status_icon = "✅" if result.get("success") else "❌"
        print(f"{status_icon} {result['scenario']}: {result.get('status', 'unknown')}")
        if result.get('found_keywords') is not None:
            print(f"   Keywords: {result.get('found_keywords')}/{result.get('total_keywords', 0)} found")
        if result.get('error'):
            print(f"   Error: {result['error']}")
    
    print()
    
    if successful == total:
        print("🎉 All tests passed! Chatbot is working correctly.")
        return 0
    elif successful >= total * 0.7:  # 70% pass rate
        print("⚠️  Most tests passed. Chatbot is mostly working.")
        return 0
    else:
        print("❌ Many tests failed. Review the chatbot implementation.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
