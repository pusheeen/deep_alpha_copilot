"""
Test Chatbot with LLM Judge
============================

This script tests the chatbot with various queries and uses the LLM judge to evaluate responses.
It demonstrates how to use the LLM judge without hard-coded test cases.
"""

import asyncio
import json
import sys
from llm_judge import LLMJudge, JudgeResult
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_chatbot_query(query: str, base_url: str = "http://localhost:8000") -> str:
    """
    Send a query to the chatbot and get the response.
    
    Args:
        query: User query
        base_url: Base URL of the chatbot API
        
    Returns:
        Chatbot response text
    """
    try:
        import aiohttp
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{base_url}/chat",
                json={"question": query},
                timeout=aiohttp.ClientTimeout(total=60)
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("answer", "No answer provided")
                else:
                    return f"Error: HTTP {response.status}"
    except ImportError:
        logger.error("aiohttp not installed. Install with: pip install aiohttp")
        return "Error: aiohttp not available"
    except Exception as e:
        logger.error(f"Error calling chatbot: {e}")
        return f"Error: {str(e)}"


async def test_chatbot_with_judge(
    queries: list[str],
    base_url: str = "http://localhost:8000",
    judge: Optional[LLMJudge] = None
) -> list[tuple[str, str, JudgeResult]]:
    """
    Test chatbot with multiple queries and evaluate with LLM judge.
    
    Args:
        queries: List of user queries to test
        base_url: Base URL of the chatbot API
        judge: LLM judge instance (if None, creates one)
        
    Returns:
        List of (query, response, judge_result) tuples
    """
    if judge is None:
        judge = LLMJudge()
    
    results = []
    
    for i, query in enumerate(queries, 1):
        logger.info(f"\n[{i}/{len(queries)}] Testing query: {query}")
        
        # Get chatbot response
        response = await test_chatbot_query(query, base_url)
        logger.info(f"Response received ({len(response)} chars)")
        
        # Evaluate with LLM judge
        try:
            judge_result = judge.evaluate(query, response)
            results.append((query, response, judge_result))
            
            logger.info(f"  Score: {judge_result.overall_score:.1f}/100 ({judge_result.grade})")
            logger.info(f"  Ticker: {judge_result.extracted_ticker or 'None'}")
            logger.info(f"  Intent: {judge_result.detected_intent or 'None'}")
        except Exception as e:
            logger.error(f"  Judge evaluation failed: {e}")
            # Create failed result
            from llm_judge import JudgeResult
            judge_result = JudgeResult(
                overall_score=0,
                grade="failed",
                detailed_scores={},
                strengths=[],
                weaknesses=[f"Judge evaluation failed: {str(e)}"],
                feedback=f"Error: {str(e)}",
                extracted_ticker=None,
                detected_intent=None
            )
            results.append((query, response, judge_result))
    
    return results


async def main():
    """Main function to run tests"""
    
    # Example queries - these can be any queries, not hard-coded
    example_queries = [
        "shall I buy MU?",
        "What is the momentum of NVDA?",
        "What's the sentiment for TSLA?",
        "What's the latest news for AAPL?",
        "What are the risks for GOOGL?",
        "How is the financial health of MSFT?",
        "Tell me about AMD",
    ]
    
    # You can also read queries from a file or accept them as arguments
    if len(sys.argv) > 1:
        # Read queries from file (one per line)
        with open(sys.argv[1], 'r') as f:
            example_queries = [line.strip() for line in f if line.strip()]
    
    base_url = sys.argv[2] if len(sys.argv) > 2 else "http://localhost:8000"
    
    logger.info(f"Testing chatbot at {base_url}")
    logger.info(f"Testing {len(example_queries)} queries\n")
    
    # Create judge
    judge = LLMJudge()
    
    # Test and evaluate
    results = await test_chatbot_with_judge(example_queries, base_url, judge)
    
    # Generate report
    queries = [r[0] for r in results]
    judge_results = [r[2] for r in results]
    report = judge.generate_report(judge_results, queries)
    
    print("\n" + report)
    
    # Save detailed results to file
    output_file = "chatbot_evaluation_results.json"
    output_data = []
    for query, response, judge_result in results:
        output_data.append({
            "query": query,
            "response": response,
            "score": judge_result.overall_score,
            "grade": judge_result.grade,
            "extracted_ticker": judge_result.extracted_ticker,
            "detected_intent": judge_result.detected_intent,
            "detailed_scores": judge_result.detailed_scores,
            "strengths": judge_result.strengths,
            "weaknesses": judge_result.weaknesses,
            "feedback": judge_result.feedback
        })
    
    with open(output_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"\nDetailed results saved to {output_file}")


if __name__ == "__main__":
    from typing import Optional
    asyncio.run(main())
