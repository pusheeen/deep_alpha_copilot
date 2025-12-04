# Deep Alpha Copilot

An AI-powered financial analysis platform that provides comprehensive stock scoring and investment insights using multiple data sources including financial statements, news, social sentiment, and technical indicators.

## Features

- **Comprehensive Stock Scoring**: Multi-dimensional analysis across 7 key areas (Deep Alpha 7-Pillar Framework):
  - Business Score (20% weight) - Revenue growth, competitive moat, R&D intensity
  - Financial Score (25% weight) - Profitability, liquidity, leverage, ROE
  - Sentiment Score (15% weight) - News sentiment, Reddit/Twitter sentiment
  - Critical Path Score (10% weight) - Strategic positioning, policy tailwinds
  - Leadership Score (10% weight) - CEO tenure, background, track record
  - Earnings Score (10% weight) - EPS/revenue trends, consistency
  - Technical Score (10% weight) - RSI, moving averages, volume, momentum

- **Real-Time Market Data**:
  - Intraday price data with 5-minute intervals for 1-day view
  - Historical price data with customizable time periods
  - Live market condition indicators (VIX, Fear & Greed Index, Put/Call Ratio)

- **AI-Powered News Analysis**:
  - Automated news fetching from the last 72 hours
  - AI filtering for company-specific and factual news
  - **3-Tier Fallback System** for reliable interpretation:
    - Tier 1: Google Gemini models (2.0 Flash Exp, 1.5 Flash)
    - Tier 2: OpenRouter open source models (Gwen, Llama, Mistral, Gemma, Qwen)
    - Tier 3: Template-based fallback (always works)
  - Deep Alpha 7-Pillar framework analysis with actionable insights
  - News refreshes every 12 hours with "last updated" timestamp
  - News sentiment analysis integrated into overall scoring

- **Interactive Visualizations**:
  - Real-time price charts with event markers
  - Historical valuation metrics (P/E, P/S ratios) with industry benchmarks
  - Time-varying industry benchmarks based on S&P 500 movements
  - Multi-stock comparison charts

- **AI Chat Assistant**:
  - Google ADK-powered conversational agent with 13 specialized sub-agents
  - Single API call handles complex multi-source queries automatically
  - Context-aware responses using company data and latest news
  - Natural language queries about stocks, market trends, and investment strategies
  - Intelligent routing to specialized agents (financial, news, sentiment, flow data, etc.)

- **Performance Optimizations**:
  - Ticker-first UI: Load user's requested ticker immediately (~0.5s)
  - Background loading: Silently loads all other tickers with progress bar
  - Lazy loading: Data downloaded on-demand from Cloud Storage
  - 85-90% faster initial load compared to loading all tickers upfront

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Google Cloud Run**: Serverless deployment platform
- **Google Cloud Storage**: Data persistence and caching
- **Google Gemini 2.5 Pro/Flash**: LLM for news analysis and chat (primary)
- **OpenRouter API**: Open source model fallbacks (Gwen, Llama, Mistral, Gemma, Qwen)
- **Google ADK**: Agentic framework for intelligent chat assistant

### Data Sources
- **yfinance**: Stock prices and financial data
- **SEC EDGAR**: Official financial filings
- **Google Custom Search API**: Latest financial news (last 72 hours)
- **Reddit API (PRAW)**: Social sentiment from Reddit (past 7 days)
- **Twitter/X API**: Social sentiment (optional)
- **Yahoo Finance**: Company news and events

### Frontend
- **TailwindCSS**: Utility-first CSS framework
- **Chart.js**: Interactive data visualizations
- **Vanilla JavaScript**: No framework dependencies for fast loading

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                  Frontend (HTML/JS)                 │
│  - Stock scoring dashboard                          │
│  - Interactive charts                               │
│  - AI chat interface                                │
└─────────────────────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────┐
│              FastAPI Backend (Cloud Run)            │
│  - REST API endpoints                               │
│  - Scoring engine                                   │
│  - Google ADK agent                                 │
└─────────────────────────────────────────────────────┘
                        │
        ┌───────────────┴───────────────┐
        ▼                               ▼
┌──────────────────┐          ┌──────────────────┐
│   Local Data     │          │  External APIs   │
│  - CSV files     │          │  - yfinance      │
│  - JSON caches   │          │  - SEC EDGAR     │
└──────────────────┘          │  - Reddit        │
                              │  - Twitter/X     │
                              │  - News APIs     │
                              └──────────────────┘
