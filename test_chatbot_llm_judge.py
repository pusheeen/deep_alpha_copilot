"""
LLM Judge Test Cases for Chatbot
=================================

This file contains comprehensive test cases for evaluating the chatbot's responses.
The chatbot should be able to handle DIVERSE user queries, not just exact matches to these test cases.

Key Principle: The chatbot should understand USER INTENT and provide appropriate answers
based on available data, regardless of how the question is phrased.

Each test case includes:
- Query: Example user question (representative of a query pattern)
- Query Pattern: The underlying intent/pattern this represents
- Expected Answer Structure: What the answer should contain
- Variations: Other ways users might ask the same question

These tests are designed to be used with an LLM judge to evaluate chatbot quality.
"""

# ============================================================================
# INVESTMENT RECOMMENDATION QUERIES
# ============================================================================
# Pattern: Users asking for buy/sell/hold recommendations

INVESTMENT_RECOMMENDATION_TESTS = [
    {
        "query": "shall I buy MU?",
        "query_pattern": "direct_buy_recommendation",
        "variations": [
            "should I buy MU?",
            "is MU a good buy?",
            "would you recommend buying MU?",
            "should I invest in MU?",
            "is MU worth buying?",
            "can I buy MU?",
            "do you recommend MU?",
            "should I purchase MU?",
            "shall i buy MU ow",  # with typo
            "MU buy recommendation",
            "should i buy mu",  # lowercase
        ],
        "expected_answer_structure": {
            "type": "investment_recommendation",
            "required_sections": [
                {
                    "name": "reasoning",
                    "description": "Reasoning based on Deep Alpha Copilot evaluation pillars",
                    "required_content": [
                        "Overall score (0-10)",
                        "Evaluation pillars (business, financial, sentiment, technical, leadership)",
                        "Key metrics from each pillar",
                        "Valuation context (P/E ratio, relative valuation)"
                    ]
                },
                {
                    "name": "bull_case",
                    "description": "Bull case scenario with reasoning and assumptions",
                    "required_content": [
                        "Clear bull case narrative",
                        "Key assumptions driving bull case",
                        "Likelihood/probability of bull case assumptions",
                        "Specific catalysts that would validate bull case"
                    ]
                },
                {
                    "name": "bear_case",
                    "description": "Bear case scenario with reasoning and assumptions",
                    "required_content": [
                        "Clear bear case narrative",
                        "Key assumptions driving bear case",
                        "Likelihood/probability of bear case assumptions",
                        "Specific risks that would validate bear case"
                    ]
                },
                {
                    "name": "recommendation",
                    "description": "Clear investment recommendation",
                    "required_content": [
                        "Buy/Hold/Sell rating",
                        "Confidence level (High/Medium/Low)",
                        "Action (e.g., 'Buy now', 'Wait for pullback', 'Dollar-cost average')",
                        "Timing guidance"
                    ]
                }
            ]
        }
    },
    {
        "query": "is NVDA a good investment?",
        "query_pattern": "investment_quality_assessment",
        "variations": [
            "is NVDA worth investing in?",
            "should I invest in NVDA?",
            "NVDA investment advice",
            "would NVDA be a good investment?",
            "is investing in NVDA a good idea?",
        ]
    },
    {
        "query": "should I sell TSLA?",
        "query_pattern": "sell_recommendation",
        "variations": [
            "should I sell my TSLA shares?",
            "is it time to sell TSLA?",
            "should I exit TSLA?",
            "TSLA sell recommendation",
        ]
    },
    {
        "query": "hold or sell AAPL?",
        "query_pattern": "hold_vs_sell_decision",
        "variations": [
            "should I hold or sell AAPL?",
            "AAPL hold or sell?",
            "keep or sell AAPL?",
        ]
    }
]

# ============================================================================
# MOMENTUM / TECHNICAL ANALYSIS QUERIES
# ============================================================================
# Pattern: Users asking about price trends, momentum, technical indicators

