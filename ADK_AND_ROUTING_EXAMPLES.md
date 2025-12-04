# ADK Explained & Concrete Routing Examples

## 1. What Does ADK Mean?

**ADK** stands for **Agent Development Kit** - it's Google's framework for building multi-agent AI systems.

### What ADK Provides

ADK is a Python framework from Google that enables you to:

1. **Define Agents**: Create specialized AI agents with specific capabilities
2. **Orchestrate Multi-Agent Systems**: Have a root agent delegate to sub-agents
3. **Tool Integration**: Connect agents to tools (functions, APIs, databases)
4. **Session Management**: Maintain conversation context across interactions
5. **Streaming Responses**: Get real-time updates as agents process queries

### ADK Components Used in This Project

```python
from google.adk.agents import Agent          # Define agents
from google.adk.runners import Runner       # Execute agent queries
from google.adk.sessions import InMemorySessionService  # Manage sessions
from google.adk.models.lite_llm import LiteLlm  # LLM wrapper
```

### How ADK Works

```
User Query
    ↓
ADK Runner (orchestrates execution)
    ↓
Root Agent (Gemini 2.5 Pro analyzes intent)
    ↓
Routes to Sub-Agent(s)
    ↓
Sub-Agent calls Tool(s)
    ↓
Tool returns data
    ↓
Sub-Agent processes data
    ↓
Root Agent synthesizes response
    ↓
User receives answer
```

### Why Use ADK?

- **Automatic Delegation**: The LLM decides which sub-agent to use (no hardcoded rules)
- **Tool Calling**: Agents can call Python functions automatically
- **Context Management**: Maintains conversation history
- **Error Handling**: Built-in retry and fallback mechanisms
- **Streaming**: Real-time updates during processing

---

## 2. Concrete Routing Examples

Here are **real, concrete examples** of how queries flow through the system:

### Example 1: Simple Financial Query

**User Query:**
```
"What are the risks for NVDA?"
```

**Step-by-Step Flow:**

1. **User sends query** → FastAPI `/chat` endpoint receives: `{"question": "What are the risks for NVDA?"}`

2. **Root Agent Analysis:**
   ```
   Intent: Risk analysis
   Ticker: NVDA (valid, in TARGET_TICKERS)
   Query Type: Financial data query
   Best Match: CompanyData_Agent
   ```

3. **Root Agent Delegates:**
   ```python
   → CompanyData_Agent receives query
   → CompanyData_Agent calls: query_company_data(ticker="NVDA", data_type="risks")
   ```

4. **Tool Execution:**
   ```python
   # In app/scoring/engine.py
   compute_company_scores("NVDA")
   # Returns: {
   #   "recommendation": {
   #     "risks": ["High valuation", "Regulatory concerns", ...],
   #     "main_risks": "NVDA faces regulatory risks...",
   #     "key_concerns": "Competition from AMD..."
   #   }
   # }
   ```

5. **Sub-Agent Response:**
   ```
   "NVDA faces several key risks:
   1. High valuation concerns
   2. Regulatory risks in China
   3. Competition from AMD and other chipmakers
   ..."
   ```

6. **Root Agent Final Response:**
   ```
   "Based on the Deep Alpha analysis, NVDA faces several key risks:
   
   1. High Valuation: The stock trades at elevated multiples...
   2. Regulatory Risks: Export controls affecting China sales...
   3. Competition: AMD and other players are gaining market share...
   
   [Full risk analysis with details]"
   ```

**Actual API Call:**
```bash
POST /chat
{
  "question": "What are the risks for NVDA?",
  "include_reasoning": false
}

Response:
{
  "answer": "NVDA faces several key risks...",
  "status": "success"
}
```

---

### Example 2: Multi-Agent Query

**User Query:**
```
"Should I buy TSLA? Show me the latest news and Reddit sentiment."
```

**Step-by-Step Flow:**

1. **User sends query** → `/chat` endpoint receives multi-part query

2. **Root Agent Analysis:**
   ```
   Intent: Investment decision + news + sentiment
   Ticker: TSLA (valid)
   Requires: Multiple data sources
   Route to: CompanyData_Agent + NewsSearch_Agent + RedditSentiment_Agent
   ```