```

## Project Structure

```
deep_alpha_copilot/
├── app/
│   ├── main.py                 # FastAPI application
│   ├── scoring/
│   │   ├── __init__.py
│   │   └── engine.py           # Core scoring logic
│   ├── agents/
│   │   └── agents.py           # Google ADK agent definitions
│   └── templates/
│       └── index.html          # Main UI
├── data/
│   ├── structured/
│   │   ├── financials/         # Company financial data
│   │   ├── prices/             # Historical price data
│   │   └── earnings/           # Quarterly earnings
│   └── unstructured/
│       ├── news/               # News articles
│       ├── news_interpretation/ # AI-generated insights
│       ├── reddit/             # Reddit posts
│       └── x/                  # Twitter/X posts
├── fetch_data.py               # Data collection script
├── target_tickers.py           # Supported tickers configuration
├── requirements.txt            # Python dependencies
├── Dockerfile                  # Container configuration
└── cloudbuild.yaml            # Google Cloud Build config
```

## Data Storage Layout

- `data/structured/`
  - `financials/`, `earnings/`, `prices/`: point-in-time datasets produced by the ingestion pipeline.
  - `sector_metrics/`: rolling company and sector aggregates (latest file drives ticker discovery and industry benchmarks).
  - `industry_benchmarks.json`: cached reference P/E and P/S ratios.
- `data/unstructured/`
  - `news/` and `news_interpretation/`: historical article dumps plus AI summaries generated during ingestion.
  - `reddit/`, `x/`: sentiment snapshots captured from social channels.
- `data/company/{TICKER}.json`: static profile composed from the latest sector metrics and `companies.csv`. Example:
  ```json
  {
    "ticker": "NVDA",
    "name": "NVIDIA Corp",
    "industry": "Semiconductors",
    "sources": {
      "metrics_file": "company_metrics_20251026_223134.json",
      "companies_csv": "companies.csv"
    },
    "metrics": { "...": "..." },
    "updated_at": "2025-10-30T04:15:05.312Z"
  }
  ```
- `data/runtime/`
  - `price_snapshots/{TICKER}.json`: most recent price pull served to the UI. Schema:
    ```json
    {
      "ticker": "NVDA",
      "fetched_at": "2025-10-30T04:15:05.312Z",
      "period": "1m",
      "current": {
        "date": "2025-10-29",
        "open": 205.11,
        "high": 207.37,
        "low": 204.90,
        "close": 207.05,
        "volume": 307574800,
        "daily_change": 0.55
      },
      "trend": {
        "start_date": "2025-09-29",
        "end_date": "2025-10-29",
        "start_price": 139.30,
        "end_price": 207.05,
        "price_change": 67.75,
        "price_change_pct": 48.64,
        "direction": "up",
        "high": 207.37,
        "low": 86.61,
        "avg_volume": 225777778
      }
    }
    ```
  - `news/{TICKER}_realtime_news.json`: live news cache used by the UI. Each refresh merges Google Custom Search headlines with the latest Yahoo Finance dump and de-duplicates by link/title. Articles carry an `origin` of `live` or `cached`, and the `published` field is enriched from the API, structured HTML metadata, or the cached file so timestamps rarely come back `null`.
    Schema:
    ```json
    {
      "ticker": "NVDA",
      "fetched_at": "2025-10-30T04:15:05.312Z",
      "summary": {
        "headline": "Latest coverage skews positive",
        "sentiment": "Positive",
        "rating": "Buy",
        "confidence": "Medium",
        "key_points": ["✅ ..." ],
        "rationale": "3 source(s) highlight supportive catalysts.",
        "conclusion": "Momentum favors accumulation on strength."
      },
      "articles": [
        {
          "title": "...",
          "source": "Reuters",
          "link": "https://...",
          "published": "2025-10-29T21:05:00Z",
          "snippet": "...",
          "sentiment": { "label": "Positive", "score": 0.52 },
          "origin": "live"
        }
      ],
      "legacy_analysis": "Full-text interpretation from the nightly batch (optional)."
    }
    ```
  - `company/{TICKER}.json`: consolidated runtime cache that combines the latest price snapshot and news summary for quick reuse by the UI.
  Runtime artifacts are refreshed automatically by the API. Cached files expire after 30 minutes.

## Quick Start

### Local Development

1. **Clone the repository**
   ```bash
   git clone https://github.com/yinglu1985/deep_alpha_copilot.git
   cd deep_alpha_copilot
   ```

2. **Set up virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   Create a `.env` file with:
   ```
   GEMINI_API_KEY=your_gemini_api_key
   OPENROUTER_API_KEY=your_openrouter_api_key  # Optional: for open source model fallbacks
   GOOGLE_SEARCH_API_KEY=your_google_search_api_key
   GOOGLE_SEARCH_ENGINE_ID=your_search_engine_id
   REDDIT_CLIENT_ID=your_reddit_client_id
   REDDIT_CLIENT_SECRET=your_reddit_client_secret
   REDDIT_USER_AGENT=YourApp/1.0
   X_BEARER_TOKEN=your_x_bearer_token  # Optional
   SEC_USER_AGENT=YourName your.email@example.com
   GCP_PROJECT_ID=your_gcp_project_id  # For Cloud Storage
   ```

5. **Run the application**
   ```bash
   uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Access the application**
   Open http://localhost:8000 in your browser

