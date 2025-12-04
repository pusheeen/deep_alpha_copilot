# Deep Alpha Copilot - Architecture Explained

## 🏗️ Agent Architecture Overview

The Deep Alpha Copilot uses a **hierarchical multi-agent system** built on Google's ADK (Agent Development Kit) framework. The architecture follows a **root agent + specialized sub-agents** pattern.

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
        │   NewsSearch_Agent        │  │  StockPricePredictor_Agent│
        │   (Latest News)           │  │  (ML Price Prediction)   │
        └──────────────────────────┘  └──────────────────────────┘
                            │                    │
                            ▼                    ▼
        ┌──────────────────────────┐  ┌──────────────────────────┐
        │   RedditSentiment_Agent   │  │  FlowData_Agent          │
        │   (Social Sentiment)      │  │  (Institutional Flows)   │
        └──────────────────────────┘  └──────────────────────────┘
                            │
                            ▼
        ... (13 total sub-agents)
```

### Root Agent: `Financial_Root_Agent`

**Purpose**: The orchestrator that interprets user queries and delegates to specialized sub-agents.

**Model**: Gemini 2.5 Pro (via ADK LiteLlm wrapper)

**Key Responsibilities**:
- Analyzes user intent from natural language queries
- Routes queries to the most appropriate sub-agent(s)
- Synthesizes responses from multiple sub-agents when needed
- Maintains context across multi-turn conversations

**Delegation Logic**: The root agent uses instruction-based routing:
- Financial data → `CompanyData_Agent`
- Latest news → `NewsSearch_Agent`
- Price predictions → `StockPricePredictor_Agent`
- Social sentiment → `RedditSentiment_Agent`
- CEO info → `CEOLookup_Agent`
- Flow data → `FlowData_Agent`
- etc.

---

## 📊 How the Deep Alpha Score is Generated

The **Deep Alpha Score** is a composite score (0-10 scale) that evaluates stocks across **7 fundamental pillars**. It's computed by `app/scoring/engine.py` in the `compute_company_scores()` function.

### Score Calculation Flow

```
1. Data Loading
   ├── Financial statements (annual/quarterly)
   ├── Earnings data (EPS surprises)
   ├── Price history (OHLCV)
   ├── Yahoo Finance live data
   ├── Reddit/Twitter sentiment
   └── CEO profiles

2. Component Score Computation (7 Pillars)
   ├── Business Score (0-10)
   ├── Financial Score (0-10)
   ├── Sentiment Score (0-10)
   ├── Critical Path Score (0-10)
   ├── Leadership Score (0-10)
   ├── Earnings Score (0-10)
   └── Technical Score (0-10)

3. Overall Score Aggregation
   └── Weighted average → Deep Alpha Score (0-10)
```

### The 7 Pillars Explained

#### 1. **Business Score** (Weight: 20%)
**Purpose**: Evaluates revenue growth, profitability, and competitive moat.

**Key Metrics**:
- **Revenue CAGR**: Compound Annual Growth Rate (filters annual data by fiscal year-end)
- **Gross Margin**: Profitability indicator
- **R&D Intensity**: Innovation investment (% of revenue)
- **Sector Growth Bonus**: Industry-specific growth multipliers

**Calculation**:
```python
# Filters annual data (Dec 31, Oct 31, Sep 30, Jan 31)
annual_revenue = revenue_series[(month == 12) & (day == 31)]
revenue_cagr = calculate_cagr(annual_revenue[-4:])

# Scores from thresholds
revenue_score = score_from_thresholds(revenue_cagr, 
    [(-0.05, 2), (0.0, 4), (0.05, 6), (0.15, 8), (0.30, 10)])
```

#### 2. **Financial Score** (Weight: 25%)
**Purpose**: Assesses financial health, profitability, and efficiency.

**Key Metrics**:
- **Net Income CAGR**: Profit growth trajectory
- **ROE (Return on Equity)**: Profitability efficiency
- **Current Ratio**: Liquidity indicator
- **Debt-to-Equity**: Leverage assessment

**Calculation**:
```python
# Filters annual net income
annual_net_income = net_income_series[(month == 12) & (day == 31)]
net_income_cagr = calculate_cagr(annual_net_income[-4:])

# Combines multiple financial metrics
financial_score = weighted_average([cagr_score, roe_score, liquidity_score])
```

#### 3. **Sentiment Score** (Weight: 15%)
**Purpose**: Measures market sentiment from news and social media.

**Key Metrics**:
- **News Sentiment**: VADER sentiment analysis on headlines (weighted by recency)
- **Reddit Sentiment**: Bullish/bearish ratio from Reddit posts
- **Twitter Sentiment**: Social media buzz (optional)

**Calculation**:
```python
# News sentiment (age-weighted)
for news_item in news_items:
    sentiment = sentiment_analyzer.polarity_scores(title)
    weight = max(0.2, 1 - (age_days / 30))  # Recent news weighted higher
    sentiments.append(sentiment["compound"] * weight)

