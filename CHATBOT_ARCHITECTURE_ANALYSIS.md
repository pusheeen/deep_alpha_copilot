# Chatbot Architecture Analysis & Evaluation Framework

## Current Architecture

### 1. **Primary Path: Google ADK (Agent Development Kit)**
- **LLM Model**: Gemini 2.5 Pro (via LiteLLM)
- **Root Agent**: `Financial_Root_Agent`
- **Architecture**: Multi-agent system with routing
- **Sub-agents Available**:
  - `RedditSentiment_Agent` - Reddit sentiment analysis
  - `Twitter_Agent` - Twitter/X sentiment
  - `CompanyData_Agent` - Financial data and scores
  - `NewsSearch_Agent` - Latest news
  - `DocumentRAG_Agent` - SEC filing retrieval (disabled - Neo4j)
  - `MarketData_Agent` - Price data
  - `FlowData_Agent` - Institutional/retail flow
  - And 7 more specialized agents

### 2. **Fallback Path: Hardcoded Logic**
- **Triggered When**:
  - ADK not available
  - ADK call fails
  - ADK returns generic/unhelpful response
  - Sentiment query but no Reddit/Twitter mentions in answer
- **Implementation**: `_handle_chat_fallback()` in `app/main.py`
- **Current Behavior**: 
  - Pattern matching on query keywords
  - Direct function calls to `query_reddit_sentiment()` and `query_twitter_data()`
  - No LLM wrapper - just data aggregation

## Problems Identified

### Problem 1: **ADK May Not Be Working Properly**
- ADK initialization happens at startup
- If initialization fails silently, fallback is used
- No logging to verify which path is taken
- Generic response detection may be too aggressive

### Problem 2: **Fallback is Not a True LLM Chatbot**
- Hardcoded if/else logic
- No natural language understanding
- No RAG (Retrieval Augmented Generation)
- Just data aggregation without synthesis

### Problem 3: **Evaluation Framework is Custom, Not Gold Standard**
- Current `test_chatbot_query()` tests:
  - Routing (which agents called)
  - Relevance (keyword matching)
  - Accuracy (cross-reference with data)
  - Data sources (mention detection)
- **Missing Gold Standard Metrics**:
  - Faithfulness (answer grounded in context)
  - Answer Relevance (semantic similarity)
  - Context Precision (relevant context retrieved)
  - Context Recall (all relevant context retrieved)
  - Answer Correctness (factual accuracy)

### Problem 4: **No RAG Implementation**
- DocumentRAG_Agent exists but Neo4j is disabled
- No vector search on SEC filings
- No semantic retrieval from knowledge base
- Just direct API calls to structured data

## Gold Standard Evaluation Frameworks

### 1. **RAGAS (Retrieval Augmented Generation Assessment)**
```python
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_correctness
)

results = evaluate(
    dataset=dataset,
    metrics=[
        faithfulness,
        answer_relevancy,
        context_precision,
        context_recall,
        answer_correctness
    ]
)
```

### 2. **LangSmith Evaluation**
- Tracks LLM calls
- Evaluates response quality
- A/B testing
- Cost tracking

### 3. **TruLens**
- Evaluates LLM applications
- Tracks prompts and responses
- Measures quality metrics

## Recommended Architecture

### **Proper LLM Chatbot with RAG**

```
User Query
    ↓
LLM Router (Gemini 2.5 Pro)
    ↓
┌─────────────────────────────────────┐
│ 1. Intent Classification            │
│    - Sentiment query?                │
│    - Financial query?                │
│    - News query?                     │
│    - Comparison query?               │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 2. Sub-Agent Routing                │
│    - RedditSentiment_Agent          │
│    - Twitter_Agent                   │
│    - CompanyData_Agent               │
│    - NewsSearch_Agent                │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 3. RAG Retrieval (if needed)        │
│    - Vector search on SEC filings   │
│    - Semantic search on news        │
│    - Context retrieval              │
└─────────────────────────────────────┘
    ↓
┌─────────────────────────────────────┐
│ 4. LLM Synthesis                    │
│    - Combine agent outputs          │
│    - Generate natural answer        │
│    - Cite sources                    │
└─────────────────────────────────────┘
    ↓
Response to User
```

## Current Evaluation Framework Details

### How I Evaluated the Chatbot

**Function**: `test_chatbot_query()` in `app/agents/agents.py`

**Test Components**:

1. **Routing Test**:
   - Checks if expected agents were called
   - Extracts agent names from reasoning field
   - Verifies correct delegation

2. **Relevance Test**:
   - Keyword matching (sentiment, financial, news keywords)
   - Checks if answer addresses the query
   - Score: 0-100 based on keyword matches

3. **Data Source Test**:
   - Checks if answer mentions expected sources (Reddit, Twitter, etc.)
   - Pattern matching on source keywords
   - Verifies data sources were used

4. **Accuracy Test**:
   - Cross-references answer with actual data
   - Compares mentioned scores with computed scores
   - Validates factual correctness

**Limitations**:
- Keyword-based, not semantic
- No faithfulness check (is answer grounded?)
- No context evaluation (was right context retrieved?)
- No LLM-based evaluation

## Why Chatbot Might Not Be Working

### Possible Issues:

1. **ADK Not Initialized**
   - Check logs: "Initializing ADK Agent..."
   - If initialization fails, `agent_caller` is None
   - Falls back to hardcoded logic

2. **ADK Returns Generic Responses**
   - Root agent instruction may be too generic
   - Not properly routing to sub-agents
   - Returns "I can help..." instead of actual answer

3. **Fallback Logic Too Simple**
   - Only handles specific patterns
   - No LLM synthesis
   - Just aggregates data without natural language

4. **No RAG**
   - Can't answer questions requiring document understanding
   - No semantic search
   - Limited to structured data APIs

## Recommendations

### 1. **Implement Proper LLM Chatbot**
- Always use LLM (Gemini) for answer synthesis
- Route to sub-agents for data retrieval
- Use LLM to combine and synthesize answers
- Add RAG for document-based queries

### 2. **Implement Gold Standard Evaluation**
- Use RAGAS or similar framework
- Measure faithfulness, relevance, precision, recall
- Track LLM calls and responses
- A/B test different approaches

### 3. **Fix ADK Routing**
- Improve root agent instructions
- Add better logging
- Verify sub-agents are being called
- Test routing logic

### 4. **Add RAG**
- Implement vector search on SEC filings
- Add semantic search on news/articles
- Retrieve relevant context before answering
- Ground answers in retrieved context

### 5. **Better Fallback**
- If ADK fails, still use LLM for synthesis
- Don't just aggregate data
- Generate natural language responses
- Maintain quality even in fallback mode