MOMENTUM_TESTS = [
    {
        "query": "What is the momentum of NVDA?",
        "query_pattern": "momentum_analysis",
        "variations": [
            "how is NVDA's momentum?",
            "NVDA momentum",
            "what's NVDA's price momentum?",
            "is NVDA going up?",
            "NVDA trend analysis",
            "is NVDA trending up?",
            "NVDA price direction",
            "how is NVDA moving?",
            "NVDA technical momentum",
            "what direction is NVDA heading?",
        ],
        "expected_answer_structure": {
            "type": "momentum_analysis",
            "required_sections": [
                {
                    "name": "technical_score",
                    "description": "Technical/momentum score with explanation",
                    "required_content": [
                        "Technical score (0-10)",
                        "Recent price trends",
                        "Technical indicators (RSI, moving averages, volume)",
                        "Momentum direction (bullish/bearish/neutral)"
                    ]
                },
                {
                    "name": "recommendation",
                    "description": "Recommendation based on momentum",
                    "required_content": [
                        "Buy/Hold/Sell rating",
                        "Brief rationale based on technical analysis"
                    ]
                }
            ]
        }
    },
    {
        "query": "is MU going up?",
        "query_pattern": "price_direction",
        "variations": [
            "is MU trending up?",
            "MU going up?",
            "is MU rising?",
            "MU price trend",
        ]
    },
    {
        "query": "what's the technical analysis for AMD?",
        "query_pattern": "technical_analysis",
        "variations": [
            "AMD technical analysis",
            "technical indicators for AMD",
            "AMD chart analysis",
        ]
    }
]

# ============================================================================
# SENTIMENT QUERIES
# ============================================================================
# Pattern: Users asking about market sentiment, public opinion

SENTIMENT_TESTS = [
    {
        "query": "What's the sentiment for TSLA?",
        "query_pattern": "sentiment_analysis",
        "variations": [
            "how is TSLA sentiment?",
            "TSLA sentiment",
            "what's the market sentiment for TSLA?",
            "public sentiment on TSLA",
            "how do people feel about TSLA?",
            "TSLA sentiment analysis",
            "what's the mood on TSLA?",
            "TSLA outlook sentiment",
            "social sentiment for TSLA",
        ],
        "expected_answer_structure": {
            "type": "sentiment_analysis",
            "required_sections": [
                {
                    "name": "sentiment_sources",
                    "description": "Sentiment from multiple sources",
                    "required_content": [
                        "Reddit sentiment (if available)",
                        "Twitter/X sentiment (if available)",
                        "Number of posts/mentions analyzed"
                    ]
                },
                {
                    "name": "sentiment_score",
                    "description": "Overall sentiment score",
                    "required_content": [
                        "Sentiment score (0-10)",
                        "Description (very positive/moderately positive/neutral/negative)",
                        "Overall Deep Alpha score (0-10)"
                    ]
                }
            ]
        }
    },
    {
        "query": "how is the market feeling about NVDA?",
        "query_pattern": "market_sentiment",
        "variations": [
            "market sentiment NVDA",
            "what's the market outlook for NVDA?",
        ]
    }
]

# ============================================================================
# NEWS QUERIES
# ============================================================================
# Pattern: Users asking about recent news, events, developments

NEWS_TESTS = [
    {
        "query": "What's the latest news for AAPL?",
        "query_pattern": "latest_news",
        "variations": [
            "AAPL latest news",
            "recent news on AAPL",
            "what's happening with AAPL?",
            "AAPL news",
            "any news on AAPL?",
            "what's new with AAPL?",
            "recent developments AAPL",
            "latest AAPL updates",
            "what happened to AAPL recently?",
        ],
        "expected_answer_structure": {
            "type": "news_summary",
            "required_sections": [
                {
                    "name": "news_summary",
                    "description": "Latest news summary",
                    "required_content": [
                        "Headline or main news theme",
                        "Number of recent articles found",
                        "Top headline(s)",
                        "Sentiment from news (if available)"
                    ]
                }
            ]
        }
    },
    {
        "query": "what happened to MU today?",
        "query_pattern": "recent_events",
        "variations": [
            "MU today",
            "MU recent events",
            "what's happening with MU?",
        ]
    }
]

