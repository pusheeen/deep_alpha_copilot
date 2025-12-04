# Root Agent: Responsibilities & Routing Principles

## 🎯 Core Responsibilities of the Root Agent

The `Financial_Root_Agent` serves as the **intelligent orchestrator** of the Deep Alpha Copilot system. It has four primary responsibilities:

### 1. **Query Interpretation & Intent Understanding**
- **Purpose**: Analyzes natural language user queries to understand what the user is asking
- **Mechanism**: Uses Gemini 2.5 Pro LLM to parse user intent
- **Output**: Determines which sub-agent(s) can best answer the query

### 2. **Intelligent Routing & Delegation**
- **Purpose**: Routes queries to the most appropriate specialized sub-agent(s)
- **Mechanism**: Matches query intent to sub-agent capabilities using instruction-based routing
- **Output**: Delegates query to one or more sub-agents

### 3. **Response Synthesis & Integration**
- **Purpose**: Combines results from multiple sub-agents when needed
- **Mechanism**: Aggregates tool outputs from sub-agents into coherent answers
- **Output**: Single, comprehensive response to the user

### 4. **Context Management & Session Handling**
- **Purpose**: Maintains conversation context across multi-turn interactions
- **Mechanism**: Uses ADK's `InMemorySessionService` to track conversation state
- **Output**: Context-aware responses that reference previous interactions

---

## 🧭 Routing Principles

The root agent follows **instruction-based routing** principles embedded in its system prompt. It uses semantic matching between query intent and sub-agent descriptions/instructions.

### Principle 1: **Semantic Intent Matching**

The root agent matches queries to sub-agents based on **keywords, intent patterns, and domain knowledge**:

```
Query Pattern → Sub-Agent Match
─────────────────────────────────────────────────────────────
"financials", "scores", "risks", "recommendation" 
  → CompanyData_Agent

"latest news", "recent developments", "breaking news"
  → NewsSearch_Agent

"predict", "forecast", "tomorrow's price"
  → StockPricePredictor_Agent

"Reddit", "sentiment", "social media"
  → RedditSentiment_Agent

"CEO", "executive", "leadership"
  → CEOLookup_Agent

"institutional", "flow", "ownership"
  → FlowData_Agent
```

### Principle 2: **Explicit Delegation Guidelines**

The root agent follows **explicit routing rules** defined in its instruction prompt:

#### **CompanyData_Agent** Routing Rules:
```
Use for:
✓ Specific financial numbers and scores
✓ Company risks, concerns, and weaknesses
✓ Investment recommendations and analysis
✓ All structured company data from JSON files

Example Queries:
- "What are the risks for NVDA?"
- "What's AVGO's financial score?"
- "Should I buy TSLA?"
- "Show me the Deep Alpha score for MSFT"
```

#### **NewsSearch_Agent** Routing Rules:
```
Use for:
✓ Latest news headlines for a specific company
✓ Press releases and recent developments
✓ Market-moving events or breaking stories
✓ Company-specific news (NOT sector-wide)

Example Queries:
- "What's the latest news about Apple?"
- "Any recent developments for NVDA?"
- "Show me breaking news for TSLA"
```

#### **SectorNews_Agent** Routing Rules:
```
Use for:
✓ News related to an entire financial sector
✓ Sector-wide analysis and trends
✓ Industry-level developments

Example Queries:
- "What's happening in the semiconductor sector?"
- "Latest news about energy companies"
- "Tech sector analysis"
```

#### **StockPricePredictor_Agent** Routing Rules:
```
Use ONLY for:
✓ Explicit requests to predict future stock prices
✓ Price forecasting queries
✓ "What will the price be tomorrow?"

IMPORTANT: Only routes if user explicitly asks for prediction
```

#### **RedditSentiment_Agent** Routing Rules:
```
Use for:
✓ Reddit sentiment analysis
✓ Social media discussions
✓ Community sentiment around companies
✓ Popular topics and trends on Reddit

Example Queries:
- "What's Reddit saying about GME?"
- "Show me social sentiment for NVDA"
```