3. **Root Agent Delegates (Parallel):**
   ```python
   # Agent 1: Investment recommendation
   → CompanyData_Agent.query_company_data(ticker="TSLA", data_type="recommendation")
   
   # Agent 2: Latest news
   → NewsSearch_Agent.search_latest_news(query="TSLA Tesla", max_results=10)
   
   # Agent 3: Reddit sentiment
   → RedditSentiment_Agent.query_reddit_sentiment(ticker="TSLA")
   ```

4. **Tool Executions:**

   **Tool 1 Output:**
   ```json
   {
     "recommendation": {
       "action": "Hold",
       "reasoning": "TSLA has strong fundamentals but high volatility...",
       "overall_score": 6.8
     }
   }
   ```

   **Tool 2 Output:**
   ```json
   {
     "articles": [
       {"title": "Tesla announces new factory", "date": "2024-12-03"},
       {"title": "TSLA stock surges on delivery numbers", "date": "2024-12-02"}
     ]
   }
   ```

   **Tool 3 Output:**
   ```json
   {
     "total_posts": 45,
     "bullish_posts": 28,
     "bearish_posts": 12,
     "sentiment_ratio": 0.36
   }
   ```

5. **Root Agent Synthesizes:**
   ```
   "Based on comprehensive analysis:
   
   INVESTMENT RECOMMENDATION: Hold
   - Deep Alpha Score: 6.8/10
   - Strong fundamentals but high volatility
   
   LATEST NEWS:
   - Tesla announces new factory (Dec 3)
   - Stock surges on delivery numbers (Dec 2)
   
   REDDIT SENTIMENT:
   - 45 posts in past 7 days
   - Bullish ratio: 62% (28 bullish, 12 bearish)
   - Community sentiment is positive
   
   CONCLUSION: TSLA shows strong fundamentals and positive sentiment,
   but consider volatility. Monitor delivery numbers and factory expansion."
   ```

**Actual API Call:**
```bash
POST /chat
{
  "question": "Should I buy TSLA? Show me the latest news and Reddit sentiment.",
  "include_reasoning": true
}

Response:
{
  "answer": "Based on comprehensive analysis...",
  "status": "success",
  "reasoning_steps": [
    {"tool": "query_company_data", "input": {"ticker": "TSLA", "data_type": "recommendation"}},
    {"tool": "search_latest_news", "input": {"query": "TSLA Tesla"}},
    {"tool": "query_reddit_sentiment", "input": {"ticker": "TSLA"}}
  ],
  "tools_used": ["query_company_data", "search_latest_news", "query_reddit_sentiment"]
}
```

---

### Example 3: News Query

**User Query:**
```
"What's the latest news about Apple?"
```

**Step-by-Step Flow:**

1. **Root Agent Analysis:**
   ```
   Intent: Latest news for specific company
   Ticker: AAPL (Apple)
   Query Type: News search
   Route to: NewsSearch_Agent
   ```

2. **Delegation:**
   ```python
   → NewsSearch_Agent.search_latest_news(query="Apple AAPL", max_results=10)
   ```

3. **Tool Execution:**
   ```python
   # Calls Google Custom Search API
   # Returns recent news articles
   {
     "articles": [
       {
         "title": "Apple announces new iPhone features",
         "link": "https://...",
         "snippet": "Apple unveiled...",
         "date": "2024-12-03"
       },
       ...
     ]
   }
   ```

4. **Response:**
   ```
   "Here's the latest news about Apple (AAPL):
   
   1. Apple announces new iPhone features (Dec 3)
      Apple unveiled new AI capabilities...
   
   2. Apple stock rises on strong earnings (Dec 1)
      ...
   
   [More articles...]"
   ```

---

### Example 4: CEO Information Query

**User Query:**
```
"Who is the CEO of Microsoft and how long have they been in the role?"
```

**Step-by-Step Flow:**

1. **Root Agent Analysis:**
   ```
   Intent: CEO information
   Ticker: MSFT (Microsoft)
   Query Type: Leadership/executive info
   Route to: CEOLookup_Agent
   ```

2. **Delegation:**
   ```python
   → CEOLookup_Agent.query_ceo_info_by_ticker(ticker="MSFT")
   ```