# ============================================================================
# RISK ANALYSIS QUERIES
# ============================================================================
# Pattern: Users asking about risks, concerns, downsides

RISK_TESTS = [
    {
        "query": "What are the risks for GOOGL?",
        "query_pattern": "risk_analysis",
        "variations": [
            "GOOGL risks",
            "what risks does GOOGL have?",
            "concerns about GOOGL",
            "GOOGL downside risks",
            "what are the concerns with GOOGL?",
            "risks of investing in GOOGL",
            "GOOGL risk factors",
        ],
        "expected_answer_structure": {
            "type": "risk_analysis",
            "required_sections": [
                {
                    "name": "company_overview",
                    "description": "Basic company information",
                    "required_content": [
                        "Deep Alpha score",
                        "Recommendation rating"
                    ]
                },
                {
                    "name": "key_risks",
                    "description": "List of key risks",
                    "required_content": [
                        "Top 3-5 key risks",
                        "Brief explanation of each risk",
                        "Sector/industry-specific risks if applicable"
                    ]
                }
            ]
        }
    },
    {
        "query": "what are the concerns with TSLA?",
        "query_pattern": "concerns_analysis",
        "variations": [
            "TSLA concerns",
            "downside of TSLA",
        ]
    }
]

# ============================================================================
# FINANCIAL HEALTH QUERIES
# ============================================================================
# Pattern: Users asking about financial health, balance sheet, profitability

FINANCIAL_HEALTH_TESTS = [
    {
        "query": "How is the financial health of MSFT?",
        "query_pattern": "financial_health",
        "variations": [
            "MSFT financial health",
            "how healthy is MSFT financially?",
            "MSFT balance sheet",
            "MSFT financial condition",
            "is MSFT financially sound?",
            "MSFT profitability",
            "financial strength of MSFT",
        ],
        "expected_answer_structure": {
            "type": "financial_health_analysis",
            "required_sections": [
                {
                    "name": "company_overview",
                    "description": "Basic company information",
                    "required_content": [
                        "Deep Alpha score",
                        "Recommendation rating"
                    ]
                },
                {
                    "name": "financial_score",
                    "description": "Financial health score and analysis",
                    "required_content": [
                        "Financial score (0-10)",
                        "Brief explanation of financial health",
                        "Key financial metrics if relevant"
                    ]
                }
            ]
        }
    },
    {
        "query": "is NVDA financially stable?",
        "query_pattern": "financial_stability",
        "variations": [
            "NVDA financial stability",
            "NVDA balance sheet strength",
        ]
    }
]

# ============================================================================
# GENERAL COMPANY QUERIES
# ============================================================================
# Pattern: Users asking for general information, overview

GENERAL_COMPANY_TESTS = [
    {
        "query": "Tell me about AMD",
        "query_pattern": "company_overview",
        "variations": [
            "AMD overview",
            "information about AMD",
            "AMD analysis",
            "what can you tell me about AMD?",
            "AMD summary",
            "AMD company info",
            "describe AMD",
        ],
        "expected_answer_structure": {
            "type": "general_company_info",
            "required_sections": [
                {
                    "name": "company_overview",
                    "description": "Company information and scores",
                    "required_content": [
                        "Company name",
                        "Deep Alpha overall score",
                        "Recommendation rating",
                        "Brief company information"
                    ]
                }
            ]
        }
    },
    {
        "query": "what's MU's score?",
        "query_pattern": "score_query",
        "variations": [
            "MU score",
            "what score does MU have?",
            "MU rating",
            "MU overall score",
        ]
    }
]

# ============================================================================
# COMPARISON QUERIES
# ============================================================================
# Pattern: Users asking to compare stocks (may not be fully supported)