#### **FlowData_Agent** Routing Rules:
```
Use for:
✓ Institutional ownership information
✓ Inflow/outflow tracking
✓ Retail flow estimates
✓ Questions about who owns a stock
✓ Institutional buying/selling activity

Example Queries:
- "Who owns NVDA?"
- "Show me institutional flows for TSLA"
- "What institutions are buying AVGO?"
```

### Principle 3: **Multi-Agent Coordination**

The root agent can **delegate to multiple sub-agents** when a query requires information from multiple sources:

```
Example Query: "What are the risks and latest news for NVDA?"

Routing Decision:
1. CompanyData_Agent → Get risks (data_type="risks")
2. NewsSearch_Agent → Get latest news

Root Agent then synthesizes both responses into one answer.
```

### Principle 4: **Fallback & Error Handling**

If uncertain about routing, the root agent:
1. **Explains reasoning**: States why it chose a particular agent
2. **Attempts best match**: Routes to the most likely sub-agent
3. **Handles failures gracefully**: If a sub-agent fails, tries alternative agents or explains limitations

### Principle 5: **Domain-Aware Routing**

The root agent knows:
- **Available tickers**: 35 companies (NVDA, AVGO, TSLA, etc.)
- **Data availability**: Financial data (2021-2024), quarterly earnings, Reddit data (past 1 month)
- **Tool limitations**: Which agents require internet access, API credentials, etc.

This knowledge helps it:
- **Validate tickers**: Ensures queries use supported ticker symbols
- **Set expectations**: Informs users about data limitations
- **Route efficiently**: Avoids routing to unavailable tools

---

## 🔄 Query Processing Flow

```
1. User Query Received
   ↓
2. Root Agent Analyzes Intent
   ├── Extracts key concepts (ticker, data type, time frame)
   ├── Identifies query category (financial, news, sentiment, etc.)
   └── Matches to sub-agent capabilities
   ↓
3. Routing Decision Made
   ├── Single agent: Routes to best match
   ├── Multiple agents: Routes to all relevant agents
   └── Uncertain: Explains reasoning, attempts best match
   ↓
4. Sub-Agent Execution
   ├── Sub-agent receives query
   ├── Sub-agent calls appropriate tool(s)
   └── Tool returns data
   ↓
5. Response Synthesis
   ├── Root agent receives sub-agent output
   ├── Combines multiple outputs if needed
   └── Formats final response
   ↓
6. User Receives Answer
   └── Comprehensive, context-aware response
```

---

## 📋 Routing Decision Matrix

| Query Type | Primary Agent | Secondary Agent (if needed) | Tool Called |
|------------|---------------|----------------------------|-------------|
| Financial scores/risks | CompanyData_Agent | - | `query_company_data()` |
| Latest company news | NewsSearch_Agent | - | `search_latest_news()` |
| Sector-wide news | SectorNews_Agent | - | `get_sector_news()` |
| Price prediction | StockPricePredictor_Agent | - | `predict_stock_price_tool()` |
| Reddit sentiment | RedditSentiment_Agent | - | `query_reddit_sentiment()` |
| CEO information | CEOLookup_Agent | - | `query_ceo_info_by_ticker()` |
| Flow data | FlowData_Agent | - | `query_flow_data()` |
| Market indices | MarketIndices_Agent | - | `query_market_indices()` |
| Comprehensive analysis | CompanyData_Agent | NewsSearch_Agent | Multiple tools |
| Investment decision | CompanyData_Agent | NewsSearch_Agent, RedditSentiment_Agent | Multiple tools |

---

## 🎓 Example Routing Scenarios

### Scenario 1: Simple Financial Query
```
User: "What are the risks for NVDA?"

Root Agent Analysis:
- Intent: Risk analysis
- Ticker: NVDA (valid)
- Data type: Risks
- Route to: CompanyData_Agent

Delegation:
→ CompanyData_Agent.query_company_data(ticker="NVDA", data_type="risks")

Response: Risk analysis from Deep Alpha scoring engine
```

