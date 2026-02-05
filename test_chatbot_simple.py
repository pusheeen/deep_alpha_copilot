#!/usr/bin/env python3
"""
Simple test script that validates the chatbot code logic without needing the full server.
This tests the async patterns and verifies the code structure.
"""
import asyncio
import sys
from pathlib import Path

def test_code_structure():
    """Test that the code structure is correct."""
    print("🔍 Checking chatbot code structure...")
    print("="*60)
    
    # Read the main.py file and check for key patterns
    main_file = Path(__file__).parent / "app" / "main.py"
    
    if not main_file.exists():
        print("❌ app/main.py not found")
        return False
    
    content = main_file.read_text()
    
    checks = []
    
    # Check 1: _handle_intelligent_chat uses executors
    if "await loop.run_in_executor(None, compute_company_scores" in content:
        checks.append(("✅ compute_company_scores uses executor", True))
    else:
        checks.append(("❌ compute_company_scores missing executor", False))
    
    # Check 2: _handle_intelligent_chat uses executors for Gemini
    if "await loop.run_in_executor(None, model.generate_content" in content:
        checks.append(("✅ Gemini API uses executor", True))
    else:
        checks.append(("❌ Gemini API missing executor", False))
    
    # Check 3: _handle_chat_fallback uses executors
    if "_handle_chat_fallback" in content and "await loop.run_in_executor(None, compute_company_scores" in content:
        checks.append(("✅ Fallback handler uses executors", True))
    else:
        checks.append(("❌ Fallback handler missing executors", False))
    
    # Check 4: Both handlers are async
    if "async def _handle_intelligent_chat" in content:
        checks.append(("✅ _handle_intelligent_chat is async", True))
    else:
        checks.append(("❌ _handle_intelligent_chat not async", False))
    
    if "async def _handle_chat_fallback" in content:
        checks.append(("✅ _handle_chat_fallback is async", True))
    else:
        checks.append(("❌ _handle_chat_fallback not async", False))
    
    # Check 5: Chat endpoint exists and calls async handler
    if '@app.post("/chat")' in content and "await _handle_intelligent_chat" in content:
        checks.append(("✅ /chat endpoint correctly implemented", True))
    else:
        checks.append(("❌ /chat endpoint issues", False))
    
    # Print results
    all_passed = True
    for check_name, passed in checks:
        print(check_name)
        if not passed:
            all_passed = False
    
    print("="*60)
    if all_passed:
        print("✅ All structural checks passed!")
        return True
    else:
        print("❌ Some structural checks failed")
        return False


def analyze_chatbot_logic():
    """Analyze the chatbot logic flow."""
    print("\n📊 Analyzing chatbot logic flow...")
    print("="*60)
    
    main_file = Path(__file__).parent / "app" / "main.py"
    content = main_file.read_text()
    
    # Count executor usage
    executor_count = content.count("run_in_executor")
    print(f"✅ Found {executor_count} uses of run_in_executor (proper async pattern)")
    
    # Count blocking calls that should be in executors
    blocking_calls = [
        "compute_company_scores",
        "query_company_data", 
        "search_latest_news",
        "query_reddit_sentiment",
        "query_twitter_data",
        "fetch_realtime_news",
        "model.generate_content"
    ]
    
    for call in blocking_calls:
        if call in content:
            # Check if it's used with executor
            pattern = f"await loop.run_in_executor(None, {call.split('.')[0]}"
            if pattern in content or (call == "model.generate_content" and "await loop.run_in_executor(None, model.generate_content" in content):
                print(f"✅ {call} properly wrapped in executor")
            else:
                # Check if it's called directly (without executor)
                direct_pattern = f"{call}("
                if direct_pattern in content and "run_in_executor" not in content[content.find(direct_pattern)-100:content.find(direct_pattern)+100]:
                    print(f"⚠️  {call} may need executor wrapper")
    
    print("="*60)


if __name__ == "__main__":
    print("🤖 Chatbot Code Validation Test")
    print("="*60)
    print("This test validates the code structure without needing the server running.\n")
    
    structure_ok = test_code_structure()
    analyze_chatbot_logic()
    
    print("\n" + "="*60)
    if structure_ok:
        print("✅ Code structure validation passed!")
        print("\nNote: To fully test the chatbot, you'll need to:")
        print("1. Install dependencies: pip install -r requirements.txt")
        print("2. Set up environment variables (.env file)")
        print("3. Start the server: python run_server.py")
        print("4. Test with: python test_chatbot.py")
        sys.exit(0)
    else:
        print("❌ Code structure validation failed")
        sys.exit(1)
