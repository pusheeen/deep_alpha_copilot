# Deep Alpha Copilot

An AI-powered financial analysis platform that provides comprehensive stock scoring and investment insights using multiple data sources including financial statements, news, social sentiment, and technical indicators.

## Features

- **Comprehensive Stock Scoring**: Multi-dimensional analysis across 6 key areas:
  - Financial Health
  - Business Model & Competitive Position
  - Leadership & Management
  - Technical Analysis
  - Sentiment Analysis (News, Reddit, Twitter/X)
  - Risk Assessment

- **Real-Time Market Data**:
  - Intraday price data with 5-minute intervals for 1-day view
  - Historical price data with customizable time periods
  - Live market condition indicators (VIX, Fear & Greed Index, Put/Call Ratio)

- **AI-Powered News Analysis**:
  - Automated news fetching and filtering using Google Gemini 2.5 Flash
  - Intelligent news interpretation with actionable insights
  - News sentiment analysis integrated into overall scoring

- **Interactive Visualizations**:
  - Real-time price charts with event markers
  - Historical valuation metrics (P/E, P/S ratios) with industry benchmarks
  - Time-varying industry benchmarks based on S&P 500 movements
  - Multi-stock comparison charts

- **AI Chat Assistant**:
  - Google ADK-powered conversational agent
  - Context-aware responses using company data and latest news
  - Natural language queries about stocks, market trends, and investment strategies

## Technology Stack

### Backend
- **FastAPI**: Modern Python web framework
- **Google Cloud Run**: Serverless deployment platform
- **BigQuery**: Data warehouse for structured financial data
- **Google Gemini 2.5 Flash**: LLM for news analysis and chat
- **Google ADK**: Agentic framework for intelligent chat assistant

### Data Sources
- **yfinance**: Stock prices and financial data
- **SEC EDGAR**: Official financial filings
- **Reddit API (PRAW)**: Social sentiment from Reddit
- **Twitter/X API**: Official company communications
- **News APIs**: Latest financial news

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
  - `news/{TICKER}_realtime_news.json`: live news cache used by the UI. Schema:
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
          "sentiment": { "label": "Positive", "score": 0.52 }
        }
      ],
      "legacy_analysis": "Full-text interpretation from the nightly batch (optional)."
    }
    ```
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
   REDDIT_CLIENT_ID=your_reddit_client_id
   REDDIT_CLIENT_SECRET=your_reddit_client_secret
   REDDIT_USER_AGENT=YourApp/1.0
   X_BEARER_TOKEN=your_x_bearer_token
   SEC_USER_AGENT=YourName your.email@example.com
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

**Semiconductors & AI**: NVDA, AMD, AVGO, TSM, ORCL

**Critical Minerals**: ALB, LAC, MP, UAMY, CRML, NMG, PPTA, NVA, NAK, NB

## Key Features in Detail

### Scoring Methodology

Each stock receives scores (0-10) across 6 dimensions:

1. **Financial Score** (30% weight)
   - Revenue growth
   - Profit margins
   - Cash flow strength
   - Debt levels

2. **Business Score** (20% weight)
   - Market position
   - Competitive advantages
   - Growth potential
   - Industry trends

3. **Leadership Score** (15% weight)
   - CEO track record
   - Management compensation alignment
   - Strategic vision

4. **Technical Score** (15% weight)
   - Price momentum
   - Volume patterns
   - Support/resistance levels
   - Moving averages

5. **Sentiment Score** (10% weight)
   - News sentiment
   - Social media sentiment
   - Analyst ratings

6. **Risk Score** (10% weight)
   - Volatility
   - Market cap
   - Liquidity
   - Regulatory risks

### AI-Powered Features

- **News Interpretation**: Gemini 2.5 Flash analyzes news articles to extract:
  - Key insights
  - Investment implications
  - Recommendation (Buy/Hold/Sell)
  - Confidence level

- **Conversational Agent**: Google ADK-powered assistant that:
  - Answers questions about specific stocks
  - Provides market insights
  - Compares companies
  - Explains financial metrics

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
- `GET /api/latest-news/{ticker}` - Latest news with AI interpretation
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
