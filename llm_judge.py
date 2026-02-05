"""
LLM Judge for Chatbot Evaluation
=================================

This module provides an LLM-based judge to evaluate chatbot responses.
Instead of hard-coded test cases, it uses an LLM to evaluate any query-response pair
based on comprehensive evaluation criteria.

Usage:
    judge = LLMJudge()
    result = judge.evaluate(
        query="shall I buy MU?",
        response="Based on Deep Alpha Copilot's evaluation..."
    )
"""

import os
import json
from typing import Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)

# Evaluation criteria that the LLM judge will use
EVALUATION_CRITERIA = {
    "intent_understanding": {
        "description": "Does the chatbot correctly understand the user's intent, regardless of phrasing?",
        "weight": "critical",
        "checklist": [
            "Extracts correct ticker symbol from query",
            "Identifies the underlying intent (recommendation, momentum, sentiment, news, etc.)",
            "Handles variations in phrasing (formal/casual, questions/statements)",
            "Handles typos and extra words gracefully",
            "Not rigidly tied to specific keywords - understands semantic meaning"
        ]
    },
    "ticker_extraction": {
        "description": "Did the chatbot correctly extract the stock ticker?",
        "weight": "high",
        "checklist": [
            "Ticker symbol is correctly identified",
            "Handles lowercase/uppercase variations",
            "Handles typos or extra words (e.g., 'MU ow' -> 'MU')",
            "Handles company names that map to tickers",
            "Ticker is validated against supported tickers list"
        ]
    },
    "content_completeness": {
        "description": "Does the answer include all required information for the query type?",
        "weight": "high",
        "checklist": [
            "All required sections for the query type are present",
            "Answer addresses the user's question directly",
            "No generic fallback responses when specific answer is possible",
            "Uses actual data from Deep Alpha Copilot (scores, metrics, recommendations)"
        ]
    },
    "investment_recommendation_quality": {
        "description": "For investment recommendations, is the analysis comprehensive?",
        "weight": "high",
        "checklist": [
            "Includes reasoning based on evaluation pillars (business, financial, sentiment, technical, leadership)",
            "Provides both bull case and bear case scenarios",
            "Includes likelihood/probability for scenarios",
            "Clear recommendation with action and timing",
            "Uses actual scores and metrics from Deep Alpha Copilot",
            "Addresses the specific question (buy/sell/hold)"
        ]
    },
    "data_utilization": {
        "description": "Does the chatbot effectively use available data to answer the question?",
        "weight": "high",
        "checklist": [
            "Leverages appropriate data sources (scores, news, sentiment, flow, etc.)",
            "Provides specific metrics and numbers where available",
            "Does not provide generic responses when data is available",
            "Uses multiple data sources when relevant to the query"
        ]
    },
    "accuracy": {
        "description": "Is the information accurate and factual?",
        "weight": "medium",
        "checklist": [
            "Scores are within valid ranges (0-10)",
            "Company names/tickers are correct",
            "Recommendations are consistent with scores",
            "Metrics and numbers are accurate"
        ]
    },
    "clarity": {
        "description": "Is the answer clear and well-structured?",
        "weight": "medium",
        "checklist": [
            "Answer is easy to read and understand",
            "Sections are clearly separated",
            "Professional tone appropriate for financial advice",
            "Structured format makes it easy to find information"
        ]
    },
    "flexibility": {
        "description": "Can the chatbot handle diverse query phrasings for the same intent?",
        "weight": "high",
        "checklist": [
            "Handles different question formats (should/can/is/would)",
            "Handles declarative statements vs questions",
            "Handles casual vs formal language",
            "Handles abbreviations and typos",
            "Provides appropriate answers regardless of exact wording"
        ]
    }
}

# Scoring rubric
SCORING_RUBRIC = {
    "excellent": {
        "score_range": (90, 100),
        "description": "Answer fully addresses the query with all required sections, accurate information, clear structure, and demonstrates flexibility in understanding diverse phrasings"
    },
    "good": {
        "score_range": (75, 89),
        "description": "Answer addresses most of the query requirements with minor gaps or issues, shows good intent understanding"
    },
    "fair": {
        "score_range": (60, 74),
        "description": "Answer partially addresses the query but missing some key sections or has accuracy issues, intent understanding may be limited"
    },
    "poor": {
        "score_range": (40, 59),
        "description": "Answer fails to properly address the query, returns generic response when specific answer is possible, or shows poor intent understanding"
    },
    "failed": {
        "score_range": (0, 39),
        "description": "Answer is completely incorrect, generic fallback, fails to extract ticker/intent, or demonstrates no understanding of user intent"
    }
}


@dataclass
class JudgeResult:
    """Result from LLM judge evaluation"""
    overall_score: float
    grade: str  # excellent, good, fair, poor, failed
    detailed_scores: Dict[str, float]  # Score for each criterion
    strengths: list[str]
    weaknesses: list[str]
    feedback: str
    extracted_ticker: Optional[str] = None
    detected_intent: Optional[str] = None


