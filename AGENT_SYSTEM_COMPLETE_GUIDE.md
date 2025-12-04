# Deep Alpha Copilot: Complete Agent System Guide

## 📚 Table of Contents

1. [Overview](#overview)
2. [What is ADK?](#what-is-adk)
3. [Agent Architecture](#agent-architecture)
4. [How Deep Alpha Score Works](#how-deep-alpha-score-works)
5. [How News Interpreter Works](#how-news-interpreter-works)
6. [Root Agent Responsibilities](#root-agent-responsibilities)
7. [Routing Principles](#routing-principles)
8. [Single vs Multiple API Calls](#single-vs-multiple-api-calls)
9. [Team vs Individual Analogy](#team-vs-individual-analogy)
10. [Key Advantages](#key-advantages)

---

## Overview

The Deep Alpha Copilot uses a **hierarchical multi-agent system** built on Google's ADK (Agent Development Kit) framework. The system consists of:

- **1 Root Agent** (`Financial_Root_Agent`) - Orchestrator using Gemini 2.5 Pro
- **13 Sub-Agents** - Specialized agents for specific tasks
- **Deep Alpha Scoring Engine** - 7-pillar fundamental analysis
- **News Interpreter** - LLM-powered news analysis

---

## What is ADK?

**ADK = Agent Development Kit** - Google's framework for building multi-agent AI systems.

### What ADK Provides

- **Define Agents**: Create specialized AI agents with specific capabilities
- **Orchestrate Multi-Agent Systems**: Root agent delegates to sub-agents
- **Tool Integration**: Connect agents to tools (functions, APIs, databases)
- **Session Management**: Maintain conversation context
- **Streaming Responses**: Real-time updates during processing

### Components Used

```python
from google.adk.agents import Agent          # Define agents
from google.adk.runners import Runner       # Execute queries
from google.adk.sessions import InMemorySessionService  # Manage sessions
from google.adk.models.lite_llm import LiteLlm  # LLM wrapper
```

---

## Agent Architecture

### Structure

```
┌─────────────────────────────────────────────────────────────┐
│              Financial_Root_Agent (Orchestrator)           │
│              Model: Gemini 2.5 Pro                          │
│              Role: Routes queries to appropriate sub-agents  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ├─── Delegates to ───┐
                            │                    │
                            ▼                    ▼
        ┌──────────────────────────┐  ┌──────────────────────────┐
        │   CompanyData_Agent      │  │  DocumentRAG_Agent       │
        │   (Financial Analysis)    │  │  (SEC Filing Analysis)   │
        └──────────────────────────┘  └──────────────────────────┘
                            │                    │
                            ▼                    ▼
        ┌──────────────────────────┐  ┌──────────────────────────┐
        │   NewsSearch_Agent       │  │  StockPricePredictor_Agent│
        │   (Latest News)          │  │  (ML Price Prediction)   │
        └──────────────────────────┘  └──────────────────────────┘
                            │                    │
                            ▼                    ▼
        ┌──────────────────────────┐  ┌──────────────────────────┐
        │   RedditSentiment_Agent  │  │  FlowData_Agent          │
        │   (Social Sentiment)     │  │  (Institutional Flows)   │
        └──────────────────────────┘  └──────────────────────────┘
                            │
                            ▼
        ... (13 total sub-agents)
```

### Sub-Agents

| Agent Name | Purpose | Tool(s) |
|------------|---------|---------|
| **CompanyData_Agent** | Financial analysis, scores, risks | `query_company_data()` |
| **NewsSearch_Agent** | Latest news headlines | `search_latest_news()` |
| **RedditSentiment_Agent** | Social sentiment analysis | `query_reddit_sentiment()` |
| **FlowData_Agent** | Institutional/retail flows | `query_flow_data()` |
| **StockPricePredictor_Agent** | ML price predictions | `predict_stock_price_tool()` |
| **CEOLookup_Agent** | CEO information | `query_ceo_info_by_ticker()` |
| ... and 7 more | | |

---

## How Deep Alpha Score Works

The **Deep Alpha Score** (0-10) evaluates stocks across **7 fundamental pillars**:

### The 7 Pillars

1. **Business Score** (20%) - Revenue CAGR, gross margin, R&D intensity
2. **Financial Score** (25%) - Net income CAGR, ROE, liquidity, leverage
3. **Sentiment Score** (15%) - News sentiment + Reddit/Twitter sentiment
4. **Critical Path Score** (10%) - Strategic positioning, policy tailwinds
5. **Leadership Score** (10%) - CEO tenure and background
6. **Earnings Score** (10%) - EPS/revenue trends, consistency
7. **Technical Score** (10%) - RSI, moving averages, volume

### Score Calculation

```python
weights = {
    "business": 0.20,      # 20%
    "financial": 0.25,     # 25% (highest weight)
    "sentiment": 0.15,     # 15%
    "critical": 0.10,      # 10%
    "leadership": 0.10,    # 10%
    "earnings": 0.10,      # 10%
    "technical": 0.10,     # 10%
}

overall_score = sum(component_score * weight) / sum(weights)
```

### Recommendation Mapping

- **Score ≥ 8.0**: "Strong Buy" (Long-term, 12-24 months)
- **Score ≥ 7.0**: "Buy" (Long-term, 12-18 months)
- **Score ≥ 4.0**: "Hold" (Medium-term, 6-12 months)
- **Score < 4.0**: "Sell" (Short-term, <6 months)

---

## How News Interpreter Works

The **News Interpreter** uses **Google Gemini** to analyze news through the Deep Alpha 7-Pillar framework.

### Process

1. **News Collection** - Google Custom Search API (last 72 hours)
2. **Context Gathering** - Company fundamentals, sector metrics, technical data
3. **LLM Analysis** - Gemini evaluates impact across all 7 pillars
4. **Output Generation** - JSON with rating, takeaways, investment conclusion

### Fallback Strategy

- **Primary**: `gemini-2.0-flash-exp` (fast, experimental)
- **Fallback**: `gemini-1.5-flash` (more stable, higher quota)

### Output Format

```json
{
  "rating_buy_hold_sell": "BUY/HOLD/SELL",
  "sentiment_confidence": "High/Medium/Low",
  "key_takeaways": [
    {"type": "Fundamental Impact", "summary": "..."},
    {"type": "Strategic Moat", "summary": "..."},
    {"type": "Technical Noise", "summary": "..."}
  ],
  "investment_conclusion": {
    "paragraph": "150-200 word summary...",
    "reasoning_justification": "..."
  }
}
```

---

## Root Agent Responsibilities

The `Financial_Root_Agent` has 4 core responsibilities:

1. **Query Interpretation** - Analyzes natural language to understand intent
2. **Intelligent Routing** - Routes queries to appropriate sub-agent(s)
3. **Response Synthesis** - Combines results from multiple sub-agents
4. **Context Management** - Maintains conversation state

---

## Routing Principles

The root agent uses **instruction-based routing** with 5 principles:

### Principle 1: Semantic Intent Matching

Matches query patterns to sub-agents:
- "financials", "scores", "risks" → `CompanyData_Agent`
- "latest news" → `NewsSearch_Agent`
- "predict", "forecast" → `StockPricePredictor_Agent`
- "Reddit", "sentiment" → `RedditSentiment_Agent`

### Principle 2: Explicit Delegation Guidelines

Each sub-agent has defined routing rules in the root agent's instruction prompt.

### Principle 3: Multi-Agent Coordination

Can delegate to multiple sub-agents simultaneously:
```
Query: "What are the risks and latest news for NVDA?"
→ Routes to: CompanyData_Agent + NewsSearch_Agent
→ Synthesizes both responses
```

### Principle 4: Fallback & Error Handling

- Explains reasoning when uncertain
- Handles failures gracefully
- Suggests alternatives when possible

### Principle 5: Domain-Aware Routing

Knows available tickers, data availability, and tool limitations.

---

## Single vs Multiple API Calls

### Without Agent System: 4 API Calls

```javascript
// Frontend must make 4 separate calls
const [scoresRes, newsRes, redditRes, flowRes] = await Promise.all([
  fetch(`/api/scores/NVDA`),           // Call 1
  fetch(`/api/latest-news/NVDA`),       // Call 2
  fetch(`/api/reddit-sentiment/NVDA`), // Call 3
  fetch(`/api/flow-data/NVDA`)         // Call 4
]);

// Then manually combine all 4 responses
```

**Problems:**
- 4 network requests
- Manual synthesis
- Complex error handling
- More frontend code

### With Agent System: 1 API Call

```javascript
// Single API call - that's it!
const response = await fetch('/chat', {
  method: 'POST',
  body: JSON.stringify({
    question: "Should I invest in NVDA? Show me risks, news, sentiment, and flows"
  })
});

// Agent automatically:
// 1. Routes to 4 sub-agents
// 2. Synthesizes all results
// 3. Returns complete answer
```

**Benefits:**
- 1 network request
- Automatic synthesis
- Built-in error handling
- Less frontend code

### Internal Calls

**Important**: The 4 sub-agents still make 4 internal calls, but:
- They're **internal function calls** (not HTTP requests)
- Can be **parallelized** automatically
- **No HTTP overhead** between calls
- **Faster execution**

---

## Team vs Individual Analogy

### Without Agent System: One Person Sequentially

```
You (One Person):
  → Call Finance API → Wait → Process
  → Call News API → Wait → Process
  → Call Sentiment API → Wait → Process
  → Call Flow API → Wait → Process
  → Synthesize everything yourself
```

**Problems:**
- Sequential thinking
- Single point of failure
- Limited expertise
- Manual coordination

### With Agent System: Coordinated Team in Parallel

```
You: "I need comprehensive analysis"

Team Manager (Root Agent):
  → Delegates to team

Team (Working in Parallel):
  ├─ Finance Specialist → Gets financial data (parallel)
  ├─ News Specialist → Gets news data (parallel)
  ├─ Sentiment Specialist → Gets sentiment data (parallel)
  └─ Flow Specialist → Gets flow data (parallel)

Team Manager:
  → Synthesizes all results intelligently
  → Returns complete answer
```

**Benefits:**
- True parallel execution
- Distributed expertise
- Intelligent coordination
- Professional synthesis

---

## Key Advantages

### 1. Intelligent Synthesis (Most Important!)

**Without Agent:**
```javascript
// Manual string concatenation:
"Recommendation: Buy. Risks: High valuation. News: 5 articles."
```

**With Agent:**
```javascript
// LLM-powered expert analysis:
"Based on comprehensive analysis, NVDA shows strong fundamentals 
(7.5/10). Recent news about AI chip development addresses competition 
risks mentioned earlier. The alignment between Reddit sentiment (62% 
bullish) and institutional flows (15M inflow) creates consensus support 
for a Buy recommendation..."
```

### 2. Natural Language Understanding

- Users can ask naturally: "What should I know about NVDA?"
- No need to know API endpoints
- Better user experience

### 3. Automatic Routing

- Agent figures out what's needed automatically
- No hardcoded logic required
- Handles new query types automatically

### 4. Context Awareness

- Maintains conversation state
- Can reference previous queries
- Natural follow-up questions

### 5. Professional Quality

- Expert-level analysis
- Actionable insights
- Reads like professional research

### 6. Speed

- ~4.5x faster (parallel execution)
- One network request vs multiple
- Internal calls are fast (function calls, not HTTP)

### 7. Error Handling

- Automatic retry
- Graceful degradation
- Fallback strategies

### 8. Frontend Simplicity

- Less code to maintain
- Easier to extend
- Loose coupling

---

## Summary

The agent system provides:

1. **Intelligent Synthesis** - Expert-level analysis vs manual combination
2. **Natural Language** - Better user experience
3. **Automatic Routing** - Less code, more flexible
4. **Context Awareness** - Better conversations
5. **Professional Quality** - High-quality output
6. **Speed** - Faster execution (bonus benefit)

**The agent system transforms complex multi-source queries into simple, intelligent interactions while providing professional-quality analysis.**

---

## Quick Reference

### Agent System Flow

```
User Query → Root Agent → Sub-Agents → Tools → Data → Synthesis → Response
```

### Key Files

- **Agent Definitions**: `app/agents/agents.py`
- **Scoring Engine**: `app/scoring/engine.py`
- **News Interpreter**: `fetch_data/news_analysis.py`
- **Main API**: `app/main.py`

### Key Concepts

- **ADK**: Agent Development Kit (Google's framework)
- **Root Agent**: Orchestrator that routes queries
- **Sub-Agents**: Specialized agents for specific tasks
- **Deep Alpha Score**: 7-pillar fundamental analysis (0-10)
- **News Interpreter**: LLM-powered news analysis

---

*This guide synthesizes information from: ARCHITECTURE_EXPLAINED.md, ROOT_AGENT_ROUTING.md, ADK_AND_ROUTING_EXAMPLES.md, SINGLE_VS_MULTIPLE_API_CALLS.md, TEAM_VS_INDIVIDUAL_ANALOGY.md, AGENT_SYSTEM_ADVANTAGES.md, and AGENT_SYSTEM_ANALOGIES.md*