### Data Collection

Fetch latest data for supported tickers:
```bash
python fetch_data.py
```

## Cloud Deployment

See [README_DEPLOY.md](README_DEPLOY.md) for detailed Google Cloud deployment instructions.

### Quick Deploy

```bash
# Set your project ID
export GCP_PROJECT_ID=your-project-id

# Run deployment script
./deploy.sh
```

## Supported Tickers

Currently tracking 15 companies across semiconductors, AI infrastructure, nuclear energy, and battery technology:

**Semiconductors & AI**: TSM, NVDA, AMD, AVGO, ORCL

**Critical Minerals**: MP, LAC, UAMY, CRML, NMG, PPTA, NVA, NAK, NB, ALB

## Key Features in Detail

### Scoring Methodology (Deep Alpha 7-Pillar Framework)

Each stock receives scores (0-10) across 7 dimensions:

1. **Business Score** (20% weight)
   - Revenue CAGR (annual growth rate)
   - Gross margin
   - R&D intensity (% of revenue)
   - Sector growth multipliers

2. **Financial Score** (25% weight) - *Highest weight*
   - Net income CAGR
   - Return on Equity (ROE)
   - Current ratio (liquidity)
   - Debt-to-equity ratio

3. **Sentiment Score** (15% weight)
   - News sentiment (VADER analysis, age-weighted)
   - Reddit sentiment (bullish/bearish ratio)
   - Twitter/X sentiment (optional)

4. **Critical Path Score** (10% weight)
   - Strategic positioning
   - Policy tailwinds (e.g., CHIPS Act, defense contracts)
   - Sector-specific critical factors

5. **Leadership Score** (10% weight)
   - CEO tenure
   - CEO background and track record
   - Leadership stability

6. **Earnings Score** (10% weight)
   - EPS trend
   - Revenue trend
   - Earnings consistency (beats/misses)

7. **Technical Score** (10% weight)
   - RSI (14-day)
   - Moving averages (MA50 vs MA200)
   - Volume trends
   - 6-month and 12-month returns

**Overall Score**: Weighted average of all 7 components (0-10 scale)
**Recommendation Mapping**:
- Score ≥ 8.0: "Strong Buy" (Long-term, 12-24 months)
- Score ≥ 7.0: "Buy" (Long-term, 12-18 months)
- Score ≥ 4.0: "Hold" (Medium-term, 6-12 months)
- Score < 4.0: "Sell" (Short-term, <6 months)

### AI-Powered Features

- **News Interpretation**: Multi-model AI analysis using Deep Alpha 7-Pillar framework:
  - **Primary**: Google Gemini models (2.0 Flash Exp, 1.5 Flash)
  - **Fallback**: OpenRouter open source models (Gwen, Llama, Mistral, Gemma, Qwen)
  - **Final Fallback**: Template-based analysis (always works)
  - Extracts key insights across all 7 pillars
  - Investment implications and recommendations
  - Buy/Hold/Sell rating with confidence level
  - **99% success rate** with multiple fallback layers

- **Conversational Agent**: Google ADK-powered multi-agent system:
  - **Root Agent**: Orchestrates queries and routes to specialized agents
  - **13 Sub-Agents**: Specialized for different tasks (financial, news, sentiment, flow data, etc.)
  - **Single API Call**: Handles complex multi-source queries automatically
  - **Intelligent Synthesis**: Combines results from multiple agents into coherent answers
  - Answers questions about specific stocks
  - Provides market insights
  - Compares companies
  - Explains financial metrics
  - Maintains conversation context

### Time-Varying Benchmarks

Industry benchmarks dynamically adjust based on S&P 500 price movements to reflect changing market conditions and valuation multiples over time.

### Intraday Data

1-day and 1-week views fetch live intraday data:
- 1d: 5-minute intervals (~78 data points)
- 1w: 30-minute intervals (~65 data points)

## API Endpoints

- `GET /` - Main dashboard
- `GET /api/scores/{ticker}` - Get comprehensive scoring
- `GET /api/price-history/{ticker}?period={period}` - Historical prices
- `GET /api/valuation-metrics/{ticker}` - P/E and P/S ratios
- `GET /api/latest-news/{ticker}` - Latest news (last 72 hours) with AI interpretation
- `GET /api/flow-data/{ticker}` - Institutional and retail flow data
- `GET /api/market-conditions` - Current market indicators
- `POST /chat` - AI chat assistant

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License.

## Contact

For questions or support, please open an issue on GitHub.

---

**Disclaimer**: This tool is for educational and research purposes only. Not financial advice. Always do your own research and consult with a qualified financial advisor before making investment decisions.