# Reddit sentiment
reddit_ratio = (bullish_posts - bearish_posts) / total_posts
reddit_score = score_from_thresholds(reddit_ratio, thresholds)

# Combined
sentiment_score = mean([news_score, reddit_score])
```

#### 4. **Critical Path Score** (Weight: 10%)
**Purpose**: Evaluates strategic positioning and critical success factors.

**Key Metrics**:
- **Sector-specific critical factors** (e.g., for Tech: AI infrastructure layer, export controls)
- **Policy tailwinds** (e.g., CHIPS Act, defense contracts)
- **Strategic relevance** to national priorities

**Calculation**:
```python
# Sector-aware scoring
critical_factors = CRITICAL_PATH_MAP.get(sector, {})
critical_score = evaluate_critical_factors(ticker, info, critical_factors)
```

#### 5. **Leadership Score** (Weight: 10%)
**Purpose**: Assesses CEO quality and leadership stability.

**Key Metrics**:
- **CEO Tenure**: Years in position
- **CEO Background**: Past experience and track record
- **Leadership Stability**: Turnover history

**Calculation**:
```python
ceo_profile = load_ceo_profile(ticker)
tenure_years = calculate_tenure(ceo_profile["start_date"])
leadership_score = score_from_thresholds(tenure_years, 
    [(2, 4), (5, 6), (10, 8), (15, 9), (20, 10)])
```

#### 6. **Earnings Score** (Weight: 10%)
**Purpose**: Evaluates earnings quality and consistency.

**Key Metrics**:
- **EPS Trend**: Earnings per share growth trajectory
- **Revenue Trend**: Revenue growth consistency
- **Earnings Consistency**: Stability of earnings beats

**Calculation**:
```python
eps_trend = calculate_trend(earnings_df["eps"])
revenue_trend = calculate_trend(earnings_df["revenue"])
consistency = count_consecutive_beats(earnings_df)

earnings_score = mean([eps_score, revenue_score, consistency_score])
```

#### 7. **Technical Score** (Weight: 10%)
**Purpose**: Analyzes price action and technical indicators.

**Key Metrics**:
- **RSI (14-day)**: Overbought/oversold indicator
- **Moving Averages**: MA50 vs MA200 (trend confirmation)
- **Volume**: Volume trends vs 30-day average
- **Returns**: 6-month and 12-month returns

**Calculation**:
```python
rsi = compute_rsi(closes, period=14)
ma50 = closes.rolling(50).mean()
ma200 = closes.rolling(200).mean()

# Score based on technical position
if ma50 > ma200 and rsi < 70:
    technical_score = 8.0  # Bullish trend, not overbought
elif ma50 < ma200 and rsi > 30:
    technical_score = 3.0  # Bearish trend, not oversold
```

### Overall Score Aggregation

The final **Deep Alpha Score** is a **weighted average** of the 7 component scores:

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

**Confidence Calculation**:
- Uses variance of component scores to compute confidence
- Higher variance → lower confidence
- Confidence range: 40% - 95%

**Recommendation Mapping**:
- **Score ≥ 8.0**: "Strong Buy" (Long-term, 12-24 months)
- **Score ≥ 7.0**: "Buy" (Long-term, 12-18 months)
- **Score ≥ 4.0**: "Hold" (Medium-term, 6-12 months)
- **Score < 4.0**: "Sell" (Short-term, <6 months)

---

## 📰 How the News Interpreter Works

The **News Interpreter** (`fetch_data/news_analysis.py`) uses **Google Gemini** to analyze news articles through the Deep Alpha 7-Pillar framework.

### News Interpretation Flow

```
1. News Collection
   ├── Google Custom Search API (last 72 hours)
   ├── Yahoo Finance news feed
   └── Cached news articles (12-hour TTL)

2. Context Gathering
   ├── Company fundamentals (P/E, ROE, momentum)
   ├── Sector metrics (quality score, momentum, ROE)
   ├── Market conditions (NASDAQ 1-month change)
   ├── Technical snapshot (RSI, SMA position, volume)
   └── AI infrastructure layer (for tech companies)

3. LLM Analysis (Gemini)
   ├── Primary: gemini-2.0-flash-exp
   ├── Fallback: gemini-1.5-flash (if quota exceeded)
   └── Deep Alpha 7-Pillar assessment

4. Output Generation
   └── JSON with rating, takeaways, investment conclusion