COMPARISON_TESTS = [
    {
        "query": "Should I buy NVDA or AMD?",
        "query_pattern": "stock_comparison",
        "variations": [
            "NVDA vs AMD",
            "which is better NVDA or AMD?",
            "compare NVDA and AMD",
            "NVDA or AMD which to buy?",
        ],
        "expected_answer_structure": {
            "type": "comparison_or_single_analysis",
            "note": "May handle by focusing on one ticker or providing analysis for each separately",
            "required_sections": [
                "At minimum, should extract one ticker and provide analysis",
                "Ideally would compare both, but may fall back to single ticker analysis"
            ]
        }
    }
]

# ============================================================================
# FLOW DATA QUERIES
# ============================================================================
# Pattern: Users asking about institutional/retail flow

FLOW_DATA_TESTS = [
    {
        "query": "what's the institutional flow for MU?",
        "query_pattern": "institutional_flow",
        "variations": [
            "MU institutional flow",
            "institutional ownership MU",
            "MU flow data",
        ]
    }
]

# ============================================================================
# COMBINE ALL TEST CASES
# ============================================================================

ALL_TEST_CASES = (
    INVESTMENT_RECOMMENDATION_TESTS +
    MOMENTUM_TESTS +
    SENTIMENT_TESTS +
    NEWS_TESTS +
    RISK_TESTS +
    FINANCIAL_HEALTH_TESTS +
    GENERAL_COMPANY_TESTS +
    COMPARISON_TESTS +
    FLOW_DATA_TESTS
)

# ============================================================================
# EVALUATION CRITERIA FOR LLM JUDGE
# ============================================================================

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
        ],
        "principle": "The chatbot should be flexible and understand user intent, not require exact query matches"
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
        ],
        "principle": "The chatbot should understand intent, not match exact patterns"
    }
}

# ============================================================================
# SCORING RUBRIC FOR LLM JUDGE
# ============================================================================

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

# ============================================================================
# TESTING PRINCIPLES
# ============================================================================

TESTING_PRINCIPLES = """
The chatbot should be evaluated based on its ability to:

1. UNDERSTAND USER INTENT: The chatbot should understand what the user is asking for,
   regardless of how the question is phrased. It should not require exact keyword matches.

2. HANDLE DIVERSE QUERIES: Users will phrase questions in many different ways. The chatbot
   should handle variations in:
   - Question format (should/can/is/would/do)
   - Formality (casual vs formal language)
   - Structure (questions vs statements)
   - Typos and extra words
   - Lowercase/uppercase

3. USE AVAILABLE DATA: When data is available to answer a question, the chatbot should use it
   rather than returning generic responses.

4. PROVIDE APPROPRIATE ANSWERS: The answer should match the query type:
   - Investment recommendations should include bull/bear cases
   - Momentum queries should include technical analysis
   - Sentiment queries should include sentiment scores
   - News queries should include recent news
   - Risk queries should list key risks

5. BE FLEXIBLE NOT RIGID: The chatbot should understand semantic meaning, not match exact
   patterns. It should handle any reasonable variation of these query types.
"""

if __name__ == "__main__":
    print("Chatbot LLM Judge Test Cases")
    print("=" * 60)
    print(f"\nTotal test case groups: 9")
    print(f"Total test cases: {len(ALL_TEST_CASES)}")
    print("\nTest Categories:")
    print(f"  1. Investment Recommendation: {len(INVESTMENT_RECOMMENDATION_TESTS)} cases")
    print(f"  2. Momentum/Technical: {len(MOMENTUM_TESTS)} cases")
    print(f"  3. Sentiment: {len(SENTIMENT_TESTS)} cases")
    print(f"  4. News: {len(NEWS_TESTS)} cases")
    print(f"  5. Risk Analysis: {len(RISK_TESTS)} cases")
    print(f"  6. Financial Health: {len(FINANCIAL_HEALTH_TESTS)} cases")
    print(f"  7. General Company: {len(GENERAL_COMPANY_TESTS)} cases")
    print(f"  8. Comparison: {len(COMPARISON_TESTS)} cases")
    print(f"  9. Flow Data: {len(FLOW_DATA_TESTS)} cases")
    print("\n" + TESTING_PRINCIPLES)
