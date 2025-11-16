# Deep Alpha Copilot – Agent Architecture

This document explains how data, analytics, and the Google ADK agent team fit together inside the Deep Alpha Copilot codebase. Use it as a map when extending the agent, debugging tool calls, or onboarding new contributors.

## Layered System Overview

```
┌────────────────────────────────────────────────────────────────────┐
│  Presentation Layer                                                 │
│  • Jinja dashboard (app/templates/index.html)                        │
│  • /chat endpoint consumed by the web UI and external callers        │
└────────────────────────────────────────────────────────────────────┘
                │ FastAPI (app/main.py)
                ▼
┌────────────────────────────────────────────────────────────────────┐
│  Intelligence Layer                                                 │
│  • Google ADK root agent + sub-agents (app/agents/agents.py)        │
│  • Scoring engine + analytics helpers (app/scoring/engine.py)       │
│  • Predictive models (app/models/*.py)                              │
└────────────────────────────────────────────────────────────────────┘
                │ Tools read/write JSON caches instead of Neo4j
                ▼
┌────────────────────────────────────────────────────────────────────┐
│  Data Layer                                                         │
│  • Offline ingestion scripts & tasks (fetch_data.py, app/tasks.py)  │
│  • Structured data: data/structured/* (financials, prices, etc.)    │
│  • Unstructured data: data/unstructured/* (news, filings, Reddit)   │
│  • Runtime caches: data/runtime/* for hot responses                 │
└────────────────────────────────────────────────────────────────────┘

Cloud Run / Docker simply package the FastAPI app and its data bundle.

## Data & Knowledge Sources

### Ingestion Scripts

| Module | Purpose | Key Outputs |
| --- | --- | --- |
| `fetch_data.py` | Multi-source ETL that pulls SEC filings, Yahoo Finance prices, CEO bios, Reddit/X/news sentiment, etc. | Populates `data/structured/*`, `data/unstructured/*`, and report CSVs. |
| `app/tasks.py` (Celery) | Batch refresh of Yahoo income statements; can be scheduled separately from the main API. | `data/structured/financials/{TICKER}_financials.json`. |
| `populate_graph.py`, `app/neo4j_for_adk.py` | Historical path for Neo4j graph ingestion. Current agent flow operates on JSON caches but scaffolding remains for future graph queries (Neo4j is not part of the live deployment). | Optional Neo4j database (currently unused). |

Tickers of interest live in `target_tickers.py`; both ingestion and runtime layers read from this single source of truth.

### Storage Layout

```
data/
├── structured/            # deterministic numeric data
│   ├── financials/        # annual/quarterly statements per ticker
│   ├── prices/            # price histories (CSV)
│   ├── earnings/          # EPS surprises, etc.
│   └── sector_metrics/    # benchmark multiples + company metadata
├── unstructured/
│   ├── 10k/               # filing text chunks
│   ├── news/ + news_interpretation/   # raw stories + LLM cards
│   ├── reddit/            # cached subreddit scrapes
│   └── x/                 # Twitter/X pulls when enabled
└── runtime/
    ├── company/           # latest scorecards per ticker
    ├── news/              # cached payloads for /api/latest-news
    └── price_snapshots/   # ad-hoc intraday snapshots
```

The scoring engine and agents read from these JSON/CSV files at runtime, which keeps inference deterministic and removes the need for live database connections in Cloud Run.

## Analytics Core (Scoring + Insights)

*File: `app/scoring/engine.py`*

1. **`compute_company_scores(ticker)`**  
   - Aggregates structured fundamentals, YFinance data, Reddit sentiment caches, CEO profiles, and runtime news to produce scores across six categories (Financial, Business, Leadership, Technical, Sentiment, Risk) plus an overall recommendation object.  
   - Applies sector-specific heuristics (e.g., `CRITICAL_PATH_MAP`, `SECTOR_GROWTH_BONUS`) and runtime caching via `_update_runtime_cache`.
2. **Auxiliary endpoints** expose price history, valuation multiples, market condition indicators, and watchlists to the UI and the agent tools.
3. **Serialization helpers** (`safe_json_serialize`, `sanitize_for_json`) protect FastAPI responses from NaN/inf issues.

Because this module is pure Python and file-based, it can be executed inside `asyncio` executors from `app/main.py` as well as directly from agent tools such as `query_company_data`.

## Predictive Modeling Layer

*Files: `app/models/train_predictor.py`, `app/models/predict.py`*

- LightGBM regressors are trained per ticker with engineered lag/rolling features derived from `data/structured/prices/*`.  
- Trained assets live under `app/models/saved_models/` (`*_price_regressor.joblib` and feature lists).  
- `predict_next_day_price()` loads the relevant model on demand and powers the `StockPricePredictor_Agent`.

## FastAPI Runtime (`app/main.py`)

Key responsibilities:

- Bootstraps Stripe/payment config, SQLite auth tables, and runtime caches.
- On startup, if Google ADK is installed, instantiates `root_agent` via `AgentCaller`. The ADK runner lives entirely in memory using `InMemorySessionService`.
- Exposes REST endpoints for:
  - `/` dashboard (Jinja template consuming `/api/*` endpoints).
  - `/api/scores/{ticker}`, `/api/price-history/{ticker}`, `/api/valuation-metrics/{ticker}`, `/api/latest-news/{ticker}`, `/api/market-conditions`.
  - `/chat` → streams user queries into the ADK agent and returns the final synthesized response (plus optional reasoning traces).
- Manages lightweight session-based authentication for gated UI features.

FastAPI never calls the LLM directly. Instead, it hands the full request payload to the ADK runner, which in turn orchestrates the sub-agents and tool calls described next.

## Google ADK Agent Team (`app/agents/agents.py`)

### Root Agent

`Financial_Root_Agent` is the top-level coordinator. It runs Gemini 2.5 Flash through the ADK `LiteLlm` wrapper and is configured with the full list of supported tickers. Delegation logic is embedded in the instruction block and determines which sub-agent should receive a conversation turn.

### Sub-Agents and Tools

| Sub-agent | Tool(s) | Purpose | Data dependencies |
| --- | --- | --- | --- |
| `CompanyData_Agent` | `query_company_data` | Primary interface to `compute_company_scores`. Supports filtered slices (`risks`, `financials`, `scores`, `recommendation`, `all`). | JSON scorecards + runtime caches. |
| `DocumentRAG_Agent` | `retrieve_from_documents` | Intended to run vector search over Neo4j embeddings for 10-K filings. Currently returns a disabled message until Neo4j is re-enabled. | Neo4j `filings` index (offline). |
| `NewsSearch_Agent` | `search_latest_news` | Uses Google Custom Search API (Gemini-compatible key & CX) to grab fresh headlines with metadata. | Internet + Google API credentials. |
| `MarketData_Agent` | `fetch_intraday_price_and_events` | Pulls delayed intraday quotes and Yahoo Finance news for supported tickers. Provides change %, timestamp, and event list. | `yfinance`, `TARGET_TICKERS`. |
| `StockPricePredictor_Agent` | `predict_stock_price_tool` | Discovers trained models dynamically (`app/models/saved_models/*`). Adds compliance reminder in instructions. Currently dormant because prediction models are not deployed. | Joblib models + price CSVs (not yet provisioned in prod). |
| `RedditSentiment_Agent` | `query_reddit_sentiment` | Live PRAW queries across curated subreddits; uses VADER for sentiment scoring and returns aggregate stats plus top posts. | Reddit API credentials, `vaderSentiment`. |
| `CEOLookup_Agent` | `query_ceo_info_by_ticker` | Scrapes LinkedIn/company pages to return CEO identity, tenure, and profile links, falling back to CSV data. | `data/companies.csv`, scraped HTML. |
| (Deprecated) `CompanyGraph_Agent` | `query_graph_database` | Keeps prompts for generating Cypher queries against an SEC knowledge graph. Currently disabled because Neo4j is optional. | Neo4j if re-enabled. |

All tools share the same `LiteLlm` client and Vertex embedding model (`text-embedding-005`), so credentials for Vertex AI must be present in the environment.

### Control Flow

1. `/chat` receives `QueryRequest`.
2. FastAPI forwards it to `AgentCaller.call()`, which wraps ADK’s asynchronous runner.
3. The root agent interprets the request, delegates to one or more sub-agents, and executes the associated tool(s). Tool inputs/outputs are streamed back as intermediate ADK events.
4. Once all necessary observations are collected, the root agent composes the final response and ADK returns it to FastAPI.

If ADK packages are missing, the app degrades gracefully: `/chat` replies with `agent_unavailable` and the rest of the analytics endpoints remain online.

## Typical Data Flows

### 1. Data Refresh

1. Run `python fetch_data.py` (optionally limited to specific tickers).  
2. Script gathers fundamentals, filings, sentiment, and news, writing JSON/CSV artifacts under `data/*`.  
3. (Optional) Celery task `fetch_financial_statements_batch` refreshes financial statements in parallel.  
4. Score caches are regenerated on-demand the next time `/api/scores/{ticker}` or `query_company_data` is called.

### 2. User Chat Session

1. User enters a prompt in the web UI.  
2. Frontend calls `/chat` with `{question, include_reasoning}`.  
3. ADK root agent decides which specialization(s) to invoke (e.g., `CompanyData_Agent` for fundamentals plus `NewsSearch_Agent` for latest events).  
4. Tool outputs are merged into the final Gemini-written answer with source notes and risk disclaimers before being returned to the UI.

### 3. Dashboard API Call

1. `/api/scores/{ticker}` runs `compute_company_scores` inside a threadpool, sanitizes the payload, and returns JSON to the dashboard.  
2. The same data is also available to the agent tools, ensuring consistency between automated answers and raw UI panels.

## External Services & Configuration

- **LLMs**: Gemini 2.5 Flash via `LiteLlm`, optional Anthropic model (`NEWS_LLM_MODEL`) for news interpretation, Vertex embeddings for RAG.
- **Market Data**: Yahoo Finance (`yfinance`), `TARGET_TICKERS` list controls allowed symbols.
- **Search & News**: Google Custom Search API (requires `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`).
- **Social Sentiment**: Reddit (PRAW), optional Twitter/X (`tweepy`).
- **Payments**: Stripe environment variables when subscription gating is enabled.
- **Database/Cache**: SQLite for users, JSON files for analytics, optional Neo4j for graph mode.

Ensure `.env` includes all relevant keys before deploying to Cloud Run or running locally.

## Extending the Agent

1. **Add a new tool**  
   - Implement a pure function in `app/agents/agents.py` (or another module) that returns JSON-serializable data.  
   - Wire it into a new `Agent` instance with clear instructions, input validation, and disclaimers.  
   - Register the sub-agent inside the `root_agent`’s `sub_agents` list.
2. **Introduce a new data source**  
   - Update `fetch_data.py` (or create a dedicated ingestion script) to materialize artifacts under `data/`.  
   - Extend `compute_company_scores` or create a specialized tool that consumes the new files.  
   - Add caching hooks if the data should appear in runtime JSON payloads.
3. **Re-enable Neo4j RAG**  
   - Configure `NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`.  
   - Remove the “disabled” early returns in `query_graph_database` and `retrieve_from_documents`, and ensure embeddings are indexed in Neo4j as expected.

Keeping ingestion deterministic and tools thin makes it straightforward to unit test each layer and reason about agent behavior in production.

---

For a quick start on local development: populate `data/` via `python fetch_data.py`, run `uvicorn app.main:app --reload`, and test `/chat` to observe the agent delegation logs printed by ADK.
