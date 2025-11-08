# main.py

"""
Main FastAPI application file, adapted to use the Google ADK agent system.
"""
import asyncio
import json
import re
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from starlette.responses import FileResponse
from pydantic import BaseModel
from pathlib import Path

# --- ADK Imports (Optional) ---
from typing import Optional, Dict, Any
try:
    from google.adk.agents import Agent
    from google.adk.runners import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    print("Warning: Google ADK not available. Agent features will be disabled.")

# Add this import
from fastapi.middleware.cors import CORSMiddleware 
import os
try:
    import stripe
except ImportError:
    stripe = None
import databases
import sqlalchemy
from passlib.context import CryptContext
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi import Form, Depends, HTTPException

app = FastAPI()

# CORS configuration - environment aware
# In production, set ALLOWED_ORIGINS env var to your domain
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:8000,http://localhost:3000").split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)
# --- Import your new ADK root agent and utilities ---
from dotenv import load_dotenv  # <-- ADD THIS
if ADK_AVAILABLE:
    try:
        from app.agents.agents import root_agent
    except ImportError:
        ADK_AVAILABLE = False
        print("Warning: Could not import agents. Agent features will be disabled.")

# Import news functions directly from fetch_data module
try:
    from fetch_data.news import fetch_news_for_ticker, interpret_news_with_gemini
    from fetch_data.sector_news import fetch_sector_news
    NEWS_AVAILABLE = True
except ImportError as e:
    fetch_news_for_ticker = None
    interpret_news_with_gemini = None
    fetch_sector_news = None
    NEWS_AVAILABLE = False
    print(f"Warning: Could not import news functions: {e}")

# Directories for cached data
from fetch_data.utils import DATA_ROOT, NEWS_DATA_DIR, NEWS_INTERPRETATION_DIR
import os

# Cached valuation metrics directory
VALUATION_METRICS_DIR = os.path.join(DATA_ROOT, "unstructured", "valuation_metrics")
os.makedirs(VALUATION_METRICS_DIR, exist_ok=True)

from app.scoring import compute_company_scores, ScoreComputationError
load_dotenv()
import math

# Utility function to sanitize data for JSON serialization
def sanitize_for_json(obj):
    """Recursively replace NaN and infinity values with None for JSON compliance."""
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    return obj

# --- Configuration ---
APP_DIR = Path(__file__).resolve().parent
# Stripe configuration (optional)
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
PRICE_ID = os.getenv("STRIPE_PRICE_ID")
if stripe:
    stripe.api_key = STRIPE_SECRET_KEY or None
# Flag whether Stripe is configured
HAS_STRIPE = bool(stripe and STRIPE_SECRET_KEY and PRICE_ID)

# Database setup
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./users.db")
database = databases.Database(DATABASE_URL)
metadata = sqlalchemy.MetaData()

