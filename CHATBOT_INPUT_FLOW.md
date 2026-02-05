# Chatbot Input Handling Flow

## Overview
This document explains how the chatbot currently handles and interprets user input.

## Current Flow Architecture

### 1. Entry Point: `/chat` Endpoint
Location: `app/main.py:2529`

The `/chat` endpoint receives user questions via POST request.

```2529:2571:app/main.py
@app.post("/chat")
async def chat(request: QueryRequest, http_request: Request):
    """
    Intelligent chatbot powered by Financial_Root_Agent (ADK) or Gemini fallback.
    Uses the ADK agent system when available, falls back to direct Gemini when not.
    """
    # Basic validation
    if not request.question or len(request.question.strip()) < 5:
        return {
            'answer': "Invalid query: Question seems too short to be meaningful",
            'status': 'validation_error'
        }

    # Try to use ADK root agent first (preferred architecture)
    if hasattr(http_request.app.state, 'agent_caller') and http_request.app.state.agent_caller:
        logger.info(f"Using root agent for query: {request.question[:50]}...")
        try:
            result = await http_request.app.state.agent_caller.call(
                request.question, 
                include_reasoning=request.include_reasoning
            )
            logger.info(f"Root agent returned status: {result.get('status')}")
            return result
        except Exception as e:
            logger.error(f"Root agent chat failed: {e}")
            import traceback
            logger.error(traceback.format_exc())
            # Fall through to fallback handler
    else:
        logger.warning("Root agent not available, using fallback handler")

    # Fallback: Use direct Gemini chatbot (when ADK not available)
    try:
        return await _handle_chat_fallback(request.question, request.include_reasoning)
    except Exception as e:
        logger.error(f"Chat fallback failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            'answer': f"I encountered an error processing your question. Please try rephrasing it or ask about a specific ticker (e.g., 'Should I buy MU?' or 'What is NVDA's momentum?').",
            'status': 'error',
            'error': str(e)
        }
```

**Flow Decision:**
1. **First Priority**: Try to use ADK `Financial_Root_Agent` via `agent_caller` (if available)
2. **Fallback**: If root agent fails or isn't available, use `_handle_chat_fallback`

### 2. Root Agent Path (ADK)
Location: `app/main.py:1458` (AgentCaller.call method)

When ADK is available, the root agent:
- Receives the raw user question
- Uses ADK's orchestration system to route to appropriate sub-agents
- Returns a structured response

**Current Status**: This path may not be working if:
- ADK is not initialized properly
- Root agent encounters an error
- Agent caller is None

### 3. Fallback Handler Path
Location: `app/main.py:2574` (`_handle_chat_fallback`)

This is the path currently being used based on the generic response you're seeing.

#### Step 1: Extract Ticker and Intent
```2574:2589:app/main.py
async def _handle_chat_fallback(question: str, include_reasoning: bool = False, ticker: str | None = None, intent: str | None = None) -> dict:
    """
    Fallback chatbot that uses tools directly without ADK.
    Uses LLM to extract ticker and intent if not already provided (to avoid duplicate calls).
    """
    question_lower = question.lower().strip()
    
    # Only extract if not already provided (avoids duplicate LLM calls)
    if ticker is None or intent is None:
        logger.info(f"Extracting ticker and intent from: {question[:50]}...")
        ticker, intent = await _extract_ticker_and_intent_with_llm(question)
        logger.info(f"Extracted ticker: {ticker}, intent: {intent}")
    if intent is None:
        intent = "general"
    
    logger.info(f"Processing fallback chat - ticker: {ticker}, intent: {intent}")
```

The function calls `_extract_ticker_and_intent_with_llm` which:
- Uses tiered LLM fallback: `gemini-2.0-flash` → `gemini-1.5-flash` → `gpt-4o-mini`
- Sends the user question to the LLM with a prompt asking to extract:
  - `ticker`: Stock ticker symbol (e.g., "MU", "NVDA")
  - `intent`: One of: "momentum", "sentiment", "news", "financials", "investment_recommendation", "general"
- Returns a tuple: `(ticker: str | None, intent: str)`

#### Step 2: Route Based on Extracted Data
After extraction, the handler routes to different logic based on intent and ticker:

1. **Momentum questions**: If intent="momentum" or keywords match
2. **Sentiment questions**: If intent="sentiment" or keywords match
3. **News questions**: If intent="news" or keywords match
4. **General company questions**: If ticker exists
5. **Default response**: If no ticker extracted or no handler matches

#### Step 3: Default Response (The Problem)
```2732:2742:app/main.py
        # Default response
        if ticker:
            return {
                'answer': f"I can help with questions about {ticker}. Try asking about momentum, sentiment, risks, financials, or latest news. For example: 'What is the sentiment of {ticker}?' or 'Does {ticker} have good momentum?'",
                'status': 'success'
            }
        else:
            return {
                'answer': "I can help answer questions about stocks. Please include a ticker symbol (e.g., NVDA, MU, AAPL) in your question. I can help with momentum, sentiment, risks, financials, and latest news.",
                'status': 'success'
            }
```

**This is exactly the response you're seeing!**

## Problem Analysis: "shall i buy MU ow"

For the question "shall i buy MU ow":

1. **Expected Behavior**: 
   - Ticker extraction should identify "MU" (Micron Technology)
   - Intent extraction should identify "investment_recommendation"
   - Handler should provide investment recommendation

2. **Actual Behavior**:
   - The generic response suggests that either:
     a. The LLM extraction failed to extract "MU" as the ticker
     b. The root agent path failed and fallback extraction is not working
     c. The ticker "MU" was extracted but filtered out (not in supported tickers list)
     d. The extraction is working but the routing logic doesn't handle "investment_recommendation" intent properly

3. **Potential Issues**:
   - **LLM Extraction Failure**: The typo "ow" at the end might confuse the LLM
   - **Ticker Validation**: If "MU" is not in the supported tickers list, it gets filtered to `None`
   - **Missing Investment Recommendation Handler**: The fallback handler may not have logic for "investment_recommendation" intent
   - **Root Agent Not Available**: If ADK isn't working, we're always using the fallback path

## Missing Handler for "investment_recommendation" Intent

Looking at the fallback handler code, I notice there's NO specific handler for `intent == "investment_recommendation"`. The handler only explicitly handles:
- `intent == "momentum"`
- `intent == "sentiment"`  
- `intent == "news"`
- General company questions (if ticker exists)

**This means questions asking "should I buy X?" or "shall I buy X?" fall through to the default response even if the ticker is correctly extracted!**

## Next Steps to Fix

1. **Add investment recommendation handler** to `_handle_chat_fallback`
2. **Verify ticker extraction** is working (check logs)
3. **Ensure MU is in supported tickers list**
4. **Check if root agent is available** (might be better path)