### Scenario 2: Multi-Agent Query
```
User: "Should I buy TSLA? Show me the latest news and sentiment."

Root Agent Analysis:
- Intent: Investment decision + news + sentiment
- Ticker: TSLA (valid)
- Requires: Multiple data sources
- Route to: CompanyData_Agent, NewsSearch_Agent, RedditSentiment_Agent

Delegation:
→ CompanyData_Agent.query_company_data(ticker="TSLA", data_type="recommendation")
→ NewsSearch_Agent.search_latest_news(query="TSLA Tesla")
→ RedditSentiment_Agent.query_reddit_sentiment(ticker="TSLA")

Response: Synthesized answer combining recommendation, news, and sentiment
```

### Scenario 3: Ambiguous Query
```
User: "Tell me about Apple."

Root Agent Analysis:
- Intent: General company information (ambiguous)
- Ticker: AAPL (valid)
- Best match: CompanyData_Agent (comprehensive data)
- Reasoning: "General queries → comprehensive analysis"

Delegation:
→ CompanyData_Agent.query_company_data(ticker="AAPL", data_type="all")

Response: Complete company profile with scores, risks, and recommendations
```

### Scenario 4: Explicit Prediction Request
```
User: "Predict tomorrow's price for AAPL"

Root Agent Analysis:
- Intent: Price prediction (explicit)
- Ticker: AAPL (valid)
- Route to: StockPricePredictor_Agent (ONLY for explicit predictions)

Delegation:
→ StockPricePredictor_Agent.predict_stock_price_tool(ticker="AAPL")

Response: Next-day price prediction with disclaimer
```

---

## 🛡️ Safety & Compliance Principles

The root agent follows these safety principles:

1. **Disclaimers**: Always includes disclaimers for:
   - Predictions (not financial advice)
   - Reddit sentiment (community opinion)
   - CEO data (accuracy limitations)

2. **Data Validation**: 
   - Validates ticker symbols against supported list
   - Checks data availability before routing
   - Handles missing data gracefully

3. **Error Handling**:
   - If sub-agent fails, explains the issue
   - Suggests alternative queries when possible
   - Never fabricates data

4. **Transparency**:
   - Explains routing decisions when uncertain
   - Shows which tools were used (if `include_reasoning=true`)
   - Provides data source attribution

---

## 🔧 Technical Implementation

### Agent Definition
```python
root_agent = Agent(
    name="Financial_Root_Agent",
    model=llm,  # Gemini 2.5 Pro
    sub_agents=[...13 sub-agents...],
    description="Main financial assistant...",
    instruction="""DELEGATION GUIDELINES: ..."""
)
```

### Query Processing
```python
# In app/main.py
async def call(self, user_message: str, include_reasoning: bool = False):
    content = types.Content(role='user', parts=[types.Part(text=user_message)])
    
    async for event in self.runner.run_async(
        user_id=self.user_id, 
        session_id=self.session_id, 
        new_message=content
    ):
        # Root agent processes query and delegates
        # Sub-agents execute tools
        # Root agent synthesizes response
```

### ADK Framework Behavior

The Google ADK framework handles:
- **Automatic delegation**: Root agent's LLM decides which sub-agent to use
- **Tool execution**: Sub-agents call their tools automatically
- **Response streaming**: Events stream back to the root agent
- **Session management**: Maintains conversation context

---

## 📊 Routing Accuracy Factors

The root agent's routing accuracy depends on:

1. **Query Clarity**: Clear, specific queries → better routing
2. **Instruction Quality**: Well-defined sub-agent descriptions → better matching
3. **LLM Capability**: Gemini 2.5 Pro's understanding → accurate intent parsing
4. **Domain Knowledge**: Root agent's knowledge of available data → appropriate routing

---

## 🎯 Key Takeaways

1. **Root agent is an orchestrator**, not a data source
2. **Routing is instruction-based**, using semantic matching
3. **Multi-agent coordination** enables comprehensive answers
4. **Safety and transparency** are built into routing decisions
5. **ADK framework** handles the mechanics of delegation

The root agent's primary value is **intelligent routing** - it understands user intent and connects queries to the right specialized agents, enabling the system to provide comprehensive, accurate financial analysis.

