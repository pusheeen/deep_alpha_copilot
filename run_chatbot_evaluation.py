"""
Run chatbot evaluation with LLM judge
"""
import json
import sys
from llm_judge import LLMJudge
import logging
import requests
import time

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def test_chatbot_query(query: str, base_url: str = "http://localhost:8000") -> tuple[str, dict]:
    """Send a query to the chatbot and get the response."""
    try:
        response = requests.post(
            f"{base_url}/chat",
            json={"question": query},
            timeout=120
        )
        if response.status_code == 200:
            data = response.json()
            answer = data.get("answer", "No answer provided")
            return answer, data
        else:
            error_text = response.text
            return f"Error: HTTP {response.status_code} - {error_text}", {}
    except requests.exceptions.Timeout:
        return "Error: Request timed out", {}
    except Exception as e:
        logger.error(f"Error calling chatbot: {e}")
        return f"Error: {str(e)}", {}


def evaluate_chatbot():
    """Test chatbot and evaluate with LLM judge"""
    
    # Test queries - covering different intents
    test_queries = [
        "shall I buy MU?",
        "What is the momentum of NVDA?",
        "What's the sentiment for TSLA?",
        "What's the latest news for AAPL?",
        "What are the risks for GOOGL?",
    ]
    
    base_url = "http://localhost:8000"
    
    logger.info(f"Testing chatbot at {base_url}")
    logger.info(f"Testing {len(test_queries)} queries\n")
    
    # Create judge
    try:
        judge = LLMJudge()
        logger.info("LLM Judge initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize LLM judge: {e}")
        return
    
    results = []
    
    for i, query in enumerate(test_queries, 1):
        logger.info(f"\n{'='*60}")
        logger.info(f"[{i}/{len(test_queries)}] Query: {query}")
        logger.info('='*60)
        
        # Get chatbot response
        response, full_data = test_chatbot_query(query, base_url)
        
        if response.startswith("Error:"):
            logger.error(f"Chatbot error: {response}")
            results.append({
                "query": query,
                "response": response,
                "evaluation": None,
                "error": response
            })
            continue
        
        logger.info(f"Response ({len(response)} chars):")
        logger.info(f"{response[:200]}...")
        
        # Evaluate with LLM judge
        try:
            logger.info("\nEvaluating with LLM judge...")
            judge_result = judge.evaluate(query, response)
            
            logger.info(f"\nEvaluation Result:")
            logger.info(f"  Score: {judge_result.overall_score:.1f}/100")
            logger.info(f"  Grade: {judge_result.grade.upper()}")
            logger.info(f"  Extracted Ticker: {judge_result.extracted_ticker or 'None'}")
            logger.info(f"  Detected Intent: {judge_result.detected_intent or 'None'}")
            
            if judge_result.strengths:
                logger.info(f"  Strengths: {', '.join(judge_result.strengths[:3])}")
            if judge_result.weaknesses:
                logger.info(f"  Weaknesses: {', '.join(judge_result.weaknesses[:3])}")
            
            results.append({
                "query": query,
                "response": response,
                "full_response": full_data,
                "evaluation": {
                    "overall_score": judge_result.overall_score,
                    "grade": judge_result.grade,
                    "extracted_ticker": judge_result.extracted_ticker,
                    "detected_intent": judge_result.detected_intent,
                    "detailed_scores": judge_result.detailed_scores,
                    "strengths": judge_result.strengths,
                    "weaknesses": judge_result.weaknesses,
                    "feedback": judge_result.feedback
                }
            })
            
        except Exception as e:
            logger.error(f"Judge evaluation failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            results.append({
                "query": query,
                "response": response,
                "evaluation": None,
                "error": f"Judge evaluation failed: {str(e)}"
            })
    
    # Generate summary report
    logger.info(f"\n{'='*60}")
    logger.info("SUMMARY REPORT")
    logger.info('='*60)
    
    evaluated_results = [r for r in results if r.get("evaluation")]
    if evaluated_results:
        avg_score = sum(r["evaluation"]["overall_score"] for r in evaluated_results) / len(evaluated_results)
        logger.info(f"\nAverage Score: {avg_score:.1f}/100")
        
        grade_counts = {}
        for r in evaluated_results:
            grade = r["evaluation"]["grade"]
            grade_counts[grade] = grade_counts.get(grade, 0) + 1
        
        logger.info(f"\nGrade Distribution:")
        for grade in ["excellent", "good", "fair", "poor", "failed"]:
            count = grade_counts.get(grade, 0)
            pct = (count / len(evaluated_results)) * 100 if evaluated_results else 0
            logger.info(f"  {grade.capitalize()}: {count} ({pct:.1f}%)")
        
        # Detailed scores summary
        logger.info(f"\nDetailed Score Averages:")
        all_detailed_scores = {}
        for r in evaluated_results:
            for criterion, score in r["evaluation"]["detailed_scores"].items():
                if criterion not in all_detailed_scores:
                    all_detailed_scores[criterion] = []
                if score is not None:
                    all_detailed_scores[criterion].append(score)
        
        for criterion, scores in all_detailed_scores.items():
            if scores:
                avg = sum(scores) / len(scores)
                logger.info(f"  {criterion}: {avg:.1f}/100")
    
    # Save results to file
    output_file = "chatbot_evaluation_results.json"
    with open(output_file, 'w') as f:
        json.dump(results, f, indent=2)
    logger.info(f"\nDetailed results saved to {output_file}")
    
    # Print individual results
    logger.info(f"\n{'='*60}")
    logger.info("INDIVIDUAL RESULTS")
    logger.info('='*60)
    for i, result in enumerate(results, 1):
        logger.info(f"\n[{i}] Query: {result['query']}")
        if result.get("evaluation"):
            eval_data = result["evaluation"]
            logger.info(f"    Score: {eval_data['overall_score']:.1f}/100 ({eval_data['grade'].upper()})")
            logger.info(f"    Ticker: {eval_data['extracted_ticker'] or 'None'}")
            logger.info(f"    Intent: {eval_data['detected_intent'] or 'None'}")
        else:
            logger.info(f"    Error: {result.get('error', 'Unknown error')}")


if __name__ == "__main__":
    evaluate_chatbot()