3. **Tool Execution:**
   ```python
   # Returns CEO profile from data/companies.csv or web scraping
   {
     "name": "Satya Nadella",
     "title": "Chief Executive Officer",
     "start_date": "February 2014",
     "calculated_duration": "10+ years",
     "past_experience": [...],
     "education": "..."
   }
   ```

4. **Response:**
   ```
   "Satya Nadella is the CEO of Microsoft (MSFT).
   
   - Title: Chief Executive Officer
   - Tenure: 10+ years (since February 2014)
   - Background: Previously led Microsoft's cloud division...
   - Education: MBA from University of Chicago..."
   ```

---

### Example 5: Price Prediction Query

**User Query:**
```
"Predict tomorrow's closing price for NVDA"
```

**Step-by-Step Flow:**

1. **Root Agent Analysis:**
   ```
   Intent: Price prediction (explicit)
   Ticker: NVDA
   Query Type: Prediction/forecast
   Route to: StockPricePredictor_Agent (ONLY for explicit predictions)
   ```

2. **Delegation:**
   ```python
   → StockPricePredictor_Agent.predict_stock_price_tool(ticker="NVDA")
   ```

3. **Tool Execution:**
   ```python
   # Loads LightGBM model from app/models/saved_models/NVDA_price_regressor.joblib
   # Predicts next-day closing price
   {
     "ticker": "NVDA",
     "predicted_price": 485.23,
     "confidence": 0.72,
     "model_version": "2024-12-01"
   }
   ```

4. **Response (with disclaimer):**
   ```
   "Based on the ML model, NVDA's predicted closing price for tomorrow is $485.23.
   
   Confidence: 72%
   Model: LightGBM regressor (trained on historical data)
   
   ⚠️ DISCLAIMER: This prediction is based on historical patterns and is not
   financial advice. Stock prices are highly volatile and unpredictable.
   Past performance does not guarantee future results."
   ```

---

### Example 6: Flow Data Query

**User Query:**
```
"Who owns NVDA? Show me institutional flows"
```

**Step-by-Step Flow:**

1. **Root Agent Analysis:**
   ```
   Intent: Ownership and flow data
   Ticker: NVDA
   Query Type: Institutional/flow data
   Route to: FlowData_Agent
   ```

2. **Delegation:**
   ```python
   → FlowData_Agent.query_flow_data(ticker="NVDA")
   ```

3. **Tool Execution:**
   ```python
   # Reads from data/structured/flow_data/NVDA_flow_data.json
   {
     "institutional_holders": [
       {"name": "Vanguard Group", "shares": 125000000, "change": +5000000},
       {"name": "BlackRock", "shares": 98000000, "change": -2000000}
     ],
     "institutional_flow": {
       "quarter": "Q3 2024",
       "net_inflow": 15000000,
       "total_institutions": 2450
     },
     "retail_flow": {
       "period": "3 months",
       "estimated_retail_participation": 0.35
     }
   }
   ```

4. **Response:**
   ```
   "NVDA Institutional Ownership (Q3 2024):
   
   Top Holders:
   - Vanguard Group: 125M shares (+5M this quarter)
   - BlackRock: 98M shares (-2M this quarter)
   
   Institutional Flow:
   - Net inflow: 15M shares
   - Total institutions: 2,450
   - Period: Q3 2024 (factual SEC 13F data)
   
   Retail Flow (Estimated):
   - Estimated retail participation: 35%
   - Period: Last 3 months"
   ```

---

## 3. Is This Mostly Useful for the Chatbot?

**Yes, but it's more than just a chatbot!** The ADK agent system powers the **interactive chat interface**, but the underlying components are used throughout the application.

### Where ADK Agents Are Used

#### 1. **Chat Interface** (Primary Use)
- **Location**: Floating chat widget in `app/templates/index.html`
- **Endpoint**: `POST /chat`
- **User Experience**: Users can ask natural language questions
- **Example**: "What are the risks for NVDA?"

```javascript
// In index.html
const chatForm = document.getElementById('chat-form');
chatForm.addEventListener('submit', async (e) => {
  const response = await fetch('/chat', {
    method: 'POST',
    body: JSON.stringify({ question: userInput })
  });
  // Display response in chat window
});
```