class LLMJudge:
    """
    LLM-based judge for evaluating chatbot responses.
    Uses an LLM to evaluate responses based on comprehensive criteria.
    """
    
    def __init__(self, model_name: str = "gemini-2.0-flash", api_key: Optional[str] = None):
        """
        Initialize the LLM judge.
        
        Args:
            model_name: LLM model to use for judging (default: gemini-2.0-flash)
            api_key: API key for the LLM (if None, uses environment variable)
        """
        self.model_name = model_name
        self.api_key = api_key or os.getenv("GEMINI_API_KEY") or os.getenv("OPENAI_API_KEY")
        
        # Try to import required libraries
        self.genai_available = False
        self.openai_available = False
        
        try:
            import google.generativeai as genai
            self.genai = genai
            self.genai_available = True
            if self.api_key and "gemini" in model_name.lower():
                genai.configure(api_key=self.api_key)
        except ImportError:
            logger.warning("google.generativeai not available, will try OpenAI")
        
        try:
            import openai
            self.openai = openai
            self.openai_available = True
        except ImportError:
            logger.warning("openai not available")
    
    def _build_judge_prompt(self, query: str, response: str) -> str:
        """Build the prompt for the LLM judge"""
        
        criteria_text = "\n\n".join([
            f"**{name}** (Weight: {info['weight']})\n"
            f"Description: {info['description']}\n"
            f"Checklist:\n" + "\n".join(f"  - {item}" for item in info['checklist'])
            for name, info in EVALUATION_CRITERIA.items()
        ])
        
        rubric_text = "\n".join([
            f"- **{grade}** ({info['score_range'][0]}-{info['score_range'][1]}): {info['description']}"
            for grade, info in SCORING_RUBRIC.items()
        ])
        
        prompt = f"""You are an expert evaluator for a financial chatbot system. Your task is to evaluate how well the chatbot answered a user's question.

**User Query:**
"{query}"

**Chatbot Response:**
"{response}"

**Evaluation Criteria:**

{criteria_text}

**Scoring Rubric:**
{rubric_text}

**Your Task:**
1. Analyze the chatbot's response against all evaluation criteria
2. Determine what ticker (if any) was extracted from the query
3. Determine what intent the chatbot detected (investment_recommendation, momentum, sentiment, news, risk_analysis, financial_health, general, etc.)
4. Score each criterion (0-100)
5. Calculate an overall score (weighted average, with critical/high weights counting more)
6. Assign a grade (excellent/good/fair/poor/failed)
7. Identify strengths and weaknesses
8. Provide constructive feedback

**Output Format (JSON only):**
{{
    "overall_score": <float 0-100>,
    "grade": "<excellent|good|fair|poor|failed>",
    "detailed_scores": {{
        "intent_understanding": <float 0-100>,
        "ticker_extraction": <float 0-100>,
        "content_completeness": <float 0-100>,
        "investment_recommendation_quality": <float 0-100 or null if not applicable>,
        "data_utilization": <float 0-100>,
        "accuracy": <float 0-100>,
        "clarity": <float 0-100>,
        "flexibility": <float 0-100>
    }},
    "extracted_ticker": "<ticker symbol or null>",
    "detected_intent": "<intent type or null>",
    "strengths": ["strength1", "strength2", ...],
    "weaknesses": ["weakness1", "weakness2", ...],
    "feedback": "<detailed feedback paragraph>"
}}

Return ONLY the JSON object, no other text."""
        
        return prompt
    
    def _call_llm(self, prompt: str) -> str:
        """Call the LLM with the prompt"""
        
        # Try Gemini first if available
        if self.genai_available and ("gemini" in self.model_name.lower() or not self.openai_available):
            try:
                model = self.genai.GenerativeModel(self.model_name)
                response = model.generate_content(prompt)
                return response.text.strip()
            except Exception as e:
                logger.error(f"Gemini call failed: {e}")
                if self.openai_available:
                    logger.info("Falling back to OpenAI")
                else:
                    raise
        
        # Fallback to OpenAI
        if self.openai_available:
            try:
                client = self.openai.OpenAI(api_key=self.api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0.3,
                    max_tokens=2000
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"OpenAI call failed: {e}")
                raise
        
        raise RuntimeError("No LLM available. Please install google-generativeai or openai and set API keys.")
    
    def _parse_judge_response(self, llm_output: str) -> JudgeResult:
        """Parse the LLM judge's response into a JudgeResult"""
        
        # Extract JSON from response
        json_text = llm_output.strip()
        
        # Remove markdown code blocks if present
        if "```json" in json_text:
            json_text = json_text.split("```json")[1].split("```")[0].strip()
        elif "```" in json_text:
            json_text = json_text.split("```")[1].split("```")[0].strip()
        
        try:
            result_dict = json.loads(json_text)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse judge response: {e}")
            logger.error(f"Response was: {llm_output}")
            raise ValueError(f"Failed to parse judge response as JSON: {e}")
        
        return JudgeResult(
            overall_score=float(result_dict.get("overall_score", 0)),
            grade=result_dict.get("grade", "failed"),
            detailed_scores=result_dict.get("detailed_scores", {}),
            strengths=result_dict.get("strengths", []),
            weaknesses=result_dict.get("weaknesses", []),
            feedback=result_dict.get("feedback", ""),
            extracted_ticker=result_dict.get("extracted_ticker"),
            detected_intent=result_dict.get("detected_intent")
        )
    
    def evaluate(self, query: str, response: str) -> JudgeResult:
        """
        Evaluate a chatbot response to a user query.
        
        Args:
            query: The user's query/question
            response: The chatbot's response
            
        Returns:
            JudgeResult with scores, feedback, and analysis
        """
        logger.info(f"Evaluating query: {query[:50]}...")
        
        prompt = self._build_judge_prompt(query, response)
        
        try:
            llm_output = self._call_llm(prompt)
            result = self._parse_judge_response(llm_output)
            logger.info(f"Evaluation complete. Score: {result.overall_score:.1f}/100 ({result.grade})")
            return result
        except Exception as e:
            logger.error(f"Evaluation failed: {e}")
            raise
    
    def evaluate_batch(self, query_response_pairs: list[tuple[str, str]]) -> list[JudgeResult]:
        """
        Evaluate multiple query-response pairs.
        
        Args:
            query_response_pairs: List of (query, response) tuples
            
        Returns:
            List of JudgeResult objects
        """
        results = []
        for query, response in query_response_pairs:
            try:
                result = self.evaluate(query, response)
                results.append(result)
            except Exception as e:
                logger.error(f"Failed to evaluate query '{query[:50]}...': {e}")
                # Create a failed result
                results.append(JudgeResult(
                    overall_score=0,
                    grade="failed",
                    detailed_scores={},
                    strengths=[],
                    weaknesses=[f"Evaluation failed: {str(e)}"],
                    feedback=f"Evaluation error: {str(e)}",
                    extracted_ticker=None,
                    detected_intent=None
                ))
        return results
    
    def generate_report(self, results: list[JudgeResult], queries: Optional[list[str]] = None) -> str:
        """
        Generate a summary report from evaluation results.
        
        Args:
            results: List of JudgeResult objects
            queries: Optional list of queries (for reference in report)
            
        Returns:
            Formatted report string
        """
        if not results:
            return "No results to report."
        
        avg_score = sum(r.overall_score for r in results) / len(results)
        
        grade_counts = {}
        for result in results:
            grade_counts[result.grade] = grade_counts.get(result.grade, 0) + 1
        
        report = []
        report.append("=" * 60)
        report.append("CHATBOT EVALUATION REPORT")
        report.append("=" * 60)
        report.append(f"\nTotal Evaluations: {len(results)}")
        report.append(f"Average Score: {avg_score:.1f}/100")
        report.append(f"\nGrade Distribution:")
        for grade in ["excellent", "good", "fair", "poor", "failed"]:
            count = grade_counts.get(grade, 0)
            pct = (count / len(results)) * 100 if results else 0
            report.append(f"  {grade.capitalize()}: {count} ({pct:.1f}%)")
        
        report.append("\n" + "=" * 60)
        report.append("DETAILED RESULTS")
        report.append("=" * 60)
        
        for i, result in enumerate(results, 1):
            report.append(f"\n[{i}] Score: {result.overall_score:.1f}/100 ({result.grade.upper()})")
            if queries and i <= len(queries):
                report.append(f"Query: {queries[i-1][:80]}...")
            if result.extracted_ticker:
                report.append(f"Ticker: {result.extracted_ticker}")
            if result.detected_intent:
                report.append(f"Intent: {result.detected_intent}")
            if result.strengths:
                report.append(f"Strengths: {', '.join(result.strengths[:3])}")
            if result.weaknesses:
                report.append(f"Weaknesses: {', '.join(result.weaknesses[:3])}")
            report.append(f"Feedback: {result.feedback[:200]}...")
            report.append("-" * 60)
        
        return "\n".join(report)


def main():
    """Example usage"""
    import sys
    
    if len(sys.argv) < 3:
        print("Usage: python llm_judge.py <query> <response>")
        print("\nExample:")
        print('  python llm_judge.py "shall I buy MU?" "Based on Deep Alpha..."')
        sys.exit(1)
    
    query = sys.argv[1]
    response = sys.argv[2]
    
    judge = LLMJudge()
    result = judge.evaluate(query, response)
    
    print("\n" + "=" * 60)
    print("EVALUATION RESULT")
    print("=" * 60)
    print(f"\nOverall Score: {result.overall_score:.1f}/100")
    print(f"Grade: {result.grade.upper()}")
    print(f"\nExtracted Ticker: {result.extracted_ticker or 'None'}")
    print(f"Detected Intent: {result.detected_intent or 'None'}")
    print(f"\nStrengths:")
    for strength in result.strengths:
        print(f"  - {strength}")
    print(f"\nWeaknesses:")
    for weakness in result.weaknesses:
        print(f"  - {weakness}")
    print(f"\nDetailed Scores:")
    for criterion, score in result.detailed_scores.items():
        print(f"  {criterion}: {score:.1f}/100")
    print(f"\nFeedback:\n{result.feedback}")


if __name__ == "__main__":
    main()
