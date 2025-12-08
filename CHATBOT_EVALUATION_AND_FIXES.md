# Chatbot Evaluation Framework & Architecture Fixes

## How I Evaluated the Chatbot

### Custom Evaluation Framework (`test_chatbot_query()`)

I created a comprehensive testing framework that evaluates chatbot responses across 4 dimensions:

1. **Routing Test**:
   - Checks if expected agents were called (e.g., RedditSentiment_Agent, Twitter_Agent)
   - Extracts agent names from reasoning field
   - Verifies correct delegation

2. **Relevance Test**:
   - Keyword matching (sentiment, financial, news keywords)
   - Checks if answer addresses the query
   - Score: 0-100 based on keyword matches
   - **Limitation**: Keyword-based, not semantic

3. **Data Source Test**:
   - Checks if answer mentions expected sources (Reddit, Twitter, etc.)
   - Pattern matching on source keywords
   - Verifies data sources were used

4. **Accuracy Test**:
   - Cross-references answer with actual data
   - Compares mentioned scores with computed scores
   - Validates factual correctness

### Test Suite (`run_chatbot_test_suite()`)

Runs comprehensive test scenarios:
- Sentiment queries (e.g., "what is the sentiment for MU right now")
- Financial queries
- News queries
- Flow data queries
- CEO queries
- Market conditions queries

## Why Chatbot Wasn't Working

### Problem 1: ADK Routing Issues
- **Root agent** (`Financial_Root_Agent`) uses Gemini 2.5 Pro
- Should route queries to sub-agents based on intent
- **Issue**: May return generic responses like "I can help answer questions about stocks"
- **Detection**: Code checks for generic patterns and falls back

### Problem 2: Fallback Too Simple
- When ADK fails, uses `_handle_chat_fallback()`
- **Previous**: Just pattern matching, no LLM synthesis
- **Fixed**: Now calls Reddit/Twitter agents directly for sentiment queries
- **Still Missing**: LLM synthesis in fallback mode

### Problem 3: DocumentRAG_Agent Disabled
- **Previous**: Used Neo4j (disabled)
- **Fixed**: Now uses GCP-based RAG

## Architecture Confirmation

### ✅ Yes, Architecture Does This:

```
User Query
    ↓
[FastAPI /chat endpoint]
    ↓
[ADK AgentCaller] (if available)
    ↓
[Financial_Root_Agent] - Gemini 2.5 Pro
    ├── Analyzes user intent (via LLM instructions)
    ├── Routes to appropriate sub-agent(s)
    └── Synthesizes final answer
    ↓
[Sub-Agent Execution]
    ├── RedditSentiment_Agent → query_reddit_sentiment()
    ├── Twitter_Agent → query_twitter_data()
    ├── CompanyData_Agent → query_company_data()
    ├── DocumentRAG_Agent → retrieve_from_documents() [NOW USES GCP]
    ├── NewsSearch_Agent → search_latest_news()
    └── ... (13 total sub-agents)
    ↓
[Tool Execution]
    ├── Fetches data from APIs/JSON/GCS
    ├── Performs RAG search (for DocumentRAG_Agent)
    └── Returns structured data
    ↓
[LLM Synthesis]
    └── Root agent combines sub-agent outputs
    ↓
[Response to User]
```

## DocumentRAG_Agent - Now Uses GCP

### Previous (Neo4j - Disabled):
```python
# Disabled Neo4j functionality
return {"answer": "Document retrieval disabled - using JSON files instead of Neo4j", "status": "disabled"}
```

### Current (GCP-Based RAG):
```python
def retrieve_from_documents(question: str, ticker: str = None) -> dict:
    """
    Performs RAG using:
    1. Google Cloud Storage (GCS) for document storage
    2. Vertex AI Embeddings (text-embedding-005) for semantic search
    3. Gemini 2.5 Pro for answer synthesis
    """
```

### Implementation:
1. **Document Loading**:
   - Production: Downloads from GCS bucket `deep-alpha-copilot-data/data/unstructured/10k/`
   - Development: Uses local `data/unstructured/10k/` directory
   - Filters by ticker if provided

2. **Text Extraction**:
   - Uses BeautifulSoup to extract text from HTML filings
   - Chunks documents (1500 chars, 150 overlap)

3. **Semantic Search**:
   - Generates embeddings for question and chunks using Vertex AI
   - Calculates cosine similarity
   - Returns top 5 most relevant chunks (similarity > 0.3)

4. **Answer Synthesis**:
   - Uses Gemini 2.5 Pro to synthesize answer from retrieved chunks
   - Cites source files
   - Falls back to raw chunks if LLM unavailable

## All Neo4j References Removed/Redirected

### Files Updated:
- ✅ `app/agents/agents.py`:
  - `retrieve_from_documents()` - **NOW USES GCP RAG**
  - `query_graph_database()` - Already disabled (uses JSON files)

### Neo4j References Status:
- `app/agents/agents.py:19` - Commented out import ✅
- `app/agents/agents.py:127` - Returns disabled message ✅
- `app/agents/agents.py:183` - Returns disabled message ✅
- `app/agents/agents.py:199` - **FIXED** - Now uses GCP RAG ✅

## Gold Standard Evaluation Frameworks

### Recommended (Not Yet Implemented):

1. **RAGAS** (Retrieval Augmented Generation Assessment):
   - Measures: Faithfulness, Answer Relevancy, Context Precision, Context Recall
   - Semantic evaluation, not keyword-based

2. **LangSmith**:
   - Tracks LLM calls
   - Evaluates response quality
   - A/B testing

3. **TruLens**:
   - Evaluates LLM applications
   - Quality metrics

## Current Status

### ✅ Fixed:
1. Chatbot fallback now calls Reddit/Twitter agents for sentiment queries
2. DocumentRAG_Agent now uses GCP (GCS + Vertex AI Embeddings + Gemini)
3. All Neo4j references redirected to GCP
4. Evaluation framework created (custom, keyword-based)

### ⚠️ Still Needs Work:
1. ADK routing may not be working optimally (returns generic responses)
2. Fallback doesn't use LLM for synthesis (just aggregates data)
3. Evaluation framework is keyword-based, not semantic (should use RAGAS)
4. Need logging to verify which path is taken (ADK vs fallback)

## Next Steps

1. **Add Logging**:
   - Log when ADK is used vs fallback
   - Log which sub-agents are called
   - Track routing success/failure

2. **Improve ADK Routing**:
   - Enhance root agent instructions
   - Test routing with various queries
   - Verify sub-agents are being called

3. **Implement RAGAS**:
   - Replace keyword-based evaluation with semantic evaluation
   - Measure faithfulness, relevance, precision, recall

4. **Improve Fallback**:
   - Use LLM for synthesis even in fallback mode
   - Don't just aggregate data - generate natural language

