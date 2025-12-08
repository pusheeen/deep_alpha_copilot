# Chatbot Architecture - Confirmed Flow

## ✅ Architecture Flow (Confirmed)

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

## ✅ Yes, Architecture Does This

**After user input:**
1. ✅ **LLM Router (Gemini 2.5 Pro)** - The `Financial_Root_Agent` uses Gemini 2.5 Pro
2. ✅ **Intent Classification** - Done via LLM instructions in the root agent
3. ✅ **Sub-Agent Routing** - Root agent delegates to specialized sub-agents
4. ✅ **RAG Retrieval** - DocumentRAG_Agent now uses GCP (Vertex AI Embeddings + GCS)
5. ✅ **LLM Synthesis** - Root agent synthesizes final answer using Gemini

## DocumentRAG_Agent - Now Uses GCP

### Previous (Neo4j - Disabled):
- ❌ Used Neo4j vector database
- ❌ Required Neo4j connection
- ❌ Returned "disabled" message

### Current (GCP-Based):
- ✅ Loads 10-K filings from **Google Cloud Storage** (production) or local files (dev)
- ✅ Uses **Vertex AI Embeddings** (`text-embedding-005`) for semantic search
- ✅ Performs cosine similarity search on document chunks
- ✅ Synthesizes answers using **Gemini 2.5 Pro**
- ✅ Falls back gracefully if no documents available

### Implementation Details:

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

## All Neo4j References Removed

### Files Updated:
- ✅ `app/agents/agents.py`:
  - `retrieve_from_documents()` - Now uses GCP
  - `query_graph_database()` - Already disabled (uses JSON files)

### Neo4j References Found:
- `app/agents/agents.py:19` - Commented out import
- `app/agents/agents.py:127` - Returns disabled message
- `app/agents/agents.py:183` - Returns disabled message  
- `app/agents/agents.py:199` - **FIXED** - Now uses GCP RAG

## How to Verify

1. **Test DocumentRAG_Agent**:
   ```
   Query: "What is NVDA's management outlook according to their 10-K filings?"
   Expected: Routes to DocumentRAG_Agent → Uses GCP RAG → Returns synthesized answer
   ```

2. **Check Logs**:
   - Look for "Error retrieving documents" if GCS access fails
   - Look for "No relevant information found" if no chunks match
   - Look for "LLM synthesis failed" if Gemini unavailable

3. **Verify Architecture**:
   - ADK should route sentiment queries to RedditSentiment_Agent + Twitter_Agent
   - Document queries should route to DocumentRAG_Agent
   - Root agent should synthesize final answer

## Next Steps

1. ✅ DocumentRAG_Agent now uses GCP
2. ⚠️ Need to verify ADK routing is working correctly
3. ⚠️ May need to improve root agent instructions for better routing
4. ⚠️ Consider adding logging to track which path is taken (ADK vs fallback)