```

### Deep Alpha 7-Pillar News Analysis

The interpreter evaluates news impact across **all 7 pillars**, but **dynamically selects relevant metrics** based on the company's sector:

#### Sector-Aware Pillar Metrics

**Pillar A (Fundamentals & Growth)**:
- **Tech/AI**: 3-5 year CAGR, R&D Intensity, Forward EPS
- **Energy/Defense**: Margin on Backlog, CapEx, Contract Stability
- **Consumer**: Same-Store Sales Growth, Inventory Turnover
- **Finance**: Net Interest Margin, Loan Growth, ROE
- **Healthcare**: Clinical Trial Progression, Blockbuster Revenue

**Pillar B (Valuation)**:
- **Tech/AI**: PEG Ratio, P/S, EV/Sales
- **Energy/Defense**: P/B, Free Cash Flow Yield
- **Consumer**: EV/Sales, Debt/EBITDA
- **Finance**: Price-to-Tangible Book Value
- **Healthcare**: P/S, Sum-of-the-Parts Valuation

**Pillar C (Competitive Moat)**:
- **Tech/AI**: Ecosystem Lock-in, Developer Dependency, IP Depth
- **Energy/Defense**: Resource Independence, Regulatory Barriers
- **Consumer**: Brand Strength, Supply Chain Advantage
- **Finance**: Deposit Base Scale, Regulatory Barriers
- **Healthcare**: Patent Expiration, Drug Uniqueness

**Pillar D (Strategic Relevance/Policy)**:
- **Tech/AI**: Export Control Exposure, CHIPS Act, US-China Decoupling
- **Energy/Defense**: National Security Mandates, DOE/DoD Contracts
- **Consumer**: Interest Rate Sensitivity, Labor Law Changes
- **Finance**: Tier 1 Capital Requirements, Rate Policy
- **Healthcare**: FDA Approval Timelines, Pricing Legislation

**Pillar E (Demand Visibility)**:
- **Tech/AI**: New Design Wins, Backlog/Book-to-Bill
- **Energy/Defense**: Long-term Contract Signings
- **Consumer**: Booking Trends, Same-Store Sales Guidance
- **Finance**: Loan Application Volume
- **Healthcare**: Phase 3 Trial Readouts

**Pillar F (AI Supply Chain Lens)**:
- **All Sectors**: AI-driven demand/efficiency gains, Substitution Risk

**Pillar G (Technical Analysis)**:
- **All Sectors**: RSI, SMA trends, Volume confirmation

### LLM Prompt Structure

The interpreter sends a comprehensive prompt to Gemini:

```python
prompt = f"""
SYSTEM INSTRUCTION:
You are a Deep Alpha Analyst applying the 7-Pillar Framework.

COMPANY: {ticker}
SECTOR: {sector}
NEWS: {news_summaries}
CONTEXTUAL DATA:
- Company Fundamentals: {company_context}
- Sector Metrics: {sector_context}
- Market Conditions: {market_context}
- Technical Data: RSI={rsi}, SMA={sma_position}, Volume={volume_change}

TASK: Assess news impact on all 7 pillars (A-G) with sector-specific metrics.

OUTPUT: JSON with:
- rating_buy_hold_sell
- sentiment_confidence
- key_takeaways (3 types: Fundamental, Strategic, Technical)
- investment_conclusion (150-200 words)
- next_step_focus (monitoring points)
"""
```

### Fallback Strategy

**Primary Model**: `gemini-2.0-flash-exp`
- Fast, experimental model
- May hit quota limits

**Fallback Model**: `gemini-1.5-flash`
- More stable, higher quota
- Used if primary model fails due to quota

**Error Handling**:
- Retries with exponential backoff (max 3 attempts)
- Falls back to secondary model if quota exceeded
- Returns error JSON if all attempts fail

### Output Format

```json
{
  "rating_buy_hold_sell": "BUY/HOLD/SELL",
  "sentiment_confidence": "High/Medium/Low",
  "key_takeaways": [
    {
      "type": "Fundamental Impact (Pillars A/B/E)",
      "summary": "..."
    },
    {
      "type": "Strategic Moat & Policy Shift (Pillars C/D/F)",
      "summary": "..."
    },
    {
      "type": "Technical Noise Filter (Pillar G)",
      "summary": "..."
    }
  ],
  "investment_conclusion": {
    "paragraph": "150-200 word summary...",
    "reasoning_justification": "1-2 sentence justification..."
  },
  "next_step_focus": {
    "title": "Next Step: Monitoring Key Alpha Drivers",
    "monitor_points": [...]
  },
  "model_used": "gemini-2.0-flash-exp",
  "fallback_used": false
}
```

---

## 🤖 Which Agent Does What?

### Complete Agent Inventory

| Agent Name | Tool(s) | Purpose | Data Source |
|------------|---------|---------|-------------|
| **CompanyData_Agent** | `query_company_data()` | Financial analysis, scores, risks, recommendations | JSON scorecards (`compute_company_scores()`) |
| **DocumentRAG_Agent** | `retrieve_from_documents()` | SEC filing analysis, management outlook | Neo4j embeddings (currently disabled) |
| **NewsSearch_Agent** | `search_latest_news()` | Latest news headlines for specific companies | Google Custom Search API |
| **SectorNews_Agent** | `get_sector_news()` | Sector-wide news and analysis | Google Custom Search API |
| **MarketData_Agent** | `fetch_intraday_price_and_events()` | Real-time price quotes, Yahoo Finance news | `yfinance` library |
| **StockPricePredictor_Agent** | `predict_stock_price_tool()` | Next-day price prediction | LightGBM models (`app/models/saved_models/`) |
| **RedditSentiment_Agent** | `query_reddit_sentiment()` | Reddit sentiment analysis (past 7 days) | Reddit API (PRAW) |
| **Twitter_Agent** | `query_twitter_sentiment()` | Twitter/X sentiment analysis | Twitter API (optional) |
| **CEOLookup_Agent** | `query_ceo_info_by_ticker()` | CEO information lookup | `data/companies.csv`, web scraping |
| **MarketIndices_Agent** | `query_market_indices()` | Market index data (VIX, NASDAQ, Dow) | `yfinance` |
| **SectorMetrics_Agent** | `query_sector_metrics()` | Sector-level financial metrics | `data/structured/sector_metrics/` |
| **TokenUsage_Agent** | `query_token_usage()` | AI token consumption statistics | OpenRouter API |
| **FlowData_Agent** | `query_flow_data()` | Institutional/retail flow data | `data/structured/flow_data/` |

### Agent Usage Examples

#### Example 1: "What are the risks for NVDA?"
```
User Query → Financial_Root_Agent
  ↓
