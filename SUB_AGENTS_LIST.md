# Current Sub-Agents in Deep Alpha Copilot

The agent system consists of **1 root agent** and **14 specialized sub-agents**:

## Root Agent
- **Financial_Root_Agent**: Main orchestrator that routes queries to appropriate sub-agents

## Sub-Agents (14 total)

1. **CompanyData_Agent** (graph_qa_subagent)
   - Purpose: Company financials, risks, scores, and investment analysis
   - Tool: `query_company_data`
   - Handles: Financial metrics, investment risks, scoring categories, buy/hold/sell recommendations

2. **DocumentRAG_Agent** (document_rag_subagent)
   - Purpose: Qualitative questions about company strategy and management outlook
   - Tool: `retrieve_from_documents`
   - Handles: SEC 10-K filing text, business strategy, detailed risk descriptions

3. **StockPricePredictor_Agent** (prediction_subagent)
   - Purpose: Predict next day's closing stock price
   - Tool: `predict_stock_price_tool`
   - Handles: ML-based price predictions

4. **NewsSearch_Agent** (news_search_subagent)
   - Purpose: Latest news headlines and summaries
   - Tool: `search_latest_news`
   - Handles: Recent news stories, press releases, market-moving events

5. **SectorNews_Agent** (sector_news_subagent)
   - Purpose: Sector-wide news and trends
   - Tool: `get_sector_news`
   - Handles: Industry-level news aggregation

6. **TokenUsage_Agent** (token_usage_subagent)
   - Purpose: API token usage tracking and analytics
   - Tool: `get_token_usage_stats`
   - Handles: Usage statistics and cost tracking

7. **MarketData_Agent** (market_data_subagent)
   - Purpose: Real-time market data and price information
   - Tool: `fetch_intraday_price_and_events`
   - Handles: Current prices, recent events, intraday data

8. **MarketIndices_Agent** (market_indices_subagent)
   - Purpose: Market index data and benchmarks
   - Tool: `get_market_indices`
   - Handles: S&P 500, NASDAQ, and other index data

9. **Twitter_Agent** (twitter_subagent)
   - Purpose: Twitter/X sentiment and social media analysis
   - Tool: `get_twitter_sentiment`
   - Handles: Social media sentiment tracking

10. **SectorMetrics_Agent** (sector_metrics_subagent)
    - Purpose: Sector-level metrics and benchmarks
    - Tool: `get_sector_metrics`
    - Handles: Industry comparisons and sector analysis

11. **FlowData_Agent** (flow_data_subagent)
    - Purpose: Institutional and retail flow data
    - Tool: `get_flow_data`
    - Handles: Ownership changes, flow analysis

12. **RedditSentiment_Agent** (reddit_sentiment_subagent)
    - Purpose: Reddit sentiment analysis
    - Tool: `get_reddit_sentiment`
    - Handles: Reddit discussions and sentiment

13. **CEOLookup_Agent** (ceo_lookup_subagent)
    - Purpose: CEO and leadership information
    - Tool: `query_ceo_info_by_ticker`
    - Handles: Executive profiles, leadership analysis

14. **AgentEvaluator_Agent** (agent_evaluator_subagent)
    - Purpose: Quality control and fact-checking
    - Tool: `fact_check_agent_output`
    - Handles: Validates agent outputs for accuracy

## Current Status

- **ADK Available**: The system checks for Google ADK (Agent Development Kit) availability
- **Fallback Mode**: If ADK is not available, the system uses direct tool calls without agent orchestration
- **Chatbot**: Works in fallback mode, handling momentum, sentiment, risks, financials, and news questions

## Note

The chatbot currently works via fallback mode when ADK is not available. The fallback handler directly processes questions about:
- Momentum analysis
- Sentiment analysis  
- Company risks
- Financial health
- Latest news

All sub-agents are defined but require ADK to be fully functional for intelligent routing and orchestration.