users = sqlalchemy.Table(
    "users",
    metadata,
    sqlalchemy.Column("id", sqlalchemy.Integer, primary_key=True),
    sqlalchemy.Column("username", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("email", sqlalchemy.String, unique=True, index=True),
    sqlalchemy.Column("hashed_password", sqlalchemy.String),
    sqlalchemy.Column("stripe_customer_id", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("stripe_subscription_id", sqlalchemy.String, nullable=True),
    sqlalchemy.Column("subscription_status", sqlalchemy.String, nullable=True),
)

engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
)
metadata.create_all(engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

@app.on_event("startup")
async def startup():
    await database.connect()

@app.on_event("shutdown")
async def shutdown():
    await database.disconnect()

def get_password_hash(password: str):
    return pwd_context.hash(password)

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

async def get_user_by_email(email: str):
    query = users.select().where(users.c.email == email)
    return await database.fetch_one(query)

async def get_user_by_id(user_id: int):
    query = users.select().where(users.c.id == user_id)
    return await database.fetch_one(query)

async def authenticate_user(email: str, password: str):
    user = await get_user_by_email(email)
    if not user or not verify_password(password, user["hashed_password"]):
        return None
    return user

async def get_current_user(request: Request):
    user_id = request.session.get("user")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await get_user_by_id(user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user

# --- ADK Agent Runner Setup ---
if ADK_AVAILABLE:
    class AgentCaller:
        """A simple wrapper class for interacting with an ADK agent."""
        def __init__(self, agent: Agent, runner: Runner, user_id: str, session_id: str):
            self.agent = agent
            self.runner = runner
            self.user_id = user_id
            self.session_id = session_id

        async def call(self, user_message: str, include_reasoning: bool = False) -> dict:
            content = types.Content(role='user', parts=[types.Part(text=user_message)])

            final_response = {
                'answer': "Agent did not produce a final response.",
                'status': 'error'
            }

            reasoning_steps = []
            tools_used = set()

            async for event in self.runner.run_async(user_id=self.user_id, session_id=self.session_id, new_message=content):
                if include_reasoning and event.author != self.agent.name and not event.is_final_response():
                     # Capture tool calls and observations as reasoning steps
                     if event.content and event.content.parts and hasattr(event.content.parts[0], 'tool_code'):
                         tool_call = event.content.parts[0].tool_code
                         reasoning_steps.append({
                             'tool': tool_call.name,
                             'input': str(tool_call.args),
                             'output': "Pending..."
                         })
                         tools_used.add(tool_call.name)
                     elif event.content and event.content.parts and hasattr(event.content.parts[0], 'tool_result'):
                         if reasoning_steps:
                            reasoning_steps[-1]['output'] = str(event.content.parts[0].tool_result.result)

                if event.is_final_response() and event.content and event.content.parts:
                    final_response['answer'] = event.content.parts[0].text
                    final_response['status'] = 'success'
                    break

            if include_reasoning:
                final_response['reasoning_steps'] = reasoning_steps
                final_response['tools_used'] = list(tools_used)

            return final_response

    async def make_agent_caller(agent: Agent) -> AgentCaller:
        """Factory function to create an AgentCaller instance."""
        app_name = agent.name + "_app"
        user_id = agent.name + "_user"
        session_id = agent.name + "_session_01"

        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        runner = Runner(agent=agent, app_name=app_name, session_service=session_service)
        return AgentCaller(agent, runner, user_id, session_id)


# --- FastAPI Application ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    # On startup, initialize the ADK AgentCaller (if available)
    if ADK_AVAILABLE:
        print("Initializing ADK Agent...")
        app.state.agent_caller = await make_agent_caller(root_agent)
        print("Agent is ready.")
    else:
        print("ADK not available. Agent features disabled.")
        app.state.agent_caller = None
    yield
    # On shutdown (not essential for this example, but good practice)
    print("Shutting down.")


app = FastAPI(
    title="Clinical Assistant API (ADK Version)",
    description="An API for interacting with the Clinical AI Assistant, powered by Google ADK.",
    version="2.0.0",
    lifespan=lifespan
)

# Add session middleware and template rendering
app.add_middleware(SessionMiddleware, secret_key=os.getenv("SESSION_SECRET_KEY", "changeme"))
templates = Jinja2Templates(directory=str(APP_DIR / "templates"))

class QueryRequest(BaseModel):
    """Defines the structure of the request body for the /chat endpoint."""
    question: str
    include_reasoning: bool = False

import os
import json
from fastapi import HTTPException

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serves the main index.html file."""
    user = None
    user_id = request.session.get("user")
    if user_id:
        user = await get_user_by_id(user_id)
    return templates.TemplateResponse("index.html", {"request": request, "user": user, "hide_sector_news": True})

@app.get("/api/scores/{ticker}")
async def get_scores(ticker: str, news_only: bool = False, query: Optional[str] = None):
    """Return the latest computed scorecard for a company or fetch news snippets for a query."""
    loop = asyncio.get_event_loop()
    if news_only:
        try:
            # Determine ticker for lookup
            search_query = query or ticker
            safe_ticker = search_query.upper()
            # Attempt to load cached news JSON (try timestamped files first)
            news_file = find_latest_timestamped_file(NEWS_DATA_DIR, f"{safe_ticker}_news")
            if news_file and os.path.exists(news_file):
                with open(news_file, "r") as f:
                    news_json = json.load(f)
                results = news_json.get("articles", [])
            elif NEWS_AVAILABLE and fetch_news_for_ticker:
                # Fetch and cache news via fetch_data.news
                results = await loop.run_in_executor(None, fetch_news_for_ticker, safe_ticker, safe_ticker)
                if results is None:
                    results = []
            else:
                results = []
            return {"status": "success", "data": {"latest_news": results}}
        except Exception as exc:  # pragma: no cover - network failures
            return {"status": "error", "message": f"Failed to fetch news: {exc}"}
    try:
        data = await loop.run_in_executor(None, compute_company_scores, ticker.upper())
        # Sanitize data to handle NaN/infinity values
        data = sanitize_for_json(data)
        return {"status": "success", "data": data}
    except ScoreComputationError as exc:
        return {"status": "error", "message": str(exc)}
    except Exception as exc:  # pragma: no cover - unexpected errors bubbled to client
        return {"status": "error", "message": f"Unexpected error: {exc}"}

@app.get("/api/news-interpretation/{ticker}")
async def get_news_interpretation(ticker: str):
    """Return precomputed AI analysis for news interpretation from cache."""
    safe_ticker = ticker.upper()
    # Try to find latest timestamped file first
    interp_file = find_latest_timestamped_file(NEWS_INTERPRETATION_DIR, f"{safe_ticker}_news_interpretation")
    if interp_file and os.path.exists(interp_file):
        with open(interp_file, "r") as f:
            data = json.load(f)
        return {"status": "success", "data": data}
    else:
        return {"status": "error", "message": f"No precomputed news interpretation for {ticker}. Please run the news interpretation job."}

@app.get("/api/price-history/{ticker}")
async def get_price_history(ticker: str, period: str = "1m"):
    """Return price history with events for a specific time period."""
    from app.scoring.engine import get_price_history_with_events

    try:
        # For now, we'll use empty news items since we're focusing on significant moves
        news_items = []
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, get_price_history_with_events, ticker.upper(), news_items, period)
        data = sanitize_for_json(data)
        return {"status": "success", "data": data}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch price history: {exc}"}

@app.get("/api/valuation-metrics/{ticker}")
async def get_valuation_metrics(ticker: str):
    """Return historical P/E and P/S ratios with industry benchmarks (cached or live)."""
    from app.scoring.engine import get_valuation_metrics as compute_metrics

    safe_ticker = ticker.upper()
    # Attempt to load cached valuation metrics JSON if available
    metrics_file = os.path.join(VALUATION_METRICS_DIR, f"{safe_ticker}_valuation_metrics.json")
    try:
        if os.path.exists(metrics_file):
            with open(metrics_file, "r") as f:
                data = json.load(f)
        else:
            # Compute metrics and cache to file
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, compute_metrics, safe_ticker)
            data = sanitize_for_json(data)
            with open(metrics_file, "w") as f:
                json.dump(data, f)
        return {"status": "success", "data": data}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch valuation metrics: {exc}"}

@app.get("/api/market-conditions")
async def get_market_conditions():
    """Return current market condition indicators."""
    from app.scoring.engine import get_market_conditions

    try:
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(None, get_market_conditions)
        return {"status": "success", "data": data}
    except Exception as exc:
        return {"status": "error", "message": f"Failed to fetch market conditions: {exc}"}

@app.get("/api/sector-news/{sector}")
async def get_sector_news_endpoint(sector: str):
    """Return the latest news for a sector from cached JSON files."""
    print(f"--- Getting sector news for {sector} ---")

    try:
        # Sanitize sector name for filename (same as in fetch script)
        import re
        safe_sector_name = re.sub(r'[^a-zA-Z0-9_]', '_', sector)
        sector_news_dir = "data/unstructured/sector_news"

        # Find latest timestamped file
        sector_file = find_latest_timestamped_file(sector_news_dir, f"{safe_sector_name}_news")

        # Check if sector file exists
        if not sector_file or not os.path.exists(sector_file):
            return {
                "status": "error",
                "message": f"No cached news found for {sector} sector. Please run news update script."
            }

        # Load sector news
        with open(sector_file, 'r') as f:
            sector_data = json.load(f)

        articles = sector_data.get('articles', [])

        if not articles:
            return {"status": "error", "message": "No articles found for this sector"}

        # Normalize article structure to match frontend expectations
        normalized_articles = []
        for article in articles:
            normalized_articles.append({
                'title': article.get('title'),
                'link': article.get('link'),
                'snippet': article.get('summary', article.get('snippet', '')),
                'source': article.get('publisher', article.get('source', 'Unknown')),
                'published': article.get('publish_time', article.get('published', ''))
            })

        # Convert to expected format with results
        news_data = {
            "answer": json.dumps({"results": normalized_articles}),
            "status": "success"
        }
        return {"status": "success", "data": news_data}
    except Exception as exc:
        print(f"Error loading cached sector news: {exc}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to load cached sector news: {exc}"}

@app.get("/api/token-usage")
async def get_token_usage():
    """Return AI token consumption data by model from the latest token usage file."""
    try:
        # Try to find actual token usage file first
        token_usage_dir = "data/unstructured/token_usage"
        token_file = find_latest_timestamped_file(token_usage_dir, "token_usage")
        
        # Fallback to rankings file if usage file doesn't exist
        if not token_file:
            token_file = find_latest_timestamped_file(token_usage_dir, "openrouter_rankings")
        
        if not token_file:
            return {
                "status": "error",
                "message": "No token usage data found. Please run fetch_data/fetch_token_usage.py to generate data."
            }
        
        # Load token usage data
        with open(token_file, 'r') as f:
            token_data = json.load(f)
        
        # Check if we have actual measured data (newest format - from rankings chart)
        if 'data_type' in token_data and token_data['data_type'] == 'actual_measured_data':
            # ACTUAL measurements from OpenRouter rankings chart
            response_data = {
                "fetch_timestamp": token_data.get('fetch_timestamp'),
                "data_type": "actual_measured_data",
                "platform": token_data.get('platform', 'OpenRouter'),
                "current_stats": token_data.get('current_stats', {}),
                "data_points": token_data.get('data_points', []),
                "source": token_data.get('source', 'OpenRouter rankings chart'),
                "note": token_data.get('note', 'Actual measurements only')
            }

            return {
                "status": "success",
                "data": response_data
            }
        # Check if we have actual published statistics (new format)
        elif 'data_type' in token_data and token_data['data_type'] == 'actual_published_statistics':
            # ACTUAL OpenRouter platform statistics
            response_data = {
                "fetch_timestamp": token_data.get('fetch_timestamp'),
                "data_type": "actual_published_statistics",
                "platform": token_data.get('platform', 'OpenRouter'),
                "current_usage": token_data.get('current_usage', {}),
                "growth_metrics": token_data.get('growth_metrics', {}),
                "daily_usage": token_data.get('data_points', []),  # Use data_points as daily_usage for frontend
                "sources": token_data.get('sources', []),
                "note": token_data.get('note', 'Actual published statistics')
            }

            return {
                "status": "success",
                "data": response_data
            }
        # Check if we have daily usage data (old synthesized format)
        elif 'daily_usage' in token_data:
            # Old format: synthesized daily totals
            response_data = {
                "fetch_timestamp": token_data.get('fetch_timestamp'),
                "days": token_data.get('days', 90),
                "total_tokens": token_data.get('total_tokens', 0),
                "total_requests": token_data.get('total_requests', 0),
                "total_cost": token_data.get('total_cost', 0),
                "daily_usage": token_data['daily_usage'],
                "source": token_data.get('source', 'estimated')
            }

            return {
                "status": "success",
                "data": response_data
            }
        # Check if we have aggregated_by_model (old format with model-specific data)
        elif 'aggregated_by_model' in token_data:
            # Use actual aggregated usage data
            model_consumption = token_data['aggregated_by_model'][:15]
            # Format for frontend
            formatted_consumption = []
            for model in model_consumption:
                formatted_consumption.append({
                    "model_id": model.get('model_id', ''),
                    "model_name": model.get('model_name', model.get('model_id', '')),
                    "tokens": model.get('total_tokens', 0),
                    "prompt_price": model.get('prompt_price', 0),
                    "completion_price": model.get('completion_price', 0),
                    "requests": model.get('total_requests', 0),
                    "cost": model.get('total_cost', 0)
                })
            
            response_data = {
                "fetch_timestamp": token_data.get('fetch_timestamp'),
                "days": token_data.get('days', 90),
                "total_models": len(token_data.get('aggregated_by_model', [])),
                "total_tokens": token_data.get('total_tokens', 0),
                "total_requests": token_data.get('total_requests', 0),
                "model_consumption": formatted_consumption,
                "source": token_data.get('source', 'estimated')
            }
            
            # Include daily usage if available
            if 'daily_usage' in token_data:
                response_data['daily_usage'] = token_data['daily_usage']
            
            return {
                "status": "success",
                "data": response_data
            }
        else:
            # Fallback: use rankings data to estimate
            rankings = token_data.get('rankings', [])
            
            model_consumption = []
            for model in rankings[:20]:  # Top 20 models
                model_id = model.get('id', '')
                model_name = model.get('name', model_id)
                pricing = model.get('pricing', {})
                
                prompt_price = float(pricing.get('prompt', 0))
                completion_price = float(pricing.get('completion', 0))
                
                # Estimate tokens: inverse relationship with price
                base_tokens = 1000000
                if prompt_price > 0:
                    estimated_tokens = int(base_tokens / (prompt_price * 1000000 + 1))
                else:
                    estimated_tokens = base_tokens
                
                model_consumption.append({
                    "model_id": model_id,
                    "model_name": model_name,
                    "tokens": estimated_tokens,
                    "prompt_price": prompt_price,
                    "completion_price": completion_price
                })
            
            model_consumption.sort(key=lambda x: x['tokens'], reverse=True)
            
            return {
                "status": "success",
                "data": {
                    "fetch_timestamp": token_data.get('fetch_timestamp'),
                    "days": token_data.get('days', 90),
                    "total_models": token_data.get('total_models', len(rankings)),
                    "model_consumption": model_consumption[:15],
                    "source": "estimated"
                }
            }
    except Exception as exc:
        print(f"Error loading token usage: {exc}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to load token usage: {exc}"}

@app.get("/api/token-usage-plot")
async def get_token_usage_plot():
    """Serve the latest token usage plot image."""
    try:
        token_usage_dir = "data/unstructured/token_usage"
        plot_file = find_latest_timestamped_file(token_usage_dir, "token_usage_plot", extension=".png")

        if not plot_file:
            # Return a placeholder or error
            return {"status": "error", "message": "No token usage plot found. Please run fetch_data/token_usage.py to generate the plot."}

        return FileResponse(plot_file, media_type="image/png")
    except Exception as exc:
        print(f"Error loading token usage plot: {exc}")
        return {"status": "error", "message": f"Failed to load token usage plot: {exc}"}

@app.get("/api/flow-plot/{ticker}")
async def get_flow_plot(ticker: str):
    """Serve the latest flow plot image for a given ticker."""
    try:
        flow_dir = "data/structured/flow_data"
        plot_file = find_latest_timestamped_file(flow_dir, f"{ticker}_flow_plot", extension=".png")

        if not plot_file:
            return {"status": "error", "message": f"No flow plot found for {ticker}. Please run fetch_data.py to generate the plot."}

        return FileResponse(plot_file, media_type="image/png")
    except Exception as exc:
        print(f"Error loading flow plot for {ticker}: {exc}")
        return {"status": "error", "message": f"Failed to load flow plot: {exc}"}

def find_latest_timestamped_file(directory: str, prefix: str, extension: str = ".json") -> Optional[str]:
    """Find the latest timestamped file matching the prefix pattern.

    Supports two timestamp formats:
    - {prefix}_YYYYMMDD_HHMMSS.{extension} (news files, plots)
    - {prefix}_YYYYMMDD.{extension} (flow data files)
    Returns the file with the latest timestamp.
    """
    import glob
    from datetime import datetime

    # Pattern to match only timestamped files
    pattern = os.path.join(directory, f"{prefix}_*{extension}")
    matching_files = glob.glob(pattern)

    if not matching_files:
        return None

    # Extract timestamp from filename and find the latest
    latest_file = None
    latest_timestamp = None

    for file_path in matching_files:
        filename = os.path.basename(file_path)
        # Remove prefix and extension to get timestamp
        if filename.startswith(prefix + "_") and filename.endswith(extension):
            timestamp_str = filename[len(prefix) + 1:-len(extension)]  # Remove prefix_ and extension

            # Try both timestamp formats
            timestamp = None

            # Try YYYYMMDD_HHMMSS format first
            try:
                timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            except ValueError:
                # Try YYYYMMDD format (for flow data files)
                try:
                    timestamp = datetime.strptime(timestamp_str, "%Y%m%d")
                except ValueError:
                    # Skip files that don't match either format
                    continue

            if timestamp and (latest_timestamp is None or timestamp > latest_timestamp):
                latest_timestamp = timestamp
                latest_file = file_path

    return latest_file

@app.get("/api/flow-data/{ticker}")
async def get_flow_data_endpoint(ticker: str, flow_type: str = "combined"):
    """Return the latest flow data (institutional and retail) for a ticker.

    Args:
        ticker: Stock ticker symbol
        flow_type: Type of flow data ('institutional', 'retail', 'combined', 'changes')
    """
    print(f"--- Getting flow data for {ticker} (type: {flow_type}) ---")

    try:
        ticker = ticker.upper().strip()

        # Find the latest flow data file
        flow_dir = "data/structured/flow_data"

        # Determine file pattern based on flow_type
        if flow_type == "institutional":
            pattern_prefix = f"{ticker}_institutional_flow"
        elif flow_type == "retail":
            pattern_prefix = f"{ticker}_retail_flow"
        else:  # combined or changes
            pattern_prefix = f"{ticker}_combined_flow"

        flow_file = find_latest_timestamped_file(flow_dir, pattern_prefix)

        if not flow_file:
            return {
                "status": "error",
                "message": f"No flow data found for {ticker}. Please run the data fetching script to generate flow data."
            }

        print(f"Loading flow data from: {flow_file}")

        # Load flow data
        with open(flow_file, 'r') as f:
            flow_data = json.load(f)

        # If requesting changes only, extract just the changes section
        if flow_type == "changes":
            if "institutional_changes" in flow_data:
                response_data = {
                    "ticker": ticker,
                    "flow_type": flow_type,
                    "data": flow_data["institutional_changes"],
                    "file_date": os.path.basename(flow_file).split('_')[-1].replace('.json', '')
                }
            else:
                return {
                    "status": "error",
                    "message": "Institutional changes data not available in this file"
                }
        else:
            response_data = {
                "ticker": ticker,
                "flow_type": flow_type,
                "data": flow_data,
                "file_date": os.path.basename(flow_file).split('_')[-1].replace('.json', '')
            }

        return {"status": "success", "data": response_data}

    except Exception as exc:
        print(f"Error loading flow data: {exc}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to load flow data: {exc}"}

@app.get("/api/latest-news/{ticker}")
async def get_latest_news_endpoint(ticker: str):
    """Return the latest news for a ticker from the most recent timestamped JSON file.

    Only uses files with timestamp format: {ticker}_news_YYYYMMDD_HHMMSS.json
    Automatically selects the file with the latest timestamp.
    """
    print(f"--- Getting latest news for {ticker} ---")

    try:
        ticker = ticker.upper().strip()

        # Find the latest timestamped news file
        news_dir = "data/unstructured/news"
        news_file = find_latest_timestamped_file(news_dir, f"{ticker}_news")
        
        if not news_file:
            return {
                "status": "error",
                "message": f"No timestamped news files found for {ticker}. Please run news update script to generate timestamped files."
            }

        print(f"Loading news from: {news_file}")

        # Load news articles
        with open(news_file, 'r') as f:
            news_data_raw = json.load(f)

        articles = news_data_raw.get('articles', [])
        company_name = news_data_raw.get('company_name', ticker)

        if not articles:
            return {
                "status": "error",
                "message": "No recent news found for this ticker."
            }

        # Convert to frontend format
        results = []
        for article in articles:
            results.append({
                "title": article.get('title', 'No title'),
                "link": article.get('link', ''),
                "snippet": article.get('summary', ''),
                "published": article.get('publish_time'),
                "source": article.get('publisher', 'Unknown'),
                "type": article.get('type', 'article')
            })

        # Load precomputed AI interpretation from cache
        safe_ticker = ticker.upper()
        # Look for static precomputed file first, then timestamped variants
        static_file = os.path.join(NEWS_INTERPRETATION_DIR, f"{safe_ticker}_news_interpretation.json")
        if os.path.exists(static_file):
            interp_file = static_file
        else:
            interp_file = find_latest_timestamped_file(NEWS_INTERPRETATION_DIR, f"{safe_ticker}_news_interpretation")
        if interp_file and os.path.exists(interp_file):
            with open(interp_file, 'r') as f:
                interpretation_result = json.load(f)
            # Map to frontend structure
            rec = interpretation_result.get('recommendation', '').upper()
            sentiment = 'neutral'
            sentiment_score = 50
            if rec == 'BUY':
                sentiment = 'bullish'
                sentiment_score = 75
            elif rec == 'SELL':
                sentiment = 'bearish'
                sentiment_score = 25
            interpretation = {
                'ticker': ticker,
                'sentiment': sentiment,
                'sentiment_score': sentiment_score,
                'summary': interpretation_result.get('interpretation', ''),
                'recommendation': rec or 'N/A',
                'reasoning': interpretation_result.get('reasoning', ''),
                'investment_impact': interpretation_result.get('reasoning', ''),
                'short_term_outlook': interpretation_result.get('reasoning', ''),
            }
        else:
            interpretation = {
                'ticker': ticker,
                'sentiment': 'neutral',
                'sentiment_score': 50,
                'summary': 'No precomputed AI analysis available.',
                'recommendation': 'N/A',
                'reasoning': '',
                'investment_impact': '',
                'short_term_outlook': '',
            }

        data = {
            "query": ticker,
            "company_name": company_name,
            "results": results,
            "interpretation": interpretation,
            "total_articles": len(results)
        }

        # Format as expected by frontend (wrap in answer field as JSON string)
        news_data = {
            "answer": json.dumps(data),
            "status": "success"
        }
        return {"status": "success", "data": news_data}
    except Exception as exc:
        print(f"Error loading cached news: {exc}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "message": f"Failed to load cached news: {exc}"}


@app.post("/chat")
async def chat(request: QueryRequest, http_request: Request):
    """
    Receives a question, processes it through the ADK agent, and returns the response.
    """
    # Basic validation
    if not request.question or len(request.question.strip()) < 5:
        return {
            'answer': "Invalid query: Question seems too short to be meaningful",
            'status': 'validation_error'
        }

    # Access the agent_caller initialized at startup
    agent_caller = http_request.app.state.agent_caller

    if not agent_caller:
        return {
            'answer': "Agent features are not available. Please contact support.",
            'status': 'agent_unavailable'
        }

    # Process the query using the ADK agent
    response = await agent_caller.call(
        user_message=request.question,
        include_reasoning=request.include_reasoning
    )
    return response
  
# User authentication and subscription routes

# Register
@app.get("/register", response_class=HTMLResponse)
async def register_get(request: Request):
    # Simple registration form
    html_content = """
<html><body>
<h2>Register</h2>
<form method='post'>
  Username: <input name='username'/><br/>
  Email: <input type='email' name='email'/><br/>
  Password: <input type='password' name='password'/><br/>
  <button type='submit'>Register</button>
</form>
</body></html>
"""
    return HTMLResponse(html_content)

@app.post("/register")
async def register_post(request: Request, username: str = Form(...), email: str = Form(...), password: str = Form(...)):
    existing_user = await get_user_by_email(email)
    if existing_user:
        return HTMLResponse("Email already registered", status_code=400)
    hashed_password = get_password_hash(password)
    await database.execute(users.insert().values(username=username, email=email, hashed_password=hashed_password))
    return RedirectResponse(url="/login", status_code=302)

# Login
@app.get("/login", response_class=HTMLResponse)
async def login_get(request: Request):
    # Simple login form
    html_content = """
<html><body>
<h2>Login</h2>
<form method='post'>
  Email: <input type='email' name='email'/><br/>
  Password: <input type='password' name='password'/><br/>
  <button type='submit'>Login</button>
</form>
</body></html>
"""
    return HTMLResponse(html_content)

@app.post("/login")
async def login_post(request: Request, email: str = Form(...), password: str = Form(...)):
    user = await authenticate_user(email, password)
    if not user:
        return HTMLResponse("Invalid credentials", status_code=401)
    request.session["user"] = user["id"]
    return RedirectResponse(url="/account", status_code=302)

# Logout
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/", status_code=302)

# Account page
@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request, current_user=Depends(get_current_user)):
    # Display account and subscription status
    subscribed = current_user.get("subscription_status") == "active"
    html = "<html><body>"
    html += f"<h2>Account for {current_user.get('username')}</h2>"
    html += f"<p>Email: {current_user.get('email')}</p>"
    html += "<h3>Subscription</h3>"
    if subscribed:
        html += "<p>Subscribed: $10/month (Active)</p>"
    else:
        if HAS_STRIPE:
            html += "<p>Monthly subscription: $10</p>"
            html += "<form method='post' action='/create-checkout-session'><button type='submit'>Subscribe</button></form>"
        else:
            html += "<p>Subscription feature is not yet configured.</p>"
    html += "<p><a href='/logout'>Logout</a> | <a href='/'>Home</a></p>"
    html += "</body></html>"
    return HTMLResponse(html)

# Create Stripe checkout session
@app.post("/create-checkout-session")
async def create_checkout_session(request: Request, current_user=Depends(get_current_user)):
    # Ensure Stripe integration is available
    if not HAS_STRIPE:
        raise HTTPException(status_code=503, detail="Stripe subscription is not configured")
    user = await get_user_by_id(current_user["id"])
    # Create Stripe customer if not exists
    if not user["stripe_customer_id"]:
        customer = stripe.Customer.create(email=user["email"])
        update_query = users.update().where(users.c.id == user["id"]).values(stripe_customer_id=customer["id"])
        await database.execute(update_query)
        stripe_customer_id = customer["id"]
    else:
        stripe_customer_id = user["stripe_customer_id"]
    try:
        session = stripe.checkout.Session.create(
            customer=stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": PRICE_ID, "quantity": 1}],
            mode="subscription",
            success_url=DOMAIN + "/subscription_success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=DOMAIN + "/account",
        )
        return RedirectResponse(session.url, status_code=303)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

# Subscription success
@app.get("/subscription_success", response_class=HTMLResponse)
async def subscription_success(request: Request, session_id: str, current_user=Depends(get_current_user)):
    # Ensure Stripe integration is available
    if not HAS_STRIPE:
        raise HTTPException(status_code=503, detail="Stripe subscription is not configured")
    stripe_session = stripe.checkout.Session.retrieve(session_id)
    subscription_id = stripe_session.get("subscription")
    # Update subscription status
    await database.execute(users.update().where(users.c.id == current_user["id"]).values(
        stripe_subscription_id=subscription_id,
        subscription_status="active"
    ))
    html = "<html><body>"
    html += f"<h2>Subscription Successful!</h2><p>Thank you, {current_user.get('username')}.</p>"
    html += "<p>Your subscription is active. $10/month.</p>"
    html += "<p><a href='/account'>Go to Account</a> | <a href='/'>Home</a></p>"
    html += "</body></html>"
    return HTMLResponse(html)