#### 2. **API Endpoints** (Secondary Use)
The same tools used by agents are also exposed as REST APIs:

```python
# Direct API access (no agent needed)
GET /api/scores/{ticker}          # Uses compute_company_scores()
GET /api/latest-news/{ticker}     # Uses search_latest_news()
GET /api/flow-data/{ticker}       # Uses query_flow_data()
```

#### 3. **Dashboard UI** (Indirect Use)
The dashboard displays data that agents can also access:
- Scorecards → Uses `compute_company_scores()` (same as `CompanyData_Agent`)
- News section → Uses news fetching (same as `NewsSearch_Agent`)
- Flow data → Uses flow data tools (same as `FlowData_Agent`)

### Why Use Agents vs Direct APIs?

| Feature | Direct API | Agent System |
|---------|-----------|--------------|
| **Natural Language** | ❌ Requires specific endpoints | ✅ Understands intent |
| **Multi-Source Queries** | ❌ Multiple API calls needed | ✅ Single query, multiple sources |
| **Context Awareness** | ❌ Stateless | ✅ Maintains conversation |
| **Intelligent Routing** | ❌ Manual routing | ✅ Automatic delegation |
| **Synthesis** | ❌ User combines results | ✅ Agent synthesizes |

### Example: Same Query, Different Approaches

**Query:** "Should I buy NVDA? Show me risks and latest news."

**Direct API Approach:**
```javascript
// User needs to make 3 separate calls
const scores = await fetch('/api/scores/NVDA');
const news = await fetch('/api/latest-news/NVDA');
const risks = await fetch('/api/scores/NVDA'); // Extract risks from scores

// User needs to combine and interpret results
```

**Agent Approach:**
```javascript
// Single query, agent handles everything
const response = await fetch('/chat', {
  method: 'POST',
  body: JSON.stringify({
    question: "Should I buy NVDA? Show me risks and latest news."
  })
});

// Agent automatically:
// 1. Routes to CompanyData_Agent (risks)
// 2. Routes to NewsSearch_Agent (news)
// 3. Synthesizes into coherent answer
```

### When to Use Agents vs Direct APIs

**Use Agents (Chat) When:**
- ✅ User wants natural language interaction
- ✅ Query requires multiple data sources
- ✅ User wants synthesized, conversational answers
- ✅ Context matters (follow-up questions)

**Use Direct APIs When:**
- ✅ Building custom UI components
- ✅ Need specific data format
- ✅ Performance is critical (no LLM overhead)
- ✅ Programmatic access (no user interaction)

### The Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    User Interface                        │
├─────────────────────────────────────────────────────────┤
│  Dashboard UI          │  Chat Interface (ADK)         │
│  (Direct APIs)          │  (Agent System)               │
├─────────────────────────────────────────────────────────┤
│  /api/scores/{ticker}   │  /chat (Agent Routing)       │
│  /api/latest-news/...   │                                │
│  /api/flow-data/...     │                                │
├─────────────────────────────────────────────────────────┤
│              Shared Tools & Data Sources                 │
│  compute_company_scores()                               │
│  search_latest_news()                                    │
│  query_flow_data()                                       │
└─────────────────────────────────────────────────────────┘
```

### Summary

**ADK agents are primarily for the chatbot**, but:
1. **The tools are shared** - Same functions power both APIs and agents
2. **Agents add intelligence** - Natural language understanding, routing, synthesis
3. **Both are useful** - APIs for programmatic access, agents for user interaction

The agent system makes the chatbot **intelligent** - it understands intent, routes queries appropriately, and synthesizes comprehensive answers. Without agents, you'd need a simple keyword-based chatbot or require users to know specific API endpoints.

---

## Key Takeaways

1. **ADK = Agent Development Kit** - Google's framework for multi-agent AI systems
2. **Concrete Examples** - Real queries showing step-by-step routing and execution
3. **Primarily for Chatbot** - But tools are shared with direct APIs
4. **Value Add** - Agents provide natural language understanding, intelligent routing, and response synthesis

The agent system transforms a simple API into an intelligent financial assistant that understands context and provides comprehensive, synthesized answers.

