#!/usr/bin/env python3
"""
Test script for the chatbot endpoint.
Tests the /chat endpoint with sample questions.
"""
import requests
import json
import sys
from typing import Dict, Any

BASE_URL = "http://localhost:8000"

def test_chat_question(question: str) -> Dict[str, Any]:
    """Test a single chat question."""
    print(f"\n{'='*60}")
    print(f"Testing: {question}")
    print(f"{'='*60}")
    
    try:
        response = requests.post(
            f"{BASE_URL}/chat",
            json={
                "question": question,
                "include_reasoning": False
            },
            timeout=60
        )
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Status: {data.get('status', 'unknown')}")
            print(f"\nAnswer:\n{data.get('answer', 'No answer provided')}")
            
            if data.get('intent'):
                print(f"\nIntent: {data.get('intent')}")
            if data.get('ticker'):
                print(f"Ticker: {data.get('ticker')}")
            
            return {"success": True, "data": data}
        else:
            print(f"❌ Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return {"success": False, "error": f"HTTP {response.status_code}", "response": response.text}
            
    except requests.exceptions.ConnectionError:
        print("❌ Error: Could not connect to server. Is it running?")
        print("   Start the server with: python run_server.py")
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
    """Run chatbot tests."""
    print("🤖 Chatbot Test Suite")
    print("="*60)
    
    # Test questions
    test_questions = [
        "What is the momentum of NVDA?",
        "What's the sentiment for TSLA?",
    ]
    
    results = []
    for question in test_questions:
        result = test_chat_question(question)
        results.append(result)
        print("\n")
    
    # Summary
    print("="*60)
    print("Test Summary")
    print("="*60)
    successful = sum(1 for r in results if r.get("success"))
    total = len(results)
    print(f"✅ Passed: {successful}/{total}")
    print(f"❌ Failed: {total - successful}/{total}")
    
    if successful == total:
        print("\n🎉 All tests passed!")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