Routes to: CompanyData_Agent
  ↓
Tool Call: query_company_data(ticker="NVDA", data_type="risks")
  ↓
Returns: Risk analysis from Deep Alpha scoring engine
```

#### Example 2: "What's the latest news about TSLA?"
```
User Query → Financial_Root_Agent
  ↓
Routes to: NewsSearch_Agent
  ↓
Tool Call: search_latest_news(query="TSLA Tesla", max_results=10)
  ↓
Returns: Latest headlines from Google Custom Search
```

#### Example 3: "Predict tomorrow's price for AAPL"
```
User Query → Financial_Root_Agent
  ↓
Routes to: StockPricePredictor_Agent
  ↓
Tool Call: predict_stock_price_tool(ticker="AAPL")
  ↓
Returns: Next-day price prediction from LightGBM model
```

#### Example 4: "What's the Reddit sentiment on GME?"
```
User Query → Financial_Root_Agent
  ↓
Routes to: RedditSentiment_Agent
  ↓
Tool Call: query_reddit_sentiment(ticker="GME")
  ↓
Returns: Bullish/bearish ratio from Reddit posts
```

### Agent Communication Pattern

1. **User sends query** → FastAPI `/chat` endpoint
2. **FastAPI forwards** → ADK AgentCaller
3. **Root agent analyzes** → Determines which sub-agent(s) to use
4. **Sub-agent executes** → Calls tool(s) and gathers data
5. **Root agent synthesizes** → Combines results into final answer
6. **Response returned** → To user via FastAPI

### Key Design Principles

1. **Separation of Concerns**: Each agent has a single, well-defined responsibility
2. **Tool-Based Architecture**: Agents don't directly access data; they use tools
3. **Graceful Degradation**: If an agent/tool fails, others continue working
4. **Deterministic Scoring**: Deep Alpha scores are computed from cached JSON files
5. **Live Data Integration**: Some agents fetch real-time data (news, prices, sentiment)

---

## 🔄 Data Flow Summary

### Scoring Pipeline
```
Local JSON Files → compute_company_scores() → 7 Component Scores → Overall Score
```

### News Interpretation Pipeline
```
Google Search API → News Articles → Gemini LLM → Deep Alpha Analysis → JSON Output
```

### Agent Query Pipeline
```
User Query → Root Agent → Sub-Agent → Tool → Data Source → Response
```

---

## 📝 Key Files Reference

- **Agent Definitions**: `app/agents/agents.py`
- **Scoring Engine**: `app/scoring/engine.py`
- **News Interpreter**: `fetch_data/news_analysis.py`
- **Main API**: `app/main.py`
- **Architecture Doc**: `AGENT_ARCHITECTURE.md`

---

This architecture enables the Deep Alpha Copilot to provide comprehensive, multi-faceted investment analysis by combining structured financial data, real-time news, social sentiment, and AI-powered interpretation.

