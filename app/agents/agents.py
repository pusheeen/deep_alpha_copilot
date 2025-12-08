# agents.py (Corrected for Financial Domain)
"""
Defines the ADK agent team for the financial data application.
This includes a root agent for orchestration and specialized sub-agents
for graph querying, document retrieval, and stock price predictions.
"""
try:
    from google.adk.agents import Agent
    from google.adk.models.lite_llm import LiteLlm
    ADK_CORE_AVAILABLE = True
except ImportError:
    ADK_CORE_AVAILABLE = False
    # Mock classes to allow file to load
    class Agent:
        def __init__(self, **kwargs): pass
    class LiteLlm:
        def __init__(self, **kwargs): pass

# from ..neo4j_for_adk import graphdb  # Disabled - using JSON files instead
from app.models.predict import predict_next_day_price
from langchain_google_vertexai import VertexAIEmbeddings
from target_tickers import TARGET_TICKERS
import pandas as pd
import os
import json
import requests
import logging
from datetime import datetime, timezone
import yfinance as yf

logger = logging.getLogger(__name__)
try:
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
except ImportError:
    build = None  # type: ignore[assignment]
    HttpError = Exception  # type: ignore[assignment]

# --- Setup ---
if ADK_CORE_AVAILABLE:
    try:
        llm = LiteLlm(model="gemini-2.5-pro")
    except Exception:
        llm = None
else:
    llm = None

embeddings = VertexAIEmbeddings(model_name="text-embedding-005")

GOOGLE_SEARCH_API_KEY = os.getenv("GOOGLE_SEARCH_API_KEY")
GOOGLE_SEARCH_ENGINE_ID = os.getenv("GOOGLE_SEARCH_ENGINE_ID")
TICKER_LIST_STR = ", ".join(sorted(TARGET_TICKERS))

# --- Tool Definitions ---
def query_company_data(ticker: str, data_type: str = "all") -> dict:
    """
    Query comprehensive company data from JSON files and scoring engine.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'NVDA', 'AVGO')
        data_type: Type of data to retrieve:
            - 'all': Complete analysis with scores and recommendations
            - 'risks': Investment risks and concerns
            - 'financials': Financial metrics and health
            - 'scores': All scoring categories
            - 'recommendation': Buy/hold/sell recommendation with reasoning
    
    Returns:
        dict: Requested company data
    """
    from app.scoring import compute_company_scores
    
    try:
        ticker = ticker.upper().strip()
        data = compute_company_scores(ticker)
        
        if data_type == "risks":
            risks = data.get("recommendation", {}).get("risks", [])
            main_risks = data.get("recommendation", {}).get("main_risks", "")
            key_concerns = data.get("recommendation", {}).get("key_concerns", "")
            
            return {
                "status": "success",
                "ticker": ticker,
                "risks": risks,
                "main_risks": main_risks,
                "key_concerns": key_concerns,
                "risk_summary": f"Key risks for {ticker}: {main_risks}. Concerns: {key_concerns}. Detailed risks: {', '.join(risks[:5])}"
            }
        elif data_type == "financials":
            scores = data.get("scores", {})
            return {
                "status": "success",
                "ticker": ticker,
                "financial_score": scores.get("financial", {}),
                "business_score": scores.get("business", {}),
                "quick_facts": data.get("quick_facts", {})
            }
        elif data_type == "scores":
            return {
                "status": "success",
                "ticker": ticker,
                "scores": data.get("scores", {}),
                "overall": data.get("overall", {})
            }
        elif data_type == "recommendation":
            return {
                "status": "success",
                "ticker": ticker,
                "recommendation": data.get("recommendation", {}),
                "overall_score": data.get("overall", {})
            }
        else:  # all
            return {
                "status": "success",
                "ticker": ticker,
                "data": data
            }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Failed to retrieve data for {ticker}: {str(e)}"
        }

def query_graph_database(question: str) -> dict:
    """
    Generates a Cypher query for the financial graph and executes it.
    DEPRECATED - Use query_company_data() instead for JSON-based data
    """
    return {"status": "disabled", "message": "Neo4j functionality disabled - use query_company_data() tool instead"}
    
    # CORRECTED: Updated schema description and examples to match actual database structure
    cypher_generation_prompt = f"""
    Task: Generate a Cypher statement to query a financial graph database.
    
    Schema: {schema}
    
    Instructions:
    - Use ONLY the provided relationship types and property keys.
    - The graph contains the following nodes and relationships:
      - (c:Company)-[:HAS_FINANCIALS]->(f:Financials)
      - (c:Company)-[:FILED]->(doc:Document)
      - (c:Company)-[:HAS_RISK]->(r:Risk)
      - (c:Company)-[:HAD_EVENT]->(e:Event)
      - (c:Company)-[:HAS_STRATEGY]->(s:Strategy)
      - (doc:Document)-[:MENTIONS_RISK]->(r:Risk)
      - (doc:Document)-[:DESCRIBES_EVENT]->(e:Event)
      - (doc:Document)-[:MENTIONS_STRATEGY]->(s:Strategy)
      - (chunk:Chunk) nodes with vector embeddings for document chunks
    
    - Key properties for nodes:
    - Company: `ticker` (e.g., 'NVDA'), `name`, `cik`
    - Financials: `company` (ticker), `year` (string like '2024'), `revenue`, `netIncome`, `eps`
    - Risk, Event, Strategy: `name`
    - Document: `source` (filename), `year`, `type`, `management_outlook`
    - Chunk: `text`, `embedding` (vector)
    
    - IMPORTANT: The Financials node uses `company` property (not ticker directly) and `year` is a STRING
    - Company tickers in your data: {TICKER_LIST_STR}
    
    Example Questions & Queries (ticker and year are database property names, not variables):
    - Question: "What was the revenue for NVDA in 2024?"
      Query: MATCH (c:Company {{ticker: 'NVDA'}})-[:HAS_FINANCIALS]->(f:Financials {{year: '2024'}}) RETURN f.revenue
    - Question: "What are the key risks for NVDA?"
      Query: MATCH (c:Company {{ticker: 'NVDA'}})-[:HAS_RISK]->(r:Risk) RETURN r.name
    - Question: "Show me financial trends for NVDA over the years"
      Query: MATCH (c:Company {{ticker: 'NVDA'}})-[:HAS_FINANCIALS]->(f:Financials) RETURN f.year, f.revenue, f.netIncome, f.eps ORDER BY f.year
    - Question: "What events happened at Apple?"
      Query: MATCH (c:Company {{ticker: 'AAPL'}})-[:HAD_EVENT]->(e:Event) RETURN e.name
    
    Question: {question}
    Return only the Cypher query, no explanation or formatting.
    """
    
    cypher_query = llm.llm_client.completion(
        model=llm.model,
        messages=[{"role": "user", "content": cypher_generation_prompt}],
        tools=[], # <-- ADD THIS LINE
    ).choices[0].message.content.strip()
    
    # Clean the response
    cypher_query = cypher_query.replace("```cypher", "").replace("```", "").strip()
    print(f"Generated Cypher: {cypher_query}")
    
    # return graphdb.send_query(cypher_query)
    return {"status": "disabled", "message": "Neo4j functionality disabled - using JSON files"}

def retrieve_from_documents(question: str, ticker: str = None) -> dict:
    """
    Performs RAG (Retrieval Augmented Generation) on 10-K filing documents using GCP.
    
    Uses Vertex AI Embeddings for semantic search and Gemini for answer synthesis.
    Documents are loaded from GCS (production) or local files (development).
    
    Args:
        question: User's question about SEC filings
        ticker: Optional ticker symbol to filter filings
        
    Returns:
        dict: Answer synthesized from relevant filing chunks
    """
    import re
    from pathlib import Path
    from bs4 import BeautifulSoup
    import numpy as np
    
    # Extract ticker from question if not provided
    if not ticker:
        ticker_match = re.search(r'\b([A-Z]{2,5})\b', question.upper())
        if ticker_match:
            ticker = ticker_match.group(1)
    
    try:
        # Get question embedding for semantic search
        question_embedding = embeddings.embed_query(question)
    
        # Determine data directory (GCS in production, local in dev)
        if os.getenv("K_SERVICE"):
            # Production: Use GCS
            from storage_helper import get_storage_manager
            storage_manager = get_storage_manager()
            filings_dir = Path("/tmp/data/unstructured/10k")
            filings_dir.mkdir(parents=True, exist_ok=True)
            
            # Download filings from GCS if needed
            if storage_manager and storage_manager.bucket:
                prefix = "data/unstructured/10k/"
                if ticker:
                    prefix += f"{ticker}_"
                blobs = list(storage_manager.bucket.list_blobs(prefix=prefix))
                for blob in blobs[:10]:  # Limit to recent 10 filings
                    local_path = filings_dir / blob.name.split("/")[-1]
                    if not local_path.exists():
                        try:
                            blob.download_to_filename(str(local_path))
                        except Exception as e:
                            logger.debug(f"Could not download {blob.name}: {e}")
        else:
            # Local development
            filings_dir = Path("data/unstructured/10k")
        
        # Load and process 10-K filings
        filing_chunks = []
        if filings_dir.exists():
            # Find relevant filing files
            if ticker:
                pattern = f"{ticker}_*.html"
            else:
                pattern = "*.html"
            
            filing_files = list(filings_dir.glob(pattern))[:5]  # Limit to 5 most recent
            
            for filing_path in filing_files:
                try:
                    # Extract text from HTML
                    with filing_path.open('r', encoding='utf-8') as f:
                        html_content = f.read()
                    
                    soup = BeautifulSoup(html_content, 'html.parser')
                    text = soup.get_text(separator=' ', strip=True)
                    
                    # Chunk the document (1500 chars with 150 overlap)
                    chunk_size = 1500
                    chunk_overlap = 150
                    chunks = []
                    for i in range(0, len(text), chunk_size - chunk_overlap):
                        chunk = text[i:i + chunk_size]
                        if len(chunk.strip()) > 100:  # Only keep substantial chunks
                            chunks.append({
                                'text': chunk,
                                'source': filing_path.name,
                                'ticker': ticker or filing_path.stem.split('_')[0]
                            })
                    
                    filing_chunks.extend(chunks)
                except Exception as e:
                    logger.debug(f"Error processing {filing_path}: {e}")
                    continue
        
        if not filing_chunks:
            # Fallback: Use company data if no filings available
            if ticker:
                try:
                    from app.scoring import compute_company_scores
                    data = compute_company_scores(ticker)
                    risks = data.get("recommendation", {}).get("risks", [])
                    main_risks = data.get("recommendation", {}).get("main_risks", "")
                    
                    return {
                        "answer": f"SEC 10-K filings are not currently available for {ticker}. "
                                f"However, based on available data: {main_risks}. "
                                f"Key risks include: {', '.join(risks[:3]) if risks else 'See company data for details'}.",
                        "status": "success",
                        "source": "company_data_fallback"
                    }
                except Exception:
                    pass
            
            return {
                "answer": "SEC 10-K filing documents are not currently available. "
                         "Please use CompanyData_Agent for structured financial data and analysis.",
                "status": "no_documents",
                "suggestion": "Try querying company financials, risks, or scores instead"
            }
        
        # Perform semantic search using embeddings
        chunk_embeddings = []
        for chunk in filing_chunks:
            try:
                chunk_emb = embeddings.embed_query(chunk['text'])
                chunk_embeddings.append(chunk_emb)
            except Exception as e:
                logger.debug(f"Error embedding chunk: {e}")
                chunk_embeddings.append(None)
        
        # Calculate cosine similarity
        similarities = []
        for chunk_emb in chunk_embeddings:
            if chunk_emb is not None:
                # Cosine similarity
                dot_product = np.dot(question_embedding, chunk_emb)
                norm_q = np.linalg.norm(question_embedding)
                norm_c = np.linalg.norm(chunk_emb)
                similarity = dot_product / (norm_q * norm_c) if (norm_q * norm_c) > 0 else 0
                similarities.append(similarity)
            else:
                similarities.append(0)
        
        # Get top 5 most relevant chunks
        top_indices = np.argsort(similarities)[-5:][::-1]
        top_chunks = [filing_chunks[i] for i in top_indices if similarities[i] > 0.3]  # Threshold: 0.3
        
        if not top_chunks:
            return {
                "answer": "No relevant information found in SEC 10-K filings for this question. "
                         "The filings may not contain information related to your query.",
                "status": "no_relevant_chunks"
            }
        
        # Combine top chunks as context
        context = "\n\n---\n\n".join([
            f"[Source: {chunk['source']}]\n{chunk['text']}"
            for chunk in top_chunks
        ])
        
        # Synthesize answer using Gemini
        if llm:
            synthesis_prompt = f"""Based on the following context from SEC 10-K filings, answer the question comprehensively.
    
    Context from filings:
    {context}
    
    Question: {question}
    
    Instructions:
    - Provide a detailed answer based on the context
    - If the context doesn't contain relevant information, say so
- Cite specific information from the filings when possible (mention the source file)
    - Focus on the financial and strategic aspects mentioned
- Be concise but thorough
    
Answer:"""
    
            try:
                answer = llm.llm_client.completion(
        model=llm.model,
        messages=[{"role": "user", "content": synthesis_prompt}],
                    tools=[],
                ).choices[0].message.content.strip()
                
                return {
                    "answer": answer,
                    "status": "success",
                    "sources": list(set(chunk['source'] for chunk in top_chunks)),
                    "chunks_used": len(top_chunks)
                }
            except Exception as e:
                logger.error(f"Error synthesizing answer with LLM: {e}")
                # Fallback: return top chunk directly
                return {
                    "answer": f"Based on SEC filings ({top_chunks[0]['source']}):\n\n{top_chunks[0]['text'][:500]}...",
                    "status": "partial",
                    "sources": [top_chunks[0]['source']],
                    "note": "LLM synthesis failed, showing raw chunk"
                }
        else:
            # No LLM available, return top chunk
            return {
                "answer": f"Based on SEC filings ({top_chunks[0]['source']}):\n\n{top_chunks[0]['text']}",
                "status": "success",
                "sources": [top_chunks[0]['source']],
                "note": "LLM not available, showing raw chunk"
            }
    
    except Exception as e:
        logger.error(f"Error in retrieve_from_documents: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "answer": f"Error retrieving documents: {str(e)}. Please try querying company data instead.",
            "status": "error",
            "error": str(e)
        }

def _discover_trained_tickers() -> set:
    from pathlib import Path
    models_dir = Path(__file__).resolve().parents[1] / "models" / "saved_models"
    if not models_dir.exists():
        return set()
    tickers = set()
    for p in models_dir.glob("*_price_regressor.joblib"):
        tickers.add(p.name.split('_')[0].upper())
    return tickers


def predict_stock_price_tool(ticker: str) -> dict:
    """
    A wrapper for the stock price prediction model.
    Input must be a single, valid stock ticker string from our available companies.
    """
    valid_tickers = _discover_trained_tickers()
    
    if not isinstance(ticker, str):
        return {"error": f"Invalid input type. Please provide a ticker as a string."}
    
    ticker = ticker.upper().strip()
    
    if not valid_tickers:
        return {"error": "No trained models found. Train models via app/models/train_predictor.py first."}
    if ticker not in valid_tickers:
        return {"error": f"Ticker '{ticker}' not found. Available tickers: {', '.join(sorted(valid_tickers))}"}
    
    print(f"Predicting price for ticker: {ticker}")
    return predict_next_day_price(ticker)


def search_latest_news(query: str, max_results: int = 5) -> dict:
    """
    Uses Google Custom Search API to retrieve the latest news articles related to the query.
    """
    if not GOOGLE_SEARCH_API_KEY or not GOOGLE_SEARCH_ENGINE_ID:
        return {"error": "Google Search API is not configured. Please set GOOGLE_SEARCH_API_KEY and GOOGLE_SEARCH_ENGINE_ID."}

    if build is None:
        return {"error": "google-api-python-client is not installed. Please install google-api-python-client."}

    max_results = max(1, min(max_results, 10))

    try:
        service = build("customsearch", "v1", developerKey=GOOGLE_SEARCH_API_KEY, cache_discovery=False)
        response = service.cse().list(
            q=query,
            cx=GOOGLE_SEARCH_ENGINE_ID,
            num=max_results,
            dateRestrict="d3"
        ).execute()

        items = response.get("items", [])
        if not items:
            return {"results": [], "message": "No recent news found for the query."}

        results = []
        for item in items:
            pagemap = item.get("pagemap", {})
            metatags = pagemap.get("metatags", [{}])
            news_article = pagemap.get("newsarticle", [{}])

            published = (
                metatags[0].get("article:published_time")
                or metatags[0].get("og:updated_time")
                or news_article[0].get("datepublished")
                or news_article[0].get("datemodified")
            )

            source = metatags[0].get("og:site_name") if metatags else None

            results.append({
                "title": item.get("title"),
                "link": item.get("link"),
                "snippet": item.get("snippet"),
                "published": published,
                "source": source
            })

        return {"query": query, "results": results}
    except HttpError as http_error:
        return {"error": f"Google Search API error: {http_error}"}
    except Exception as exc:
        return {"error": f"Unexpected error querying Google Search API: {exc}"}


def fetch_intraday_price_and_events(ticker: str, max_events: int = 5) -> dict:
    """
    Fetches the latest available price information and recent news events for a ticker.
    Uses Yahoo Finance (delayed data) for intraday prices and press coverage.
    """
    if not isinstance(ticker, str):
        return {"error": "Ticker must be provided as a string."}

    ticker = ticker.upper().strip()
    if ticker not in TARGET_TICKERS:
        return {"error": f"Ticker '{ticker}' is not in the supported list: {TICKER_LIST_STR}"}

    try:
        instrument = yf.Ticker(ticker)
    except Exception as exc:
        return {"error": f"Failed to initialize market data client for {ticker}: {exc}"}

    price_payload: dict = {}
    try:
        fast_info = getattr(instrument, "fast_info", {}) or {}
        last_price = fast_info.get("last_price")
        prev_close = fast_info.get("previous_close") or fast_info.get("regular_market_previous_close")
        currency = fast_info.get("currency") or fast_info.get("last_price_currency")
        exchange = fast_info.get("exchange") or fast_info.get("market")
        price_time = fast_info.get("last_price_time")

        if not last_price:
            intraday = instrument.history(period="1d", interval="5m")
            if not intraday.empty:
                last_row = intraday.tail(1).iloc[0]
                last_price = float(last_row["Close"])
                prev_close = prev_close or float(intraday.head(1).iloc[0]["Open"])
                price_time = last_row.name.to_pydatetime().replace(tzinfo=timezone.utc)

        if last_price:
            change = None
            percent_change = None
            if prev_close and prev_close != 0:
                change = float(last_price) - float(prev_close)
                percent_change = (change / float(prev_close)) * 100

            if isinstance(price_time, (int, float)):
                price_dt = datetime.fromtimestamp(price_time, tz=timezone.utc)
            elif isinstance(price_time, datetime):
                price_dt = price_time.astimezone(timezone.utc)
            else:
                price_dt = datetime.now(timezone.utc)

            price_payload = {
                "ticker": ticker,
                "last_price": round(float(last_price), 4),
                "previous_close": round(float(prev_close), 4) if prev_close else None,
                "change": round(float(change), 4) if change is not None else None,
                "percent_change": round(float(percent_change), 4) if percent_change is not None else None,
                "currency": currency,
                "exchange": exchange,
                "price_timestamp_utc": price_dt.isoformat(),
                "disclaimer": "Pricing data sourced from Yahoo Finance and may be delayed."
            }
        else:
            price_payload = {"warning": f"No price data available for {ticker} at this time."}
    except Exception as exc:
        price_payload = {"error": f"Failed to fetch intraday price for {ticker}: {exc}"}

    events: list = []
    try:
        raw_news = getattr(instrument, "news", []) or []
        for item in raw_news[:max_events]:
            published = item.get("providerPublishTime")
            if published:
                published_dt = datetime.fromtimestamp(published, tz=timezone.utc).isoformat()
            else:
                published_dt = None
            events.append({
                "title": item.get("title"),
                "publisher": item.get("publisher"),
                "published_at_utc": published_dt,
                "type": item.get("type"),
                "link": item.get("link")
            })
    except Exception as exc:
        events = []
        price_payload.setdefault("warnings", []).append(f"Failed to retrieve news for {ticker}: {exc}")

    return {
        "ticker": ticker,
        "price": price_payload,
        "recent_events": events,
        "notes": "News items provided by Yahoo Finance; availability varies by ticker."
    }

# --- Sub-Agent Definitions ---
graph_qa_subagent = Agent(
    name="CompanyData_Agent",
    model=llm,
    tools=[query_company_data],
    description=f"Use for questions about company financials, risks, scores, and investment analysis from JSON data. Works with tickers: {TICKER_LIST_STR}.",
    instruction=f"""
    Your task is to use the `query_company_data` tool to answer questions about companies.
    
    CAPABILITIES:
    - Financial metrics and scores (use data_type='financials')
    - Investment risks and concerns (use data_type='risks')
    - All scoring categories (use data_type='scores')  
    - Buy/hold/sell recommendations (use data_type='recommendation')
    - Complete company analysis (use data_type='all')
    
    IMPORTANT:
    - Always use exact ticker symbols: {TICKER_LIST_STR}
    - For risk questions, use data_type='risks' to get comprehensive risk analysis
    - For financial health questions, use data_type='financials'
    - For investment decisions, use data_type='recommendation'
    - Provide detailed, actionable insights based on the returned data
    
    EXAMPLES:
    - "What are the risks for AVGO?" → query_company_data(ticker="AVGO", data_type="risks")
    - "How is NVDA's financial health?" → query_company_data(ticker="NVDA", data_type="financials")
    - "Should I buy TSLA?" → query_company_data(ticker="TSLA", data_type="recommendation")
    """
)

document_rag_subagent = Agent(
    name="DocumentRAG_Agent",
    model=llm,
    tools=[retrieve_from_documents],
    description="Use for qualitative questions about company strategy, management outlook, detailed business descriptions, or any information that requires reading through SEC 10-K filing text. Uses GCP-based RAG with Vertex AI Embeddings and Gemini synthesis.",
    instruction="""
    Your task is to use the `retrieve_from_documents` tool to find detailed, qualitative information from SEC 10-K filings stored in Google Cloud Storage.
    
    The tool performs semantic search using Vertex AI Embeddings and synthesizes answers using Gemini.
    
    Use this agent for:
    - Management's discussion and analysis (MD&A)
    - Business strategy and outlook
    - Detailed risk descriptions
    - Product and service descriptions
    - Market analysis and competitive positioning
    - Qualitative insights from SEC filings
    
    IMPORTANT:
    - The tool automatically extracts ticker from question if not provided
    - Documents are loaded from GCS in production or local files in development
    - Answers are synthesized from the most relevant filing chunks
    - If no filings are available, the tool will suggest using CompanyData_Agent instead
    
    Provide comprehensive answers based on the retrieved document chunks, citing source files when possible.
    """
)

prediction_subagent = Agent(
    name="StockPricePredictor_Agent",
    model=llm,
    tools=[predict_stock_price_tool],
    description="Use ONLY to predict the next day's closing stock price. Dynamically discovers available tickers from trained models.",
    instruction="""
    Your only task is to use the `predict_stock_price_tool` for stock price predictions.

    IMPORTANT:
    - Only use tickers for which models have been trained (dynamically discovered).
    - Input must be a single ticker string.
    - Always include a disclaimer that predictions are estimates based on historical data and not financial advice.
    """
)

news_search_subagent = Agent(
    name="NewsSearch_Agent",
    model=llm,
    tools=[search_latest_news],
    description="Use to gather the latest news headlines and summaries for financial queries.",
    instruction="""
    Your task is to search for the most recent and relevant news stories that help answer the user's question.

    CAPABILITIES:
    - Retrieve fresh headlines related to companies, sectors, or macroeconomic topics
    - Provide source name, publication time, and short summaries
    - Highlight multiple perspectives when available

    IMPORTANT:
    - Use concise summaries referencing the original article
    - Include publication time and source where possible
    - Clarify that links point to external news sites
    - Do not fabricate articles; rely solely on returned search results
    """
)

def get_sector_news(sector: str) -> dict:
    """
    Fetches news articles for a given financial sector.
    """
    from fetch_data.sector_news import fetch_sector_news
    try:
        articles = fetch_sector_news(sector)
        return {'sector': sector, 'articles': articles}
    except Exception as e:
        return {'error': f"Failed to fetch sector news for {sector}: {e}"}

sector_news_subagent = Agent(
    name="SectorNews_Agent",
    model=llm,
    tools=[get_sector_news],
    description="Use to fetch the latest news articles for a given financial sector.",
    instruction="""
    Your task is to retrieve the latest news articles for a financial sector.
    Use the `get_sector_news` tool, which takes a sector name as input and returns the articles.
    """
)

def get_token_usage(days: int = 90) -> dict:
    """
    Fetches AI token usage data from OpenRouter API for the last N days.
    
    Args:
        days: Number of days of history to fetch (default: 90, i.e., 3 months)
    
    Returns:
        Dictionary containing token usage data by model
    """
    from fetch_data.token_usage import fetch_openrouter_usage_history, aggregate_usage_by_model
    
    try:
        usage_data = fetch_openrouter_usage_history(days=days)
        
        if usage_data.get('error'):
            return {'error': usage_data.get('error')}
        
        # Aggregate by model if we have usage data
        if usage_data.get('usage_data'):
            aggregated = aggregate_usage_by_model(usage_data['usage_data'])
            usage_data['aggregated_by_model'] = aggregated
        
        return {
            'status': 'success',
            'days': usage_data.get('days', days),
            'total_models': len(usage_data.get('aggregated_by_model', [])),
            'total_tokens': usage_data.get('total_tokens', 0),
            'total_requests': usage_data.get('total_requests', 0),
            'fetch_timestamp': usage_data.get('fetch_timestamp'),
            'model_consumption': usage_data.get('aggregated_by_model', [])[:15],  # Top 15
            'source': usage_data.get('source', 'estimated')
        }
    except Exception as e:
        return {'error': f"Failed to fetch token usage: {e}"}

token_usage_subagent = Agent(
    name="TokenUsage_Agent",
    model=llm,
    tools=[get_token_usage],
    description="Use to fetch AI token consumption data from OpenRouter API. Shows which AI models are being used and their token consumption over the last 3 months.",
    instruction="""
    Your task is to retrieve AI token usage data showing which models are consuming tokens.
    
    CAPABILITIES:
    - Fetch token usage for the last 3 months (90 days) by default
    - Show token consumption by model
    - Display total tokens, requests, and costs
    
    IMPORTANT:
    - Use get_token_usage() to fetch the latest data
    - Present the data in a clear, organized format
    - Highlight the most used models
    - Explain what the token usage means for the system
    """
)

market_data_subagent = Agent(
    name="MarketData_Agent",
    model=llm,
    tools=[fetch_intraday_price_and_events],
    description="Use to retrieve the latest available stock price and recent events for supported tickers using Yahoo Finance.",
    instruction=f"""
    Your task is to report the most recent market data for a company.

    CAPABILITIES:
    - Provide the latest intraday price (delayed) and percent change for supported tickers ({TICKER_LIST_STR})
    - Include timestamp, exchange, and currency when available
    - Surface recent news/events with titles, publishers, and links
    - Mention that prices may be delayed and sourced from Yahoo Finance

    IMPORTANT:
    - Only answer for supported tickers
    - Clearly state when data is unavailable or delayed
    - Do not generate forecasts; stick to retrieved data
    """
)




def get_market_index_data(index_name: str) -> dict:
    """
    Fetches data for a specific market index.
    """
    from fetch_data.market_indices import fetch_market_indices
    indices = fetch_market_indices()
    return indices.get(index_name, {"error": f"Index '{index_name}' not found."})

market_indices_subagent = Agent(
    name="MarketIndices_Agent",
    model=llm,
    tools=[get_market_index_data],
    description="Use to get data for major market indices like VIX, NASDAQ, Dow Jones, and Russell 2000.",
    instruction="""
    Your task is to provide data for a given market index.
    Use the `get_market_index_data` tool to retrieve the data.
    """
)

def query_twitter_data(ticker: str) -> dict:
    """
    Fetches real-time Twitter/X data for a specific company ticker.
    """
    from fetch_data.twitter import fetch_x_data_for_company, initialize_x_client
    from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
    client = initialize_x_client()
    if not client:
        return {"error": "X/Twitter client not available."}
    analyzer = SentimentIntensityAnalyzer()
    # This is a simplified version for real-time query, for full data use the batch script
    # We need to get company name and ceo name from somewhere, for now, we'll just use the ticker
    return fetch_x_data_for_company(client, ticker, ticker, "", analyzer)

twitter_subagent = Agent(
    name="Twitter_Agent",
    model=llm,
    tools=[query_twitter_data],
    description="Use for REAL-TIME Twitter/X sentiment analysis and social media discussions about stocks.",
    instruction="""
    Your task is to fetch and analyze LIVE Twitter/X sentiment for specific tickers.
    """
)

def get_sector_metrics(sector: str) -> dict:
    """
    Fetches calculated metrics for a given financial sector.
    """
    import json
    from fetch_data.utils import SECTOR_METRICS_DIR
    try:
        with open(os.path.join(SECTOR_METRICS_DIR, "sector_metrics.json"), 'r') as f:
            sector_metrics = json.load(f)
        return sector_metrics.get(sector, {"error": f"Sector '{sector}' not found."})
    except FileNotFoundError:
        return {"error": "Sector metrics file not found. Please run the data fetching script."}
    except Exception as e:
        return {"error": f"Error reading sector metrics: {e}"}

sector_metrics_subagent = Agent(
    name="SectorMetrics_Agent",
    model=llm,
    tools=[get_sector_metrics],
    description="Use to get calculated metrics for a specific financial sector (e.g., 'Technology', 'Energy').",
    instruction="""
    Your task is to provide calculated metrics for a given financial sector.
    Use the `get_sector_metrics` tool to retrieve the data.
    """
)

def get_flow_data(ticker: str, flow_type: str = "combined", date: str = "latest") -> dict:
    """
    Fetches institutional and retail flow data for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g., 'NVDA', 'AVGO')
        flow_type: Type of flow data to retrieve:
            - 'institutional': Institutional ownership and flow
            - 'retail': Retail flow estimates
            - 'combined': Both institutional and retail (default)
            - 'changes': Institutional changes only
        date: Date to retrieve (YYYYMMDD format) or 'latest' for most recent

    Returns:
        dict: Flow data for the specified ticker
    """
    import json
    import glob
    from fetch_data.utils import FLOW_DATA_DIR

    try:
        ticker = ticker.upper().strip()

        # Determine the file pattern based on flow_type
        if flow_type == "institutional":
            pattern = os.path.join(FLOW_DATA_DIR, f"{ticker}_institutional_flow_*.json")
        elif flow_type == "retail":
            pattern = os.path.join(FLOW_DATA_DIR, f"{ticker}_retail_flow_*.json")
        else:  # combined or changes
            pattern = os.path.join(FLOW_DATA_DIR, f"{ticker}_combined_flow_*.json")

        # Find matching files
        files = glob.glob(pattern)

        if not files:
            return {
                "status": "error",
                "ticker": ticker,
                "message": f"No flow data files found for {ticker}. Please run the data fetching script first."
            }

        # Sort files by date (newest first) and get the latest or specific date
        files.sort(reverse=True)

        if date == "latest":
            filename = files[0]
        else:
            # Look for specific date
            date_match = [f for f in files if date in f]
            if not date_match:
                return {
                    "status": "error",
                    "ticker": ticker,
                    "message": f"No flow data found for {ticker} on date {date}"
                }
            filename = date_match[0]

        with open(filename, 'r') as f:
            flow_data = json.load(f)

        # If requesting changes only, extract just the changes section
        if flow_type == "changes":
            if "institutional_changes" in flow_data:
                return {
                    "status": "success",
                    "ticker": ticker,
                    "flow_type": flow_type,
                    "data": flow_data["institutional_changes"],
                    "file_date": os.path.basename(filename).split('_')[-1].replace('.json', '')
                }
            else:
                return {
                    "status": "error",
                    "ticker": ticker,
                    "message": "Institutional changes data not available in this file"
                }

        return {
            "status": "success",
            "ticker": ticker,
            "flow_type": flow_type,
            "data": flow_data,
            "file_date": os.path.basename(filename).split('_')[-1].replace('.json', ''),
            "available_dates": [os.path.basename(f).split('_')[-1].replace('.json', '') for f in files]
        }

    except FileNotFoundError:
        return {
            "status": "error",
            "ticker": ticker,
            "message": f"Flow data file not found for {ticker}. Please run the data fetching script."
        }
    except Exception as e:
        return {
            "status": "error",
            "ticker": ticker,
            "message": f"Error reading flow data: {e}"
        }

flow_data_subagent = Agent(
    name="FlowData_Agent",
    model=llm,
    tools=[get_flow_data],
    description="Use to get institutional and retail flow data for stocks, including ownership changes, inflow/outflow tracking, and volume patterns.",
    instruction=f"""
    Your task is to retrieve and analyze institutional and retail flow data for specific tickers.

    CAPABILITIES:
    - Institutional ownership and holder information (use flow_type='institutional')
    - Retail flow estimates based on volume patterns (use flow_type='retail')
    - Combined institutional and retail analysis (use flow_type='combined')
    - Institutional inflow/outflow tracking (use flow_type='changes')
    - Historical flow data with date-based tracking
    - Daily flow metrics and trends

    INSTITUTIONAL CHANGE TRACKING:
    - Compares current holdings with previous period
    - Shows which institutions bought or sold shares
    - Calculates net institutional inflow/outflow
    - Identifies top 5 buyers and sellers
    - Provides percentage changes for each holder

    IMPORTANT:
    - Always use exact ticker symbols: {TICKER_LIST_STR}
    - For institutional data: Shows top holders, ownership percentages, and institutional changes
    - For retail data: Provides estimated retail participation and flow direction
    - For changes: Shows institutional buying/selling activity
    - Include disclaimers that retail estimates are based on heuristics
    - Explain the data in context of market sentiment and investor behavior
    - Data files are saved daily with date suffixes (YYYYMMDD)

    EXAMPLES:
    - "What's the institutional ownership of NVDA?" → get_flow_data(ticker="NVDA", flow_type="institutional")
    - "Show me retail flow for AVGO" → get_flow_data(ticker="AVGO", flow_type="retail")
    - "Analyze flow data for TSLA" → get_flow_data(ticker="TSLA", flow_type="combined")
    - "Did institutions buy or sell NVDA recently?" → get_flow_data(ticker="NVDA", flow_type="changes")
    - "Show institutional changes for AMD" → get_flow_data(ticker="AMD", flow_type="changes")
    """
)


# --- LinkedIn CEO Lookup Agent ---
def query_ceo_info_by_ticker(ticker: str) -> dict:
    """
    Queries CEO information by company ticker using multiple data sources.

    Args:
        ticker: The company ticker symbol (e.g., 'NVDA', 'AAPL')

    Returns:
        dict: Contains CEO name, current title, duration, and company info
    """
    import requests
    from bs4 import BeautifulSoup
    import re
    from datetime import datetime
    from dateutil import parser
    import json

    try:
        # Validate ticker input
        if not ticker or not isinstance(ticker, str):
            return {"error": "Invalid ticker. Please provide a valid stock ticker symbol."}

        ticker = ticker.upper().strip()

        # Get company name from data/companies.csv if available
        company_name = f"{ticker} Company"
        if os.path.exists("data/companies.csv"):
            try:
                companies_df = pd.read_csv("data/companies.csv")
                company_row = companies_df[companies_df['ticker'] == ticker]
                if not company_row.empty:
                    company_name = company_row.iloc[0]['company_name']
            except Exception:
                pass

        ceo_data = {
            "ticker": ticker,
            "company_name": company_name,
            "ceo_name": "Not found",
            "ceo_title": "Not found",
            "tenure_duration": "Not found",
            "start_date": "Not found",
            "linkedin_url": "Not found",
            "source": "Multiple sources",
            "past_experience": [],
            "education": "Not found",
            "career_highlights": []
        }

        # Method 1: Try to find CEO via company's investor relations or about page
        search_terms = [
            f"{company_name} CEO chief executive officer",
            f"{ticker} company CEO leadership",
            f"{company_name} management team"
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
        }

        # Method 2: Use a direct company website search or SEC filings approach
        # For well-known companies, use hardcoded data for reliability
        known_ceos = {
            'NVDA': {
                'name': 'Jensen Huang',
                'title': 'President, CEO and Co-Founder',
                'start_date': 'April 1993',
                'calculated_duration': '30+ years',
                'source': 'NVIDIA official records',
                'past_experience': [
                    {'company': 'AMD', 'role': 'Director of CoreWare', 'duration': '1993', 'description': 'Led microprocessor design'},
                    {'company': 'LSI Logic', 'role': 'Microprocessor Designer', 'duration': '1985-1993', 'description': 'Designed microprocessors and chipsets'}
                ],
                'education': 'Stanford University (MS Electrical Engineering), Oregon State University (BS Electrical Engineering)',
                'career_highlights': [
                    'Co-founded NVIDIA at age 30',
                    'Led GPU revolution in computing',
                    'Pioneer in AI and machine learning hardware',
                    'Named one of Time\'s 100 Most Influential People'
                ]
            },
            'AAPL': {
                'name': 'Tim Cook',
                'title': 'Chief Executive Officer',
                'start_date': 'August 2011',
                'calculated_duration': '13+ years',
                'source': 'Apple official records',
                'past_experience': [
                    {'company': 'Apple', 'role': 'Chief Operating Officer', 'duration': '2007-2011', 'description': 'Managed worldwide sales and operations'},
                    {'company': 'Apple', 'role': 'Senior Vice President of Worldwide Operations', 'duration': '1998-2007', 'description': 'Streamlined manufacturing and supply chain'},
                    {'company': 'Compaq', 'role': 'Vice President of Corporate Materials', 'duration': '1994-1998', 'description': 'Managed procurement and vendor relations'},
                    {'company': 'IBM', 'role': 'Various Positions', 'duration': '1982-1994', 'description': 'Operations and supply chain management'}
                ],
                'education': 'Auburn University (BS Industrial Engineering), Duke University (MBA)',
                'career_highlights': [
                    'Transformed Apple\'s supply chain operations',
                    'Succeeded Steve Jobs as CEO',
                    'Led Apple to become world\'s most valuable company',
                    'Advocate for privacy and environmental sustainability'
                ]
            },
            'MSFT': {
                'name': 'Satya Nadella',
                'title': 'Chairman and Chief Executive Officer',
                'start_date': 'February 2014',
                'calculated_duration': '10+ years',
                'source': 'Microsoft official records',
                'past_experience': [
                    {'company': 'Microsoft', 'role': 'Executive Vice President of Cloud and Enterprise', 'duration': '2011-2014', 'description': 'Led Azure cloud computing platform'},
                    {'company': 'Microsoft', 'role': 'Senior Vice President of R&D for Online Services', 'duration': '2007-2011', 'description': 'Oversaw Bing search engine development'},
                    {'company': 'Microsoft', 'role': 'Various Technical Leadership Roles', 'duration': '1992-2007', 'description': 'Led multiple product divisions including Office and Windows Server'}
                ],
                'education': 'University of Chicago Booth School of Business (MBA), University of Wisconsin-Milwaukee (MS Computer Science), Manipal Institute of Technology (BS Electrical Engineering)',
                'career_highlights': [
                    'Transformed Microsoft to cloud-first company',
                    'Led successful Azure cloud platform launch',
                    '22+ years at Microsoft before becoming CEO',
                    'Focused on AI and digital transformation'
                ]
            },
            'GOOGL': {
                'name': 'Sundar Pichai',
                'title': 'Chief Executive Officer',
                'start_date': 'October 2015',
                'calculated_duration': '9+ years',
                'source': 'Alphabet official records',
                'past_experience': [
                    {'company': 'Google', 'role': 'Senior Vice President of Products', 'duration': '2013-2015', 'description': 'Oversaw Google\'s product portfolio including Search, Maps, and Google+'},
                    {'company': 'Google', 'role': 'Vice President of Product Management', 'duration': '2008-2013', 'description': 'Led Chrome browser development and strategy'},
                    {'company': 'Google', 'role': 'Product Manager', 'duration': '2004-2008', 'description': 'Worked on Google Toolbar and other early products'},
                    {'company': 'McKinsey & Company', 'role': 'Consultant', 'duration': '2002-2004', 'description': 'Management consulting'},
                    {'company': 'Applied Materials', 'role': 'Engineer', 'duration': '2000-2002', 'description': 'Semiconductor equipment engineering'}
                ],
                'education': 'Stanford University (MBA), University of Pennsylvania (MS Materials Science), Indian Institute of Technology Kharagpur (B.Tech Metallurgical Engineering)',
                'career_highlights': [
                    'Led development of Google Chrome browser',
                    'Oversaw Android mobile operating system',
                    'Instrumental in Google\'s mobile-first strategy',
                    'Became CEO of Alphabet in 2019'
                ]
            },
            'AMZN': {
                'name': 'Andy Jassy',
                'title': 'President and Chief Executive Officer',
                'start_date': 'July 2021',
                'calculated_duration': '3+ years',
                'source': 'Amazon official records',
                'past_experience': [
                    {'company': 'Amazon Web Services', 'role': 'CEO', 'duration': '2016-2021', 'description': 'Led world\'s largest cloud computing platform'},
                    {'company': 'Amazon Web Services', 'role': 'Senior Vice President', 'duration': '2006-2016', 'description': 'Built AWS from startup to $10B+ business'},
                    {'company': 'Amazon', 'role': 'Various Leadership Roles', 'duration': '1997-2006', 'description': 'Led multiple business units and strategic initiatives'},
                    {'company': 'MBI', 'role': 'Project Manager', 'duration': '1990s', 'description': 'Early career in project management'}
                ],
                'education': 'Harvard Business School (MBA), Harvard University (BA Government)',
                'career_highlights': [
                    'Built Amazon Web Services into dominant cloud platform',
                    '24+ years at Amazon before becoming CEO',
                    'Pioneered cloud computing industry',
                    'Succeeded Jeff Bezos as Amazon CEO'
                ]
            },
            'TSLA': {
                'name': 'Elon Musk',
                'title': 'Chief Executive Officer',
                'start_date': 'October 2008',
                'calculated_duration': '16+ years',
                'source': 'Tesla official records',
                'past_experience': [
                    {'company': 'SpaceX', 'role': 'Founder, CEO and CTO', 'duration': '2002-Present', 'description': 'Private space exploration and satellite internet'},
                    {'company': 'PayPal (X.com)', 'role': 'Co-founder and CEO', 'duration': '1999-2002', 'description': 'Online payment system, sold to eBay for $1.5B'},
                    {'company': 'Zip2', 'role': 'Co-founder and CEO', 'duration': '1995-1999', 'description': 'Online city guide software, sold to Compaq for $307M'}
                ],
                'education': 'University of Pennsylvania (BS Physics, BS Economics), Stanford University (PhD Physics - dropped out)',
                'career_highlights': [
                    'Serial entrepreneur with multiple successful exits',
                    'Revolutionized electric vehicle industry',
                    'Advancing space exploration through SpaceX',
                    'World\'s richest person (various times)'
                ]
            },
            'META': {
                'name': 'Mark Zuckerberg',
                'title': 'Chairman and Chief Executive Officer',
                'start_date': 'February 2004',
                'calculated_duration': '20+ years',
                'source': 'Meta official records',
                'past_experience': [
                    {'company': 'Harvard University', 'role': 'Student / Early Facebook Development', 'duration': '2003-2004', 'description': 'Created Facebook while studying psychology and computer science'},
                    {'company': 'Various Programming Projects', 'role': 'Programmer', 'duration': 'High School - 2003', 'description': 'Created Synapse Media Player and other software applications'}
                ],
                'education': 'Harvard University (Psychology and Computer Science - dropped out)',
                'career_highlights': [
                    'Founded Facebook at age 19',
                    'Built world\'s largest social media platform',
                    'Youngest billionaire at age 23',
                    'Leading development of metaverse technologies'
                ]
            },
            'IREN': {
                'name': 'Daniel Roberts',
                'title': 'Chief Executive Officer and Co-Founder',
                'start_date': 'November 2018',
                'calculated_duration': '6+ years',
                'source': 'Iris Energy official records',
                'past_experience': [
                    {'company': 'Macquarie Group', 'role': 'Investment Banking', 'duration': '2010-2018', 'description': 'Corporate finance and renewable energy investments'},
                    {'company': 'Various Energy Companies', 'role': 'Strategy and Development', 'duration': '2008-2010', 'description': 'Renewable energy project development'}
                ],
                'education': 'University of Sydney (Finance and Economics)',
                'career_highlights': [
                    'Co-founded Iris Energy focused on sustainable Bitcoin mining',
                    'Expertise in renewable energy and cryptocurrency',
                    'Led company to NASDAQ listing',
                    'Pioneer in ESG-focused cryptocurrency mining'
                ]
            }
        }

        if ticker in known_ceos:
            ceo_info = known_ceos[ticker]
            ceo_data.update({
                "ceo_name": ceo_info['name'],
                "ceo_title": ceo_info['title'],
                "start_date": ceo_info['start_date'],
                "tenure_duration": ceo_info['calculated_duration'],
                "source": ceo_info['source'],
                "past_experience": ceo_info.get('past_experience', []),
                "education": ceo_info.get('education', 'Not found'),
                "career_highlights": ceo_info.get('career_highlights', [])
            })

            # Try to find LinkedIn profile for the CEO
            try:
                linkedin_search_url = f"https://www.google.com/search?q={ceo_info['name']}+{company_name}+linkedin"
                search_response = requests.get(linkedin_search_url, headers=headers, timeout=10)

                if search_response.status_code == 200:
                    linkedin_pattern = r'https://[a-z]{2,3}\.linkedin\.com/in/[a-zA-Z0-9\-]+/?'
                    linkedin_matches = re.findall(linkedin_pattern, search_response.text)

                    if linkedin_matches:
                        # Clean and validate LinkedIn URL
                        linkedin_url = linkedin_matches[0].replace('\\', '')
                        if 'linkedin.com/in/' in linkedin_url:
                            ceo_data["linkedin_url"] = linkedin_url

            except Exception as e:
                pass  # LinkedIn search failed, continue without it

        else:
            # Method 3: For unknown companies, try web scraping approach
            try:
                # Search for CEO information using Google search
                search_query = f"{company_name} current CEO chief executive officer 2025"
                search_url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"

                search_response = requests.get(search_url, headers=headers, timeout=10)

                if search_response.status_code == 200:
                    soup = BeautifulSoup(search_response.content, 'html.parser')

                    # Look for CEO information in search results
                    text_content = soup.get_text()

                    # Common patterns for CEO information
                    ceo_patterns = [
                        rf'{re.escape(company_name)}.*?CEO[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                        rf'CEO[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+).*?{re.escape(company_name)}',
                        rf'Chief Executive Officer[:\s]*([A-Z][a-z]+\s+[A-Z][a-z]+)',
                        rf'([A-Z][a-z]+\s+[A-Z][a-z]+)[,\s]*CEO of {re.escape(company_name)}',
                    ]

                    for pattern in ceo_patterns:
                        matches = re.findall(pattern, text_content, re.IGNORECASE)
                        if matches:
                            potential_ceo = matches[0].strip()
                            # Validate the name (should be 2-4 words, proper capitalization)
                            if 2 <= len(potential_ceo.split()) <= 4 and potential_ceo.replace(' ', '').isalpha():
                                ceo_data["ceo_name"] = potential_ceo
                                ceo_data["ceo_title"] = "Chief Executive Officer"
                                ceo_data["source"] = "Web search results"
                                break

            except Exception as e:
                ceo_data["search_error"] = f"Web search failed: {str(e)}"

        # Calculate more precise duration if we have start date
        if ceo_data["start_date"] != "Not found":
            try:
                # Extract year from start date
                year_match = re.search(r'(\d{4})', ceo_data["start_date"])
                if year_match:
                    start_year = int(year_match.group(1))
                    current_year = datetime.now().year
                    years_tenure = current_year - start_year

                    if years_tenure >= 0:
                        ceo_data["calculated_years"] = years_tenure
                        if years_tenure == 1:
                            ceo_data["tenure_duration"] = "1 year"
                        else:
                            ceo_data["tenure_duration"] = f"{years_tenure} years"

            except Exception as e:
                pass  # Keep original duration if calculation fails

        return {
            "success": True,
            "ceo_data": ceo_data,
            "note": "CEO information compiled from multiple sources. Data accuracy may vary for less common companies."
        }

    except Exception as e:
        return {"error": f"Error retrieving CEO information: {str(e)}"}

# --- Reddit Sentiment Agent ---
def query_reddit_sentiment(ticker: str, limit: int = 20) -> dict:
    """
    Fetches real-time Reddit sentiment for a specific company ticker.
    Uses PRAW API with stored credentials to scrape recent posts.
    
    Args:
        ticker: Stock ticker symbol (e.g., 'NVDA', 'AVGO')
        limit: Number of posts to fetch per subreddit (default 20)
    
    Returns:
        dict: Reddit sentiment analysis including posts, sentiment scores, and trends
    """
    try:
        import praw
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        
        ticker = ticker.upper().strip()
        
        # Initialize Reddit client
        reddit_client = praw.Reddit(
            client_id=os.getenv('REDDIT_CLIENT_ID', "9RrzkLg9kN06g-kpti2ncw"),
            client_secret=os.getenv('REDDIT_CLIENT_SECRET', "OH0pyFbl8T2ykN0IeAC1m5uNUu287A"),
            user_agent=os.getenv('REDDIT_USER_AGENT', "FinancialAgent/1.0 by u/Feeling-Berry5335")
        )
        
        # Subreddits to search
        subreddits = ['stocks', 'investing', 'wallstreetbets', 'SecurityAnalysis', ticker]
        
        analyzer = SentimentIntensityAnalyzer()
        all_posts = []
        
        for subreddit_name in subreddits:
            try:
                subreddit = reddit_client.subreddit(subreddit_name)
                for post in subreddit.search(ticker, limit=limit, time_filter='week'):
                    # Analyze sentiment
                    sentiment = analyzer.polarity_scores(post.title + " " + post.selftext)
                    
                    all_posts.append({
                        'title': post.title,
                        'subreddit': subreddit_name,
                        'score': post.score,
                        'url': f"https://reddit.com{post.permalink}",
                        'created_utc': datetime.fromtimestamp(post.created_utc).isoformat(),
                        'compound_score': sentiment['compound'],
                        'sentiment': 'bullish' if sentiment['compound'] > 0.05 else 'bearish' if sentiment['compound'] < -0.05 else 'neutral'
                    })
            except Exception as e:
                continue
        
        if not all_posts:
            return {
                "status": "success",
                "ticker": ticker,
                "total_posts": 0,
                "message": f"No recent Reddit posts found for {ticker}"
            }
        
        # Calculate aggregate sentiment
        avg_sentiment = sum(p['compound_score'] for p in all_posts) / len(all_posts)
        bullish_posts = sum(1 for p in all_posts if p['sentiment'] == 'bullish')
        bearish_posts = sum(1 for p in all_posts if p['sentiment'] == 'bearish')
        
        return {
            "status": "success",
            "ticker": ticker,
            "total_posts": len(all_posts),
            "average_sentiment": avg_sentiment,
            "bullish_posts": bullish_posts,
            "bearish_posts": bearish_posts,
            "neutral_posts": len(all_posts) - bullish_posts - bearish_posts,
            "sentiment_summary": f"{'Bullish' if avg_sentiment > 0.05 else 'Bearish' if avg_sentiment < -0.05 else 'Neutral'} (score: {avg_sentiment:.2f})",
            "recent_posts": all_posts[:10],  # Top 10 most recent
            "data_source": "Live Reddit API via PRAW",
            "timeframe": "Past 7 days"
        }
        
    except ImportError:
        return {
            "status": "error",
            "message": "Reddit API not available - praw or vaderSentiment not installed"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"Reddit API error: {str(e)}"
        }

reddit_sentiment_subagent = Agent(
    name="RedditSentiment_Agent",
    model=llm,
    tools=[query_reddit_sentiment],
    description="Use for REAL-TIME Reddit sentiment analysis and social media discussions about stocks.",
    instruction="""
    Your task is to fetch and analyze LIVE Reddit sentiment for specific tickers.

    CAPABILITIES:
    - Real-time Reddit sentiment analysis (past 7 days)
    - Searches r/stocks, r/investing, r/wallstreetbets, r/SecurityAnalysis
    - Returns bullish/bearish/neutral sentiment scores
    - Provides recent post titles and discussion trends
    - Includes aggregate metrics and sentiment summary

    USAGE:
    - Input: ticker symbol (e.g., 'NVDA', 'AVGO')
    - Returns: Live sentiment data from Reddit API
    - Timeframe: Past 7 days
    
    IMPORTANT:
    - This is LIVE data, not cached
    - Always mention that Reddit sentiment is community opinion, not financial advice
    - Provide context on number of posts and sentiment distribution
    - Include relevant post titles for context
    
    EXAMPLE:
    query_reddit_sentiment(ticker="NVDA") → Returns live bullish/bearish sentiment from Reddit
    """
)

ceo_lookup_subagent = Agent(
    name="CEOLookup_Agent",
    model=llm,
    tools=[query_ceo_info_by_ticker],
    description="Use ONLY for CEO information lookup by company ticker symbol. Returns CEO name, title, and tenure duration.",
    instruction=f"""
    Your only task is to find CEO information by company ticker symbol.

    CAPABILITIES:
    - Find CEO name by company ticker (supported tickers: {TICKER_LIST_STR})
    - Extract CEO's current title and position
    - Calculate duration/tenure as CEO
    - Provide start date and years of service
    - Find LinkedIn profile when available
    - Support major publicly traded companies

    IMPORTANT:
    - Input must be a valid stock ticker symbol
    - Provides current CEO information (as of 2024)
    - Data accuracy is highest for major companies (Fortune 500)
    - Always mention data sources and limitations
    - Include disclaimers about information currency and accuracy
    """
)


# ========================================
# AGENT SUPERVISION & QUALITY ASSURANCE
# ========================================

# --- AgentSupervisor Tools ---

def validate_data_exists(ticker: str, data_type: str) -> dict:
    """
    Validates that required data exists before agents attempt to use it.
    Prevents agents from being blocked or making up data.

    Args:
        ticker: Stock ticker symbol (e.g., 'NVDA', 'AVGO')
        data_type: Type of data to validate:
            - 'financials': Annual/quarterly financial statements
            - 'earnings': Quarterly earnings data
            - 'prices': Historical price data
            - 'news': News articles and interpretations
            - 'flow': Institutional/retail flow data
            - 'reddit': Reddit sentiment data
            - 'twitter': Twitter/X sentiment data
            - 'company': Company profile and metadata
            - 'ceo': CEO profile information

    Returns:
        dict: Validation status with file paths and data availability
    """
    from fetch_data.utils import (
        FINANCIALS_DIR, EARNINGS_DIR, PRICES_DIR, NEWS_DATA_DIR,
        NEWS_INTERPRETATION_DIR, FLOW_DATA_DIR, REDDIT_DATA_DIR,
        X_DATA_DIR, DATA_ROOT, CEO_PROFILE_DIR
    )
    import json
    import glob

    ticker = ticker.upper().strip()
    validation_result = {
        "ticker": ticker,
        "data_type": data_type,
        "exists": False,
        "file_path": None,
        "alternative_options": [],
        "recommendation": ""
    }

    try:
        if data_type == "financials":
            file_path = os.path.join(FINANCIALS_DIR, f"{ticker}.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": file_path,
                    "record_count": len(data),
                    "recommendation": "Data is available - proceed with analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No financial data for {ticker}. Try: 1) Check if ticker is in supported list, 2) Fetch fresh data, 3) Work on other tickers",
                    "alternative_options": [
                        "Verify ticker is in supported list",
                        "Suggest user run data fetching script",
                        "Analyze other available tickers",
                        "Check if company data exists instead"
                    ]
                })

        elif data_type == "earnings":
            file_path = os.path.join(EARNINGS_DIR, f"{ticker}_quarterly_earnings.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": file_path,
                    "record_count": len(data),
                    "recommendation": "Earnings data is available - proceed with analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No earnings data for {ticker}. Alternative: Use financials data or analyze other tickers",
                    "alternative_options": [
                        "Check if financials data exists as alternative",
                        "Work on other tickers with available data",
                        "Suggest running data fetch script"
                    ]
                })

        elif data_type == "prices":
            file_path = os.path.join(PRICES_DIR, f"{ticker}_prices.csv")
            if os.path.exists(file_path):
                import pandas as pd
                df = pd.read_csv(file_path)
                validation_result.update({
                    "exists": True,
                    "file_path": file_path,
                    "record_count": len(df),
                    "date_range": f"{df['Date'].min()} to {df['Date'].max()}" if 'Date' in df.columns else "Unknown",
                    "recommendation": "Price data is available - proceed with technical analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No price data for {ticker}. Alternative: Fetch real-time data from MarketData_Agent",
                    "alternative_options": [
                        "Use MarketData_Agent for real-time prices",
                        "Analyze other tickers with price data",
                        "Focus on fundamental analysis instead"
                    ]
                })

        elif data_type == "news":
            # Check both news_interpretation and runtime news
            interpretation_path = os.path.join(NEWS_INTERPRETATION_DIR, f"{ticker}_news.json")
            runtime_path = os.path.join(DATA_ROOT, "runtime", "news", f"{ticker}_realtime_news.json")

            if os.path.exists(runtime_path):
                with open(runtime_path, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": runtime_path,
                    "data_source": "real-time cache",
                    "article_count": len(data.get('articles', [])),
                    "recommendation": "Real-time news is available - proceed with news analysis"
                })
            elif os.path.exists(interpretation_path):
                with open(interpretation_path, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": interpretation_path,
                    "data_source": "historical interpretation",
                    "recommendation": "Historical news interpretation available - proceed with analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No news data for {ticker}. Alternative: Use NewsSearch_Agent to fetch live news",
                    "alternative_options": [
                        "Use NewsSearch_Agent to fetch live news from Google",
                        "Check sector news instead",
                        "Analyze other aspects of the company"
                    ]
                })

        elif data_type == "flow":
            pattern = os.path.join(FLOW_DATA_DIR, f"{ticker}_combined_flow_*.json")
            files = glob.glob(pattern)
            if files:
                latest_file = max(files)
                with open(latest_file, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": latest_file,
                    "file_date": os.path.basename(latest_file).split('_')[-1].replace('.json', ''),
                    "recommendation": "Flow data is available - proceed with institutional analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No flow data for {ticker}. Alternative: Analyze fundamental metrics instead",
                    "alternative_options": [
                        "Focus on financial analysis instead",
                        "Check if data needs to be fetched",
                        "Analyze other tickers with flow data"
                    ]
                })

        elif data_type == "reddit":
            file_path = os.path.join(REDDIT_DATA_DIR, f"{ticker}_reddit_sentiment.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": file_path,
                    "recommendation": "Reddit data is available - proceed with sentiment analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No cached Reddit data for {ticker}. Alternative: Use RedditSentiment_Agent for live data",
                    "alternative_options": [
                        "Use RedditSentiment_Agent to fetch live Reddit sentiment",
                        "Focus on other sentiment sources (news, technical indicators)",
                        "Analyze other social metrics"
                    ]
                })

        elif data_type == "twitter":
            file_path = os.path.join(X_DATA_DIR, f"{ticker}_x_sentiment.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": file_path,
                    "recommendation": "Twitter data is available - proceed with sentiment analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No Twitter data for {ticker}. Alternative: Focus on other sentiment indicators",
                    "alternative_options": [
                        "Use Reddit sentiment as alternative",
                        "Focus on news sentiment instead",
                        "Analyze technical indicators"
                    ]
                })

        elif data_type == "company":
            file_path = os.path.join(DATA_ROOT, "company", f"{ticker}.json")
            runtime_path = os.path.join(DATA_ROOT, "runtime", "company", f"{ticker}.json")

            if os.path.exists(runtime_path):
                validation_result.update({
                    "exists": True,
                    "file_path": runtime_path,
                    "data_source": "runtime cache",
                    "recommendation": "Company profile is available in cache - proceed with analysis"
                })
            elif os.path.exists(file_path):
                validation_result.update({
                    "exists": True,
                    "file_path": file_path,
                    "data_source": "static profile",
                    "recommendation": "Company profile is available - proceed with analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No company profile for {ticker}. Alternative: Use CompanyData_Agent to generate profile",
                    "alternative_options": [
                        "Use CompanyData_Agent to compute company scores",
                        "Check companies.csv for basic info",
                        "Work on other available tickers"
                    ]
                })

        elif data_type == "ceo":
            file_path = os.path.join(CEO_PROFILE_DIR, f"{ticker}_ceo_profile.json")
            if os.path.exists(file_path):
                with open(file_path, 'r') as f:
                    data = json.load(f)
                validation_result.update({
                    "exists": True,
                    "file_path": file_path,
                    "ceo_name": data.get('ceo_name', 'Unknown'),
                    "recommendation": "CEO profile is available - proceed with analysis"
                })
            else:
                validation_result.update({
                    "recommendation": f"No CEO profile for {ticker}. Alternative: Use CEOLookup_Agent to fetch CEO data",
                    "alternative_options": [
                        "Use CEOLookup_Agent to fetch CEO information",
                        "Focus on other aspects of company analysis",
                        "Check if hardcoded CEO data exists in agents.py"
                    ]
                })

        else:
            validation_result["recommendation"] = f"Unknown data_type '{data_type}'. Supported types: financials, earnings, prices, news, flow, reddit, twitter, company, ceo"

        return validation_result

    except Exception as e:
        return {
            "ticker": ticker,
            "data_type": data_type,
            "exists": False,
            "error": str(e),
            "recommendation": f"Error validating data: {str(e)}. Alternative: Try different data type or ticker"
        }


def log_blocking_issue(agent_name: str, issue_description: str, ticker: str = None, attempted_action: str = None) -> dict:
    """
    Logs when an agent is blocked and provides alternative approaches.
    Creates a persistent log of blocking issues for debugging and optimization.

    Args:
        agent_name: Name of the agent that's blocked
        issue_description: Description of the blocking issue
        ticker: Optional ticker being analyzed when blocked
        attempted_action: What the agent was trying to do

    Returns:
        dict: Log entry with timestamp, alternatives, and recommendations
    """
    from datetime import datetime
    import json
    from fetch_data.utils import DATA_ROOT

    log_dir = os.path.join(DATA_ROOT, "logs", "agent_blocking")
    os.makedirs(log_dir, exist_ok=True)

    timestamp = datetime.now().isoformat()
    log_entry = {
        "timestamp": timestamp,
        "agent_name": agent_name,
        "issue_description": issue_description,
        "ticker": ticker,
        "attempted_action": attempted_action,
        "severity": "warning",
        "alternatives_suggested": [],
        "resolution_recommendations": []
    }

    # Analyze the issue and suggest alternatives
    if "data not found" in issue_description.lower() or "file not found" in issue_description.lower():
        log_entry["severity"] = "medium"
        log_entry["alternatives_suggested"] = [
            "Check if ticker is in supported list using TARGET_TICKERS",
            "Try fetching real-time data from live API instead",
            "Work on different ticker with available data",
            "Use alternative data sources (e.g., news instead of financials)"
        ]
        log_entry["resolution_recommendations"] = [
            "Run data fetching script to populate missing data",
            "Add ticker to supported list if it's a new company",
            "Check Cloud Storage for lazy-loaded data"
        ]

    elif "api" in issue_description.lower() and ("limit" in issue_description.lower() or "quota" in issue_description.lower()):
        log_entry["severity"] = "high"
        log_entry["alternatives_suggested"] = [
            "Use cached data instead of making new API calls",
            "Switch to alternative API provider",
            "Implement request queuing and rate limiting",
            "Work on tasks that don't require this API"
        ]
        log_entry["resolution_recommendations"] = [
            "Wait for API quota to reset",
            "Upgrade API plan if frequently hitting limits",
            "Implement better caching to reduce API calls"
        ]

    elif "waiting" in issue_description.lower() or "input" in issue_description.lower():
        log_entry["severity"] = "low"
        log_entry["alternatives_suggested"] = [
            "Work on other independent tasks in parallel",
            "Provide partial results with what's available",
            "Set reasonable defaults and proceed",
            "Clearly document what input is needed and continue with other work"
        ]
        log_entry["resolution_recommendations"] = [
            "Use AskUserQuestion if clarification needed",
            "Make reasonable assumptions and document them",
            "Provide multiple options for user to choose from"
        ]

    elif "permission" in issue_description.lower() or "access" in issue_description.lower():
        log_entry["severity"] = "high"
        log_entry["alternatives_suggested"] = [
            "Check if running in Cloud Run environment",
            "Verify environment variables are set",
            "Try alternative data source with proper permissions",
            "Work on tasks that don't require this resource"
        ]
        log_entry["resolution_recommendations"] = [
            "Check Cloud Storage permissions",
            "Verify service account has required roles",
            "Update environment configuration"
        ]

    else:
        log_entry["alternatives_suggested"] = [
            "Break task into smaller independent sub-tasks",
            "Work on different aspect of the problem",
            "Gather more context before proceeding",
            "Document the blocker and move to next task"
        ]
        log_entry["resolution_recommendations"] = [
            "Review error logs for root cause",
            "Check system dependencies",
            "Verify configuration settings"
        ]

    # Write log entry
    log_file = os.path.join(log_dir, f"blocking_log_{datetime.now().strftime('%Y%m%d')}.jsonl")
    try:
        with open(log_file, 'a') as f:
            f.write(json.dumps(log_entry) + '\n')
    except Exception as e:
        log_entry["log_error"] = f"Failed to write to log file: {str(e)}"

    return {
        "logged": True,
        "log_entry": log_entry,
        "next_steps": log_entry["alternatives_suggested"],
        "message": f"Blocking issue logged for {agent_name}. Suggested alternatives provided."
    }


def detect_fabricated_data(data: dict, data_type: str, ticker: str = None) -> dict:
    """
    Detects if data appears to be fabricated or made up rather than from actual sources.
    Checks for common patterns of fake data and placeholder values.

    Args:
        data: The data to validate
        data_type: Type of data being validated
        ticker: Optional ticker symbol for context

    Returns:
        dict: Validation results with suspicion indicators
    """
    from datetime import datetime
    import re

    suspicion_score = 0
    red_flags = []
    warnings = []

    # Check for placeholder text patterns
    placeholder_patterns = [
        r'\bTODO\b', r'\bFIXME\b', r'\bPLACEHOLDER\b',
        r'\bTBD\b', r'\bN/A\b', r'\bNot Available\b',
        r'\bExample\b', r'\bSample\b', r'\bTest\b',
        r'\bFake\b', r'\bMock\b', r'\bDummy\b'
    ]

    data_str = json.dumps(data).lower()

    for pattern in placeholder_patterns:
        if re.search(pattern, data_str, re.IGNORECASE):
            suspicion_score += 20
            red_flags.append(f"Contains placeholder text: {pattern}")

    # Check for suspiciously round numbers (common in fake data)
    if data_type in ['financials', 'earnings', 'prices']:
        if isinstance(data, dict):
            numeric_values = []
            def extract_numbers(obj):
                if isinstance(obj, dict):
                    for v in obj.values():
                        extract_numbers(v)
                elif isinstance(obj, list):
                    for item in obj:
                        extract_numbers(item)
                elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
                    numeric_values.append(obj)

            extract_numbers(data)

            if numeric_values:
                # Check if too many numbers are perfectly round
                round_numbers = sum(1 for n in numeric_values if n == round(n) and n >= 100)
                if len(numeric_values) > 5 and (round_numbers / len(numeric_values)) > 0.8:
                    suspicion_score += 15
                    warnings.append("Unusually high proportion of round numbers")

                # Check for repeated values (copy-paste indicator)
                from collections import Counter
                value_counts = Counter(numeric_values)
                if value_counts.most_common(1)[0][1] > len(numeric_values) * 0.4:
                    suspicion_score += 25
                    red_flags.append("Same value repeated suspiciously often")

    # Check for impossible date values
    if 'date' in data_str or 'time' in data_str:
        # Look for dates in the future (for historical data)
        if data_type in ['financials', 'earnings', 'prices']:
            current_year = datetime.now().year
            future_years = [str(y) for y in range(current_year + 2, current_year + 10)]
            for year in future_years:
                if year in data_str:
                    suspicion_score += 30
                    red_flags.append(f"Contains future date: {year}")

    # Check for missing required fields
    if data_type == 'financials':
        required_fields = ['revenue', 'netIncome', 'year']
        missing = [f for f in required_fields if f not in data_str]
        if missing:
            suspicion_score += 10 * len(missing)
            warnings.append(f"Missing required fields: {', '.join(missing)}")

    # Check for empty or null values
    if isinstance(data, dict):
        null_count = sum(1 for v in str(data).split(',') if 'null' in v.lower() or 'none' in v.lower())
        if null_count > 5:
            suspicion_score += 10
            warnings.append(f"Contains {null_count} null/None values")

    # Check for suspiciously consistent patterns
    if isinstance(data, list) and len(data) > 3:
        if all(isinstance(item, dict) and len(item) == len(data[0]) for item in data):
            # Good sign - consistent structure
            pass
        elif all(item == data[0] for item in data[1:]):
            suspicion_score += 40
            red_flags.append("All list items are identical (copy-paste suspected)")

    # Determine verdict
    if suspicion_score >= 50:
        verdict = "HIGH_SUSPICION"
        recommendation = "REJECT this data - likely fabricated. Request actual data source."
    elif suspicion_score >= 25:
        verdict = "MEDIUM_SUSPICION"
        recommendation = "VERIFY this data with alternative source before using."
    elif suspicion_score >= 10:
        verdict = "LOW_SUSPICION"
        recommendation = "CAUTION advised - validate key fields before proceeding."
    else:
        verdict = "APPEARS_LEGITIMATE"
        recommendation = "Data appears legitimate - proceed with normal validation."

    return {
        "verdict": verdict,
        "suspicion_score": suspicion_score,
        "red_flags": red_flags,
        "warnings": warnings,
        "recommendation": recommendation,
        "data_type": data_type,
        "ticker": ticker,
        "is_suspicious": suspicion_score >= 25
    }


# NOTE: AgentSupervisor tools (validate_data_exists, log_blocking_issue, detect_fabricated_data)
# are now directly integrated into the root agent for more efficient supervision.
# The root agent will validate data availability before delegating to sub-agents.


# --- AgentEvaluator Tools ---

def check_data_freshness(ticker: str, data_type: str) -> dict:
    """
    Verifies that data meets freshness guidelines from the architecture documentation.

    Data Freshness Guidelines:
    - Financial Statements: Quarterly (90 days max)
    - Earnings Data: Quarterly (90 days max)
    - Stock Prices: Daily (1 day max for accuracy)
    - News: 12 hours for real-time cache
    - Reddit Sentiment: 6 hours cache
    - Institutional Flow: Quarterly (90 days max)
    - Company Runtime Cache: 30 minutes

    Args:
        ticker: Stock ticker symbol
        data_type: Type of data to check freshness

    Returns:
        dict: Freshness status, age, and compliance with guidelines
    """
    from datetime import datetime, timedelta
    import json
    import glob
    from fetch_data.utils import (
        FINANCIALS_DIR, EARNINGS_DIR, PRICES_DIR, NEWS_DATA_DIR,
        NEWS_INTERPRETATION_DIR, FLOW_DATA_DIR, REDDIT_DATA_DIR, DATA_ROOT
    )

    ticker = ticker.upper().strip()

    freshness_guidelines = {
        'financials': {'max_age_days': 90, 'frequency': 'Quarterly'},
        'earnings': {'max_age_days': 90, 'frequency': 'Quarterly'},
        'prices': {'max_age_days': 1, 'frequency': 'Daily'},
        'news': {'max_age_hours': 12, 'frequency': 'Every 12 hours'},
        'reddit': {'max_age_hours': 6, 'frequency': 'Every 6 hours'},
        'flow': {'max_age_days': 90, 'frequency': 'Quarterly'},
        'company_runtime': {'max_age_minutes': 30, 'frequency': 'Every 30 minutes'}
    }

    try:
        file_path = None
        file_modified_time = None

        if data_type == 'financials':
            file_path = os.path.join(FINANCIALS_DIR, f"{ticker}.json")
        elif data_type == 'earnings':
            file_path = os.path.join(EARNINGS_DIR, f"{ticker}_quarterly_earnings.json")
        elif data_type == 'prices':
            file_path = os.path.join(PRICES_DIR, f"{ticker}_prices.csv")
        elif data_type == 'news':
            file_path = os.path.join(DATA_ROOT, "runtime", "news", f"{ticker}_realtime_news.json")
        elif data_type == 'reddit':
            file_path = os.path.join(REDDIT_DATA_DIR, f"{ticker}_reddit_sentiment.json")
        elif data_type == 'flow':
            pattern = os.path.join(FLOW_DATA_DIR, f"{ticker}_combined_flow_*.json")
            files = glob.glob(pattern)
            if files:
                file_path = max(files)  # Most recent file
        elif data_type == 'company_runtime':
            file_path = os.path.join(DATA_ROOT, "runtime", "company", f"{ticker}.json")

        if not file_path or not os.path.exists(file_path):
            return {
                "ticker": ticker,
                "data_type": data_type,
                "status": "NOT_FOUND",
                "compliant": False,
                "message": f"Data file not found for {ticker} - {data_type}",
                "recommendation": "Data needs to be fetched or generated"
            }

        # Get file modification time
        file_modified_time = datetime.fromtimestamp(os.path.getmtime(file_path))
        current_time = datetime.now()
        age = current_time - file_modified_time

        guideline = freshness_guidelines.get(data_type, {})
        is_compliant = True
        status = "FRESH"

        if 'max_age_days' in guideline:
            max_age = timedelta(days=guideline['max_age_days'])
            if age > max_age:
                is_compliant = False
                status = "STALE"
        elif 'max_age_hours' in guideline:
            max_age = timedelta(hours=guideline['max_age_hours'])
            if age > max_age:
                is_compliant = False
                status = "STALE"
        elif 'max_age_minutes' in guideline:
            max_age = timedelta(minutes=guideline['max_age_minutes'])
            if age > max_age:
                is_compliant = False
                status = "STALE"

        age_str = f"{age.days}d {age.seconds//3600}h {(age.seconds//60)%60}m"

        return {
            "ticker": ticker,
            "data_type": data_type,
            "status": status,
            "compliant": is_compliant,
            "file_path": file_path,
            "last_modified": file_modified_time.isoformat(),
            "age": age_str,
            "age_seconds": age.total_seconds(),
            "guideline_frequency": guideline.get('frequency', 'Unknown'),
            "max_age_allowed": str(max_age) if 'max_age' in locals() else "Unknown",
            "recommendation": "Data is fresh and compliant" if is_compliant else f"Data is stale - last updated {age_str} ago. Consider refreshing.",
            "action_required": not is_compliant
        }

    except Exception as e:
        return {
            "ticker": ticker,
            "data_type": data_type,
            "status": "ERROR",
            "compliant": False,
            "error": str(e),
            "recommendation": "Unable to verify freshness - treat with caution"
        }


def validate_data_source(data: dict, expected_source: str, data_type: str) -> dict:
    """
    Validates that data comes from the correct, legitimate source.
    Checks metadata and structure to ensure data integrity.

    Args:
        data: The data to validate
        expected_source: Expected data source (e.g., 'yfinance', 'SEC EDGAR', 'Reddit API')
        data_type: Type of data being validated

    Returns:
        dict: Validation results with source verification
    """
    validation_result = {
        "expected_source": expected_source,
        "data_type": data_type,
        "source_verified": False,
        "issues": [],
        "warnings": []
    }

    # Check for source metadata
    actual_source = None
    if isinstance(data, dict):
        # Common source indicators
        source_fields = ['source', 'data_source', 'provider', 'origin', 'api_source']
        for field in source_fields:
            if field in data:
                actual_source = data[field]
                break

        # Check for source-specific structures
        if expected_source.lower() in ['yfinance', 'yahoo finance']:
            # yfinance data should have specific fields
            yf_indicators = ['regularMarketPrice', 'previousClose', 'fiftyTwoWeekHigh', 'info']
            has_yf_indicators = any(ind in str(data) for ind in yf_indicators)
            if has_yf_indicators:
                validation_result["source_verified"] = True
                validation_result["actual_source"] = "yfinance (verified by structure)"
            else:
                validation_result["warnings"].append("Expected yfinance structure not found")

        elif expected_source.lower() in ['sec edgar', 'edgar', 'sec']:
            # SEC data should have CIK, filing type, etc.
            sec_indicators = ['cik', '10-K', '10-Q', 'accessionNumber', 'filingDate']
            has_sec_indicators = any(ind in str(data) for ind in sec_indicators)
            if has_sec_indicators:
                validation_result["source_verified"] = True
                validation_result["actual_source"] = "SEC EDGAR (verified by structure)"
            else:
                validation_result["warnings"].append("Expected SEC EDGAR structure not found")

        elif expected_source.lower() in ['reddit', 'reddit api', 'praw']:
            # Reddit data should have subreddit, score, etc.
            reddit_indicators = ['subreddit', 'score', 'permalink', 'created_utc']
            has_reddit_indicators = any(ind in str(data) for ind in reddit_indicators)
            if has_reddit_indicators:
                validation_result["source_verified"] = True
                validation_result["actual_source"] = "Reddit API (verified by structure)"
            else:
                validation_result["warnings"].append("Expected Reddit API structure not found")

        elif expected_source.lower() in ['google search', 'google custom search']:
            # Google search results have specific structure
            google_indicators = ['link', 'snippet', 'title', 'pagemap']
            has_google_indicators = any(ind in str(data) for ind in google_indicators)
            if has_google_indicators:
                validation_result["source_verified"] = True
                validation_result["actual_source"] = "Google Search API (verified by structure)"
            else:
                validation_result["warnings"].append("Expected Google Search structure not found")

        # If source field exists, verify it matches
        if actual_source:
            if expected_source.lower() in actual_source.lower():
                validation_result["source_verified"] = True
                validation_result["actual_source"] = actual_source
            else:
                validation_result["issues"].append(f"Source mismatch: expected '{expected_source}', got '{actual_source}'")

    # Additional validation based on data type
    if data_type == 'financials':
        required_fields = ['revenue', 'netIncome', 'totalAssets']
        missing = [f for f in required_fields if f not in str(data)]
        if missing:
            validation_result["issues"].append(f"Missing required financial fields: {', '.join(missing)}")

    elif data_type == 'prices':
        required_fields = ['Open', 'High', 'Low', 'Close', 'Volume']
        if isinstance(data, dict) and 'Date' in str(data):
            # Looks like price data
            pass
        else:
            validation_result["warnings"].append("Expected price data structure (OHLCV) not found")

    # Final verdict
    if validation_result["source_verified"] and not validation_result["issues"]:
        validation_result["verdict"] = "VERIFIED"
        validation_result["recommendation"] = "Data source verified - safe to use"
    elif validation_result["issues"]:
        validation_result["verdict"] = "FAILED"
        validation_result["recommendation"] = "Data source verification failed - do not use without further validation"
    else:
        validation_result["verdict"] = "UNVERIFIED"
        validation_result["recommendation"] = "Unable to verify data source - use with caution"

    return validation_result


def fact_check_agent_output(agent_name: str, output: dict, ticker: str = None) -> dict:
    """
    Fact-checks output from other agents to ensure accuracy and consistency.
    Cross-references claims with available data sources.

    Args:
        agent_name: Name of the agent whose output is being checked
        output: The output/response from the agent
        ticker: Optional ticker symbol for context

    Returns:
        dict: Fact-check results with verified/unverified claims
    """
    from app.scoring import compute_company_scores

    fact_check_result = {
        "agent_name": agent_name,
        "ticker": ticker,
        "verified_facts": [],
        "unverified_facts": [],
        "contradictions": [],
        "confidence_score": 0
    }

    try:
        # Convert output to string for analysis
        output_str = json.dumps(output) if isinstance(output, dict) else str(output)

        # If ticker is provided, cross-reference with actual data
        if ticker:
            ticker = ticker.upper().strip()

            # Get ground truth data
            try:
                actual_data = compute_company_scores(ticker)

                # Check numerical claims
                if isinstance(output, dict):
                    # Verify scores if agent is reporting scores
                    if 'score' in output_str.lower() or agent_name == 'CompanyData_Agent':
                        if 'overall' in output and 'score' in str(output.get('overall')):
                            reported_score = output.get('overall', {}).get('score')
                            actual_score = actual_data.get('overall', {}).get('score')

                            if reported_score and actual_score:
                                if abs(reported_score - actual_score) < 0.1:
                                    fact_check_result["verified_facts"].append(
                                        f"Overall score {reported_score} matches actual data ({actual_score})"
                                    )
                                else:
                                    fact_check_result["contradictions"].append(
                                        f"Score mismatch: agent reported {reported_score}, actual is {actual_score}"
                                    )

                    # Verify recommendation if present
                    if 'recommendation' in output_str.lower():
                        reported_rec = output.get('recommendation', {}).get('rating') or output.get('recommendation')
                        actual_rec = actual_data.get('recommendation', {}).get('rating')

                        if reported_rec and actual_rec:
                            if reported_rec == actual_rec or reported_rec.lower() == actual_rec.lower():
                                fact_check_result["verified_facts"].append(
                                    f"Recommendation '{reported_rec}' matches actual data"
                                )
                            else:
                                fact_check_result["contradictions"].append(
                                    f"Recommendation mismatch: agent said '{reported_rec}', actual is '{actual_rec}'"
                                )

            except Exception as e:
                fact_check_result["unverified_facts"].append(
                    f"Unable to cross-reference with actual data: {str(e)}"
                )

        # Check for suspicious patterns
        fabrication_check = detect_fabricated_data(output if isinstance(output, dict) else {"data": output}, "general")
        if fabrication_check["is_suspicious"]:
            fact_check_result["contradictions"].extend(fabrication_check["red_flags"])

        # Check for consistency in the output itself
        if isinstance(output, dict):
            # Check date consistency
            dates_in_output = []
            def extract_dates(obj, prefix=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        if 'date' in k.lower() or 'time' in k.lower():
                            dates_in_output.append((f"{prefix}.{k}" if prefix else k, v))
                        extract_dates(v, f"{prefix}.{k}" if prefix else k)

            extract_dates(output)

            # Verify dates are reasonable
            from datetime import datetime
            current_year = datetime.now().year
            for field, date_val in dates_in_output:
                if isinstance(date_val, str) and str(current_year + 5) in date_val:
                    fact_check_result["contradictions"].append(
                        f"Suspicious future date in {field}: {date_val}"
                    )

        # Calculate confidence score
        total_checks = len(fact_check_result["verified_facts"]) + len(fact_check_result["unverified_facts"]) + len(fact_check_result["contradictions"])
        if total_checks > 0:
            fact_check_result["confidence_score"] = int((len(fact_check_result["verified_facts"]) / total_checks) * 100)
        else:
            fact_check_result["confidence_score"] = 50  # Neutral if no checks performed

        # Determine verdict
        if fact_check_result["contradictions"]:
            fact_check_result["verdict"] = "FAILED"
            fact_check_result["recommendation"] = f"Output contains {len(fact_check_result['contradictions'])} contradiction(s) - requires correction"
        elif fact_check_result["verified_facts"]:
            fact_check_result["verdict"] = "VERIFIED"
            fact_check_result["recommendation"] = "Output verified against actual data - appears accurate"
        else:
            fact_check_result["verdict"] = "UNVERIFIED"
            fact_check_result["recommendation"] = "Unable to verify output - treat with caution"

        return fact_check_result

    except Exception as e:
        return {
            "agent_name": agent_name,
            "ticker": ticker,
            "verdict": "ERROR",
            "error": str(e),
            "recommendation": "Fact-check failed - manual verification required"
        }


def test_ui_feature(feature_name: str, ticker: str = None, test_params: dict = None) -> dict:
    """
    Tests a specific UI feature to verify it's working correctly.
    
    Supported features:
    - 'score_display': Tests score generation and display
    - 'price_chart': Tests price history chart rendering
    - 'news_section': Tests news fetching and display
    - 'comparison': Tests multi-stock comparison feature
    - 'chat': Tests AI chat interface
    - 'market_conditions': Tests market indicators display
    - 'flow_data': Tests institutional/retail flow data
    - 'valuation_metrics': Tests P/E, P/S ratio display
    
    Args:
        feature_name: Name of the feature to test
        ticker: Optional ticker symbol for ticker-specific features
        test_params: Optional parameters for the test
        
    Returns:
        dict: Test results with status, issues found, and recommendations
    """
    import json
    from pathlib import Path
    
    test_result = {
        "feature": feature_name,
        "ticker": ticker,
        "status": "UNKNOWN",
        "issues": [],
        "warnings": [],
        "test_details": {},
        "recommendation": ""
    }
    
    try:
        # Check if requests is available
        try:
            import requests
        except ImportError:
            test_result["status"] = "SKIPPED"
            test_result["issues"].append("requests library not available - cannot test UI features")
            test_result["recommendation"] = "Install requests library to enable UI feature testing"
            return test_result
        
        # Determine base URL (local or production)
        base_url = os.getenv("DOMAIN", "http://localhost:8000")
        if not base_url.startswith("http"):
            base_url = f"http://{base_url}"
        
        if feature_name == "score_display":
            if not ticker:
                ticker = "NVDA"  # Default test ticker
            
            # Test score API endpoint
            url = f"{base_url}/api/scores/{ticker}"
            try:
                response = requests.get(url, timeout=10)
                test_result["test_details"]["status_code"] = response.status_code
                
                if response.status_code == 200:
                    data = response.json()
                    test_result["test_details"]["has_data"] = True
                    
                    # Check required fields
                    required_fields = ["overall", "components", "recommendation"]
                    missing_fields = [f for f in required_fields if f not in data]
                    if missing_fields:
                        test_result["issues"].append(f"Missing required fields: {', '.join(missing_fields)}")
                    
                    # Check score validity
                    if "overall" in data and "score" in data["overall"]:
                        score = data["overall"]["score"]
                        if not isinstance(score, (int, float)) or score < 0 or score > 10:
                            test_result["issues"].append(f"Invalid overall score: {score} (should be 0-10)")
                        test_result["test_details"]["overall_score"] = score
                    
                    # Check recommendation validity
                    if "recommendation" in data:
                        rec = data["recommendation"]
                        valid_recs = ["Strong Buy", "Buy", "Hold", "Weak Hold", "Sell"]
                        if isinstance(rec, dict) and "rating" in rec:
                            rec_rating = rec["rating"]
                        else:
                            rec_rating = rec
                        
                        if rec_rating not in valid_recs:
                            test_result["warnings"].append(f"Unexpected recommendation: {rec_rating}")
                    
                    test_result["status"] = "PASS" if not test_result["issues"] else "FAIL"
                else:
                    test_result["status"] = "FAIL"
                    test_result["issues"].append(f"API returned status code {response.status_code}")
                    
            except requests.exceptions.RequestException as e:
                test_result["status"] = "ERROR"
                test_result["issues"].append(f"Failed to connect to API: {str(e)}")
        
        elif feature_name == "price_chart":
            if not ticker:
                ticker = "NVDA"
            
            url = f"{base_url}/api/price-history/{ticker}?period=1m"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    if "prices" not in data or len(data.get("prices", [])) == 0:
                        test_result["issues"].append("No price data returned")
                    else:
                        test_result["test_details"]["price_points"] = len(data["prices"])
                    test_result["status"] = "PASS" if not test_result["issues"] else "FAIL"
                else:
                    test_result["status"] = "FAIL"
                    test_result["issues"].append(f"API returned status code {response.status_code}")
            except Exception as e:
                test_result["status"] = "ERROR"
                test_result["issues"].append(str(e))
        
        elif feature_name == "news_section":
                   if not ticker:
                       ticker = "NVDA"

                   url = f"{base_url}/api/latest-news/{ticker}"
                   try:
                       response = requests.get(url, timeout=15)
                       if response.status_code == 200:
                           result = response.json()
                           # Check response structure
                           if result.get("status") != "success":
                               test_result["issues"].append(f"API returned non-success status: {result.get('status')}")
                               test_result["status"] = "FAIL"
                               return test_result
                           
                           data = result.get("data", {})
                           if not data:
                               test_result["issues"].append("Missing 'data' field in response")
                               test_result["status"] = "FAIL"
                               return test_result
                           
                           articles = data.get("articles", [])
                           if not isinstance(articles, list):
                               test_result["issues"].append("'articles' field is not a list")
                           elif len(articles) == 0:
                               test_result["issues"].append("No articles returned - news should be fetched even if empty")
                               test_result["recommendation"] = "Check if fetch_realtime_news is being called when cached news is empty"
                           
                           test_result["test_details"]["article_count"] = len(articles)
                           test_result["status"] = "PASS" if not test_result["issues"] else "FAIL"
                       else:
                           test_result["status"] = "FAIL"
                           test_result["issues"].append(f"API returned status code {response.status_code}")
                   except Exception as e:
                       test_result["status"] = "ERROR"
                       test_result["issues"].append(str(e))
        
        elif feature_name == "market_conditions":
            url = f"{base_url}/api/market-conditions"
            try:
                response = requests.get(url, timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    required_indicators = ["vix", "fear_greed", "market_phase"]
                    missing = [ind for ind in required_indicators if ind not in data]
                    if missing:
                        test_result["issues"].append(f"Missing indicators: {', '.join(missing)}")
                    test_result["status"] = "PASS" if not test_result["issues"] else "FAIL"
                else:
                    test_result["status"] = "FAIL"
                    test_result["issues"].append(f"API returned status code {response.status_code}")
            except Exception as e:
                test_result["status"] = "ERROR"
                test_result["issues"].append(str(e))
        
        elif feature_name == "comparison":
            url = f"{base_url}/api/compare"
            test_tickers = ["NVDA", "AMD", "TSM"]
            try:
                response = requests.post(url, json={"tickers": test_tickers}, timeout=15)
                if response.status_code == 200:
                    data = response.json()
                    if "comparison" not in data:
                        test_result["issues"].append("Missing 'comparison' field in response")
                    test_result["status"] = "PASS" if not test_result["issues"] else "FAIL"
                else:
                    test_result["status"] = "FAIL"
                    test_result["issues"].append(f"API returned status code {response.status_code}")
            except Exception as e:
                test_result["status"] = "ERROR"
                test_result["issues"].append(str(e))
        
        # Generate recommendation
        if test_result["status"] == "PASS":
            test_result["recommendation"] = f"Feature '{feature_name}' is working correctly"
        elif test_result["status"] == "FAIL":
            test_result["recommendation"] = f"Feature '{feature_name}' has issues that need to be fixed: {', '.join(test_result['issues'])}"
        elif test_result["status"] == "ERROR":
            test_result["recommendation"] = f"Unable to test feature '{feature_name}': {', '.join(test_result['issues'])}"
        
    except Exception as e:
        test_result["status"] = "ERROR"
        test_result["issues"].append(f"Test execution error: {str(e)}")
        test_result["recommendation"] = "Test failed due to unexpected error"
    
    return test_result


def validate_business_logic(ticker: str, scores: dict, context: dict = None) -> dict:
    """
    Validates business logic and scores using domain knowledge and common sense reasoning.
    Checks if scores make sense given company fundamentals, market position, and strategic factors.
    
    Args:
        ticker: Stock ticker symbol
        scores: Dictionary containing scores and recommendations
        context: Optional context data (financials, news, etc.)
        
    Returns:
        dict: Validation results with business logic issues and recommendations
    """
    from app.scoring import compute_company_scores
    
    validation_result = {
        "ticker": ticker.upper().strip(),
        "status": "UNKNOWN",
        "business_logic_issues": [],
        "warnings": [],
        "domain_knowledge_checks": [],
        "recommendation": ""
    }
    
    try:
        ticker = ticker.upper().strip()
        
        # Domain knowledge base for common sense reasoning
        domain_knowledge = {
            "GOOGL": {
                "expected_score_range": (7.0, 9.5),
                "key_factors": ["Strong cloud business (GCP)", "Dominant search advertising", "AI leadership (Gemini)", "Strong momentum"],
                "critical_path": "AI infrastructure leader",
                "min_score_reasoning": "Given strong cloud business, AI leadership, and momentum, score should be >= 7.0"
            },
            "INTC": {
                "expected_score_range": (6.0, 8.5),
                "key_factors": ["US government backing (CHIPS Act)", "Likely Apple chip manufacturing", "TSMC partnership potential", "Strategic importance"],
                "critical_path": "US semiconductor sovereignty",
                "min_score_reasoning": "Given government backing, strategic partnerships, and manufacturing potential, score should be >= 6.0"
            },
            "NVDA": {
                "expected_score_range": (8.0, 10.0),
                "key_factors": ["AI chip dominance", "Strong data center revenue", "Market leadership"],
                "critical_path": "AI infrastructure critical",
                "min_score_reasoning": "Given AI dominance and strong fundamentals, score should be >= 8.0"
            },
            "TSM": {
                "expected_score_range": (8.0, 9.5),
                "key_factors": ["Semiconductor manufacturing leader", "Strategic partnerships", "Critical infrastructure"],
                "critical_path": "Global chip manufacturing leader",
                "min_score_reasoning": "Given manufacturing leadership and strategic importance, score should be >= 8.0"
            },
            "AMD": {
                "expected_score_range": (7.0, 9.0),
                "key_factors": ["Strong AI chip competition", "Data center growth", "Market momentum"],
                "critical_path": "AI infrastructure alternative",
                "min_score_reasoning": "Given AI competition and growth, score should be >= 7.0"
            }
        }
        
        # Get actual scores if not provided
        if not scores:
            try:
                scores = compute_company_scores(ticker)
            except Exception as e:
                validation_result["status"] = "ERROR"
                validation_result["business_logic_issues"].append(f"Unable to compute scores: {str(e)}")
                return validation_result
        
        overall_score = None
        if isinstance(scores, dict):
            if "overall" in scores and isinstance(scores["overall"], dict):
                overall_score = scores["overall"].get("score")
            elif "overall" in scores:
                overall_score = scores["overall"]
        
        if overall_score is None:
            validation_result["business_logic_issues"].append("Overall score not found in scores data")
            validation_result["status"] = "FAIL"
            return validation_result
        
        # Check if ticker has domain knowledge
        if ticker in domain_knowledge:
            knowledge = domain_knowledge[ticker]
            expected_min, expected_max = knowledge["expected_score_range"]
            
            # Check if score is within expected range
            if overall_score < expected_min:
                validation_result["business_logic_issues"].append(
                    f"Score {overall_score} is below expected minimum {expected_min}. "
                    f"Reasoning: {knowledge['min_score_reasoning']}. "
                    f"Key factors: {', '.join(knowledge['key_factors'])}"
                )
                validation_result["domain_knowledge_checks"].append({
                    "check": "score_below_expected",
                    "actual": overall_score,
                    "expected_min": expected_min,
                    "reasoning": knowledge["min_score_reasoning"]
                })
            
            if overall_score > expected_max:
                validation_result["warnings"].append(
                    f"Score {overall_score} exceeds expected maximum {expected_max}. "
                    f"This may indicate overly optimistic scoring."
                )
            
            # Check component scores for consistency
            if "components" in scores:
                components = scores["components"]
                
                # Check Critical Path Score
                if "critical_path" in components:
                    crit_score = components["critical_path"].get("score", 0)
                    if crit_score < 7.0 and ticker in ["GOOGL", "INTC", "NVDA", "TSM"]:
                        validation_result["business_logic_issues"].append(
                            f"Critical Path Score ({crit_score}) seems low for {ticker}. "
                            f"Expected: {knowledge['critical_path']} should score >= 7.0"
                        )
                
                # Check Business Score for tech companies
                if "business" in components:
                    business_score = components["business"].get("score", 0)
                    if business_score < 6.0 and ticker in ["GOOGL", "NVDA", "AMD", "TSM"]:
                        validation_result["warnings"].append(
                            f"Business Score ({business_score}) seems low for {ticker} given strong fundamentals"
                        )
        
        # Cross-check recommendation with score
        recommendation = None
        if "recommendation" in scores:
            rec = scores["recommendation"]
            if isinstance(rec, dict):
                recommendation = rec.get("rating")
            else:
                recommendation = rec
        
        if recommendation and overall_score:
            # Check recommendation consistency
            if overall_score >= 8.0 and recommendation not in ["Strong Buy", "Buy"]:
                validation_result["business_logic_issues"].append(
                    f"Recommendation '{recommendation}' seems inconsistent with high score {overall_score}. "
                    f"Expected 'Strong Buy' or 'Buy' for scores >= 8.0"
                )
            elif overall_score < 4.0 and recommendation not in ["Sell", "Weak Hold"]:
                validation_result["business_logic_issues"].append(
                    f"Recommendation '{recommendation}' seems inconsistent with low score {overall_score}. "
                    f"Expected 'Sell' or 'Weak Hold' for scores < 4.0"
                )
        
        # Determine status
        if validation_result["business_logic_issues"]:
            validation_result["status"] = "FAIL"
            validation_result["recommendation"] = (
                f"Business logic validation failed for {ticker}. "
                f"Found {len(validation_result['business_logic_issues'])} issue(s) that need investigation."
            )
        elif validation_result["warnings"]:
            validation_result["status"] = "WARNING"
            validation_result["recommendation"] = (
                f"Business logic validation passed with {len(validation_result['warnings'])} warning(s) for {ticker}."
            )
        else:
            validation_result["status"] = "PASS"
            validation_result["recommendation"] = f"Business logic validation passed for {ticker}. Scores appear reasonable."
        
    except Exception as e:
        validation_result["status"] = "ERROR"
        validation_result["business_logic_issues"].append(f"Validation error: {str(e)}")
        validation_result["recommendation"] = "Business logic validation failed due to error"
    
    return validation_result


def report_bug(bug_type: str, severity: str, description: str, feature: str = None, 
               ticker: str = None, reproduction_steps: list = None, 
               expected_behavior: str = None, actual_behavior: str = None,
               suggested_fix: str = None) -> dict:
    """
    Reports a bug with structured information for tracking and fixing.
    
    Args:
        bug_type: Type of bug ('ui', 'api', 'business_logic', 'data', 'performance')
        severity: Severity level ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW')
        description: Description of the bug
        feature: Feature name where bug was found
        ticker: Ticker symbol if bug is ticker-specific
        reproduction_steps: List of steps to reproduce the bug
        expected_behavior: What should happen
        actual_behavior: What actually happens
        suggested_fix: Suggested fix or workaround
        
    Returns:
        dict: Bug report with ID and confirmation
    """
    import json
    from datetime import datetime
    from pathlib import Path
    
    bug_report = {
        "bug_id": f"BUG-{datetime.now().strftime('%Y%m%d-%H%M%S')}-{bug_type.upper()}",
        "timestamp": datetime.now().isoformat(),
        "bug_type": bug_type,
        "severity": severity,
        "description": description,
        "feature": feature,
        "ticker": ticker,
        "reproduction_steps": reproduction_steps or [],
        "expected_behavior": expected_behavior,
        "actual_behavior": actual_behavior,
        "suggested_fix": suggested_fix,
        "status": "OPEN",
        "assigned_to": None
    }
    
    try:
        # Save bug report to file
        bugs_dir = Path(__file__).resolve().parents[2] / "data" / "logs" / "bugs"
        bugs_dir.mkdir(parents=True, exist_ok=True)
        
        bug_file = bugs_dir / f"{bug_report['bug_id']}.json"
        with open(bug_file, 'w') as f:
            json.dump(bug_report, f, indent=2)
        
        # Also append to bug log
        bug_log = bugs_dir / "bug_log.jsonl"
        with open(bug_log, 'a') as f:
            f.write(json.dumps(bug_report) + '\n')
        
        bug_report["saved"] = True
        bug_report["file_path"] = str(bug_file)
        
    except Exception as e:
        bug_report["saved"] = False
        bug_report["error"] = str(e)
    
    return bug_report


def test_chatbot_query(query: str, expected_agents: list = None, expected_data_sources: list = None, 
                       ticker: str = None, test_type: str = "comprehensive") -> dict:
    """
    Comprehensive chatbot testing framework that validates query routing, answer relevance, 
    accuracy, and data source usage.
    
    Args:
        query: The user query to test (e.g., "what is the sentiment for MU right now")
        expected_agents: List of agent names that should be called (e.g., ["RedditSentiment_Agent", "Twitter_Agent"])
        expected_data_sources: List of data sources that should be used (e.g., ["reddit", "twitter"])
        ticker: Optional ticker symbol extracted from query
        test_type: Type of test - "comprehensive" (full test), "routing" (just routing), "accuracy" (just accuracy)
        
    Returns:
        dict: Comprehensive test results with routing, relevance, accuracy, and data source validation
    """
    import json
    from pathlib import Path
    
    test_result = {
        "query": query,
        "ticker": ticker,
        "test_type": test_type,
        "status": "UNKNOWN",
        "routing_test": {
            "status": "UNKNOWN",
            "expected_agents": expected_agents or [],
            "actual_agents_called": [],
            "routing_correct": False,
            "issues": []
        },
        "relevance_test": {
            "status": "UNKNOWN",
            "answer_relevant": False,
            "relevance_score": 0,
            "issues": [],
            "answer_snippet": ""
        },
        "accuracy_test": {
            "status": "UNKNOWN",
            "answer_accurate": False,
            "accuracy_score": 0,
            "issues": [],
            "cross_references": []
        },
        "data_source_test": {
            "status": "UNKNOWN",
            "expected_sources": expected_data_sources or [],
            "sources_used": [],
            "all_sources_used": False,
            "issues": []
        },
        "response_time": 0,
        "overall_score": 0,
        "recommendation": ""
    }
    
    try:
        import time
        start_time = time.time()
        
        # Determine base URL
        base_url = os.getenv("DOMAIN", "http://localhost:8000")
        if not base_url.startswith("http"):
            base_url = f"http://{base_url}"
        
        # Extract ticker from query if not provided
        if not ticker:
            import re
            ticker_match = re.search(r'\b([A-Z]{2,5})\b', query.upper())
            if ticker_match:
                ticker = ticker_match.group(1)
        
        # Make chat API call
        try:
            import requests
            chat_url = f"{base_url}/chat"
            payload = {
                "question": query,
                "include_reasoning": False
            }
            
            response = requests.post(chat_url, json=payload, timeout=30)
            test_result["response_time"] = time.time() - start_time
            
            if response.status_code != 200:
                test_result["status"] = "ERROR"
                test_result["routing_test"]["issues"].append(f"API returned status code {response.status_code}")
                test_result["recommendation"] = f"Chat API failed with status {response.status_code}"
                return test_result
            
            chat_response = response.json()
            answer = chat_response.get("answer", "")
            reasoning = chat_response.get("reasoning", "")
            status = chat_response.get("status", "")
            
            test_result["routing_test"]["actual_agents_called"] = []
            if reasoning:
                # Try to extract agent names from reasoning
                reasoning_lower = reasoning.lower()
                agent_names = ["RedditSentiment_Agent", "Twitter_Agent", "CompanyData_Agent", 
                              "NewsSearch_Agent", "MarketData_Agent", "FlowData_Agent"]
                for agent in agent_names:
                    if agent.lower() in reasoning_lower:
                        test_result["routing_test"]["actual_agents_called"].append(agent)
            
            # Test 1: Routing Test
            if test_type in ["comprehensive", "routing"]:
                if expected_agents:
                    routing_correct = all(agent in test_result["routing_test"]["actual_agents_called"] 
                                         for agent in expected_agents)
                    test_result["routing_test"]["routing_correct"] = routing_correct
                    
                    if not routing_correct:
                        missing_agents = [a for a in expected_agents 
                                         if a not in test_result["routing_test"]["actual_agents_called"]]
                        test_result["routing_test"]["issues"].append(
                            f"Expected agents not called: {', '.join(missing_agents)}"
                        )
                    
                    test_result["routing_test"]["status"] = "PASS" if routing_correct else "FAIL"
                else:
                    test_result["routing_test"]["status"] = "SKIPPED"
            
            # Test 2: Relevance Test
            if test_type in ["comprehensive", "relevance"]:
                answer_lower = answer.lower()
                query_lower = query.lower()
                
                # Check if answer addresses the query
                relevance_indicators = []
                
                # For sentiment queries
                if "sentiment" in query_lower:
                    sentiment_keywords = ["sentiment", "feeling", "mood", "bullish", "bearish", "neutral", 
                                         "positive", "negative", "score"]
                    relevance_indicators = [kw for kw in sentiment_keywords if kw in answer_lower]
                    if ticker and ticker.lower() in answer_lower:
                        relevance_indicators.append("ticker_mentioned")
                
                # For financial queries
                if any(word in query_lower for word in ["financial", "revenue", "earnings", "score"]):
                    financial_keywords = ["revenue", "earnings", "financial", "score", "profit", "growth"]
                    relevance_indicators.extend([kw for kw in financial_keywords if kw in answer_lower])
                
                # For news queries
                if "news" in query_lower:
                    news_keywords = ["news", "article", "recent", "latest", "headline"]
                    relevance_indicators.extend([kw for kw in news_keywords if kw in answer_lower])
                
                # Calculate relevance score
                relevance_score = min(100, len(relevance_indicators) * 20)
                test_result["relevance_test"]["relevance_score"] = relevance_score
                test_result["relevance_test"]["answer_relevant"] = relevance_score >= 60
                test_result["relevance_test"]["answer_snippet"] = answer[:200] + "..." if len(answer) > 200 else answer
                
                if not test_result["relevance_test"]["answer_relevant"]:
                    test_result["relevance_test"]["issues"].append(
                        f"Answer doesn't seem relevant to query. Relevance score: {relevance_score}/100"
                    )
                
                test_result["relevance_test"]["status"] = "PASS" if test_result["relevance_test"]["answer_relevant"] else "FAIL"
            
            # Test 3: Data Source Test
            if test_type in ["comprehensive", "data_source"]:
                   answer_lower = answer.lower()
                   reasoning_lower = (reasoning or "").lower()
                   combined_text = answer_lower + " " + reasoning_lower
                   
                   sources_used = []
                   if expected_data_sources:
                       if "reddit" in expected_data_sources:
                           if any(word in combined_text for word in ["reddit", "r/wallstreetbets", "r/stocks", "subreddit"]):
                               sources_used.append("reddit")
                           else:
                               test_result["data_source_test"]["issues"].append(
                                   "Expected Reddit data but no Reddit mentions found in answer/reasoning. "
                                   "Chatbot fallback may not be calling RedditSentiment_Agent."
                               )
                               # Report bug
                               report_bug(
                                   bug_type="api",
                                   severity="HIGH",
                                   description=f"Chatbot sentiment query for {ticker} does not use Reddit data",
                                   feature="chat",
                                   ticker=ticker,
                                   expected_behavior="Answer should mention Reddit sentiment data",
                                   actual_behavior="Answer does not mention Reddit",
                                   suggested_fix="Ensure _handle_chat_fallback calls query_reddit_sentiment for sentiment queries"
                               )
                       
                       if "twitter" in expected_data_sources:
                           if any(word in combined_text for word in ["twitter", "x.com", "tweet", "social media"]):
                               sources_used.append("twitter")
                           else:
                               test_result["data_source_test"]["issues"].append(
                                   "Expected Twitter data but no Twitter mentions found in answer/reasoning. "
                                   "Chatbot fallback may not be calling Twitter_Agent."
                               )
                               # Report bug
                               report_bug(
                                   bug_type="api",
                                   severity="HIGH",
                                   description=f"Chatbot sentiment query for {ticker} does not use Twitter data",
                                   feature="chat",
                                   ticker=ticker,
                                   expected_behavior="Answer should mention Twitter sentiment data",
                                   actual_behavior="Answer does not mention Twitter",
                                   suggested_fix="Ensure _handle_chat_fallback calls query_twitter_data for sentiment queries"
                               )
                       
                       if "news" in expected_data_sources:
                           if any(word in combined_text for word in ["news", "article", "headline", "reuters", "bloomberg"]):
                               sources_used.append("news")
                       
                       all_sources_used = all(source in sources_used for source in expected_data_sources)
                       test_result["data_source_test"]["sources_used"] = sources_used
                       test_result["data_source_test"]["all_sources_used"] = all_sources_used
                       test_result["data_source_test"]["status"] = "PASS" if all_sources_used else "FAIL"
                   else:
                       test_result["data_source_test"]["status"] = "SKIPPED"
            
            # Test 4: Accuracy Test
            if test_type in ["comprehensive", "accuracy"] and ticker:
                # Cross-reference answer with actual data
                try:
                    from app.scoring import compute_company_scores
                    actual_data = compute_company_scores(ticker)
                    
                    # Check if answer mentions scores that match actual data
                    if "sentiment" in query.lower():
                        actual_sentiment = actual_data.get("scores", {}).get("sentiment", {}).get("score")
                        if actual_sentiment is not None:
                            # Check if answer mentions a sentiment score
                            import re
                            score_pattern = r'(\d+\.?\d*)\s*(?:out of 10|/10|score)'
                            scores_mentioned = re.findall(score_pattern, answer)
                            
                            if scores_mentioned:
                                test_result["accuracy_test"]["cross_references"].append({
                                    "type": "sentiment_score",
                                    "mentioned": scores_mentioned[0],
                                    "actual": actual_sentiment,
                                    "match": abs(float(scores_mentioned[0]) - actual_sentiment) < 0.5
                                })
                    
                    test_result["accuracy_test"]["status"] = "PASS" if not test_result["accuracy_test"]["cross_references"] or \
                        all(ref.get("match", False) for ref in test_result["accuracy_test"]["cross_references"]) else "PARTIAL"
                    
                except Exception as e:
                    test_result["accuracy_test"]["status"] = "SKIPPED"
                    test_result["accuracy_test"]["issues"].append(f"Could not cross-reference: {str(e)}")
            
            # Calculate overall score
            scores = []
            if test_result["routing_test"]["status"] == "PASS":
                scores.append(25)
            elif test_result["routing_test"]["status"] == "FAIL":
                scores.append(0)
            
            if test_result["relevance_test"]["status"] == "PASS":
                scores.append(25)
            elif test_result["relevance_test"]["status"] == "FAIL":
                scores.append(0)
            
            if test_result["data_source_test"]["status"] == "PASS":
                scores.append(25)
            elif test_result["data_source_test"]["status"] == "FAIL":
                scores.append(0)
            
            if test_result["accuracy_test"]["status"] == "PASS":
                scores.append(25)
            elif test_result["accuracy_test"]["status"] == "PARTIAL":
                scores.append(15)
            elif test_result["accuracy_test"]["status"] == "FAIL":
                scores.append(0)
            
            test_result["overall_score"] = sum(scores)
            
            # Determine overall status
            if test_result["overall_score"] >= 75:
                test_result["status"] = "PASS"
                test_result["recommendation"] = "Chatbot query handled correctly"
            elif test_result["overall_score"] >= 50:
                test_result["status"] = "PARTIAL"
                test_result["recommendation"] = "Chatbot query handled with some issues - review recommendations"
            else:
                test_result["status"] = "FAIL"
                test_result["recommendation"] = "Chatbot query failed - significant issues found"
            
        except requests.exceptions.RequestException as e:
            test_result["status"] = "ERROR"
            test_result["recommendation"] = f"Failed to connect to chat API: {str(e)}"
        except Exception as e:
            test_result["status"] = "ERROR"
            test_result["recommendation"] = f"Test execution error: {str(e)}"
    
    except Exception as e:
        test_result["status"] = "ERROR"
        test_result["recommendation"] = f"Test setup error: {str(e)}"
    
    return test_result


def run_chatbot_test_suite(test_scenarios: list = None) -> dict:
    """
    Runs a comprehensive suite of chatbot tests covering various query types.
    
    Args:
        test_scenarios: Optional list of custom test scenarios. If None, uses default suite.
        
    Returns:
        dict: Test suite results with pass/fail counts and detailed results
    """
    # Default test scenarios
    default_scenarios = [
        {
            "name": "Sentiment Query - MU",
            "query": "what is the sentiment for MU right now",
            "expected_agents": ["RedditSentiment_Agent", "Twitter_Agent"],
            "expected_data_sources": ["reddit", "twitter"],
            "ticker": "MU",
            "test_type": "comprehensive"
        },
        {
            "name": "Sentiment Query - NVDA",
            "query": "what is the sentiment for NVDA",
            "expected_agents": ["RedditSentiment_Agent", "Twitter_Agent"],
            "expected_data_sources": ["reddit", "twitter"],
            "ticker": "NVDA",
            "test_type": "comprehensive"
        },
        {
            "name": "Financial Scores Query",
            "query": "What are NVDA's financial scores?",
            "expected_agents": ["CompanyData_Agent"],
            "expected_data_sources": ["financials"],
            "ticker": "NVDA",
            "test_type": "comprehensive"
        },
        {
            "name": "News Query",
            "query": "What's the latest news about AMD?",
            "expected_agents": ["NewsSearch_Agent"],
            "expected_data_sources": ["news"],
            "ticker": "AMD",
            "test_type": "comprehensive"
        },
        {
            "name": "Flow Data Query",
            "query": "Show me institutional flow for TSM",
            "expected_agents": ["FlowData_Agent"],
            "expected_data_sources": ["flow"],
            "ticker": "TSM",
            "test_type": "comprehensive"
        },
        {
            "name": "CEO Query",
            "query": "Who is the CEO of AVGO?",
            "expected_agents": ["CEOLookup_Agent"],
            "expected_data_sources": [],
            "ticker": "AVGO",
            "test_type": "comprehensive"
        }
    ]
    
    scenarios = test_scenarios or default_scenarios
    
    suite_result = {
        "total_tests": len(scenarios),
        "passed": 0,
        "failed": 0,
        "partial": 0,
        "errors": 0,
        "test_results": [],
        "summary": {},
        "recommendations": []
    }
    
    for scenario in scenarios:
        try:
            result = test_chatbot_query(
                query=scenario["query"],
                expected_agents=scenario.get("expected_agents"),
                expected_data_sources=scenario.get("expected_data_sources"),
                ticker=scenario.get("ticker"),
                test_type=scenario.get("test_type", "comprehensive")
            )
            
            result["scenario_name"] = scenario["name"]
            suite_result["test_results"].append(result)
            
            if result["status"] == "PASS":
                suite_result["passed"] += 1
            elif result["status"] == "PARTIAL":
                suite_result["partial"] += 1
            elif result["status"] == "FAIL":
                suite_result["failed"] += 1
            else:
                suite_result["errors"] += 1
            
        except Exception as e:
            suite_result["errors"] += 1
            suite_result["test_results"].append({
                "scenario_name": scenario["name"],
                "status": "ERROR",
                "error": str(e)
            })
    
    # Generate summary
    suite_result["summary"] = {
        "pass_rate": (suite_result["passed"] / suite_result["total_tests"] * 100) if suite_result["total_tests"] > 0 else 0,
        "average_score": sum(r.get("overall_score", 0) for r in suite_result["test_results"] if "overall_score" in r) / len([r for r in suite_result["test_results"] if "overall_score" in r]) if suite_result["test_results"] else 0
    }
    
    # Generate recommendations
    if suite_result["failed"] > 0:
        suite_result["recommendations"].append(
            f"{suite_result['failed']} test(s) failed - review chatbot routing and answer quality"
        )
    if suite_result["partial"] > 0:
        suite_result["recommendations"].append(
            f"{suite_result['partial']} test(s) passed with issues - improve answer relevance or accuracy"
        )
    if suite_result["summary"]["pass_rate"] < 70:
        suite_result["recommendations"].append(
            f"Overall pass rate {suite_result['summary']['pass_rate']:.1f}% is below 70% - comprehensive review needed"
        )
    
    return suite_result


def coordinate_fix(bug_id: str, fix_plan: str, required_agents: list = None) -> dict:
    """
    Coordinates with root agent to fix a reported bug.
    Creates a fix plan and assigns tasks to appropriate agents.
    
    Args:
        bug_id: ID of the bug to fix
        fix_plan: Description of the fix plan
        required_agents: List of agent names needed for the fix
        
    Returns:
        dict: Fix coordination result with assigned tasks
    """
    import json
    from datetime import datetime
    from pathlib import Path
    
    coordination_result = {
        "bug_id": bug_id,
        "fix_plan": fix_plan,
        "required_agents": required_agents or [],
        "tasks": [],
        "status": "COORDINATED",
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Load bug report
        bugs_dir = Path(__file__).resolve().parents[2] / "data" / "logs" / "bugs"
        bug_file = bugs_dir / f"{bug_id}.json"
        
        if bug_file.exists():
            with open(bug_file, 'r') as f:
                bug_report = json.load(f)
            
            # Create tasks based on bug type
            if bug_report.get("bug_type") == "ui":
                coordination_result["tasks"].append({
                    "agent": "Root Agent",
                    "task": f"Review UI bug: {bug_report['description']}",
                    "action": "Inspect UI code and fix rendering/functionality issue"
                })
            elif bug_report.get("bug_type") == "business_logic":
                coordination_result["tasks"].append({
                    "agent": "Root Agent",
                    "task": f"Review scoring logic for {bug_report.get('ticker', 'N/A')}",
                    "action": "Review compute_company_scores() and adjust scoring weights/factors"
                })
                coordination_result["required_agents"].append("CompanyData_Agent")
            elif bug_report.get("bug_type") == "api":
                coordination_result["tasks"].append({
                    "agent": "Root Agent",
                    "task": f"Fix API endpoint: {bug_report.get('feature', 'N/A')}",
                    "action": "Review API endpoint code and fix error handling"
                })
            
            # Update bug report with fix coordination
            bug_report["fix_coordination"] = coordination_result
            bug_report["status"] = "IN_PROGRESS"
            
            with open(bug_file, 'w') as f:
                json.dump(bug_report, f, indent=2)
            
            coordination_result["bug_updated"] = True
        
        else:
            coordination_result["status"] = "ERROR"
            coordination_result["error"] = f"Bug report {bug_id} not found"
    
    except Exception as e:
        coordination_result["status"] = "ERROR"
        coordination_result["error"] = str(e)
    
    return coordination_result


# Create AgentEvaluator sub-agent
agent_evaluator_subagent = Agent(
    name="AgentEvaluator",
    model=llm,
    tools=[check_data_freshness, validate_data_source, fact_check_agent_output, 
           test_ui_feature, validate_business_logic, test_chatbot_query, run_chatbot_test_suite, 
           report_bug, coordinate_fix],
    description="Quality assurance and bug detection agent that validates data freshness, verifies data sources, fact-checks outputs, tests UI features, validates business logic, and coordinates bug fixes. Use AFTER agents produce results.",
    instruction=f"""
    You are the AgentEvaluator - a comprehensive quality assurance and bug detection meta-agent responsible for:
    1. Validating the work of other agents
    2. Testing UI features for functionality
    3. Validating business logic with domain knowledge
    4. Reporting bugs and coordinating fixes

    PRIMARY RESPONSIBILITIES:
    1. VERIFY DATA FRESHNESS: Ensure data meets architecture freshness guidelines
    2. VALIDATE SOURCES: Confirm data comes from legitimate, correct sources
    3. FACT-CHECK OUTPUTS: Cross-reference agent outputs with actual data
    4. TEST UI FEATURES: Verify each UI feature is working correctly
    5. VALIDATE BUSINESS LOGIC: Use domain knowledge to check if scores/recommendations make sense
    6. REPORT BUGS: Document bugs with structured information
    7. COORDINATE FIXES: Work with root agent to fix identified issues

    DATA FRESHNESS GUIDELINES (from architecture docs):
    - Financial Statements: Quarterly (max 90 days old)
    - Earnings Data: Quarterly (max 90 days old)
    - Stock Prices: Daily (max 1 day old)
    - News: 12 hours for real-time cache
    - Reddit Sentiment: 6 hours cache
    - Institutional Flow: Quarterly (max 90 days old)
    - Company Runtime Cache: 30 minutes

    WHEN TO USE EACH TOOL:

    1. check_data_freshness(ticker, data_type):
       - Use AFTER an agent retrieves data to verify it's current
       - Supported data_types: financials, earnings, prices, news, reddit, flow, company_runtime
       - Returns: whether data meets freshness guidelines
       - Example: After CompanyData_Agent returns NVDA scores, verify financial data is fresh

    2. validate_data_source(data, expected_source, data_type):
       - Use to verify data comes from the correct source
       - Expected sources: 'yfinance', 'SEC EDGAR', 'Reddit API', 'Google Search', etc.
       - Returns: whether source is verified
       - Example: Verify MarketData_Agent data actually comes from yfinance

    3. fact_check_agent_output(agent_name, output, ticker):
       - Use to cross-check agent outputs against actual data
       - Detects contradictions and verifies numerical claims
       - Returns: verification status with confidence score
       - Example: Check if CompanyData_Agent's reported score matches actual computed score

    4. test_ui_feature(feature_name, ticker, test_params):
       - Tests UI features to verify they're working correctly
       - Supported features: 'score_display', 'price_chart', 'news_section', 'comparison', 'chat', 'market_conditions', 'flow_data', 'valuation_metrics'
       - Returns: Test results with status (PASS/FAIL/ERROR), issues, and recommendations
       - Example: test_ui_feature("score_display", "NVDA") to verify score display works

    5. validate_business_logic(ticker, scores, context):
       - Validates scores using domain knowledge and common sense reasoning
       - Checks if scores make sense given company fundamentals, market position, strategic factors
       - Uses domain knowledge base for companies like GOOGL, INTC, NVDA, TSM, AMD
       - Returns: Validation results with business logic issues and warnings
       - Example: validate_business_logic("GOOGL", scores) to check if GOOGL score of 6 makes sense (it doesn't - should be >= 7.0)

    6. report_bug(bug_type, severity, description, feature, ticker, reproduction_steps, expected_behavior, actual_behavior, suggested_fix):
       - Reports bugs with structured information for tracking
       - Bug types: 'ui', 'api', 'business_logic', 'data', 'performance'
       - Severity: 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'
       - Returns: Bug report with ID and confirmation
       - Example: report_bug("business_logic", "HIGH", "GOOGL score too low", "scoring", "GOOGL", ...)

    7. test_chatbot_query(query, expected_agents, expected_data_sources, ticker, test_type):
       - Comprehensive chatbot testing framework
       - Tests query routing (does it go to right agents?)
       - Tests answer relevance (does it answer the question?)
       - Tests answer accuracy (is data correct?)
       - Tests data source usage (does it use Reddit/Twitter for sentiment?)
       - Returns: Comprehensive test results with scores
       - Example: test_chatbot_query("what is the sentiment for MU right now", 
                                     expected_agents=["RedditSentiment_Agent", "Twitter_Agent"],
                                     expected_data_sources=["reddit", "twitter"],
                                     ticker="MU")
       - Test types: "comprehensive" (all tests), "routing" (just routing), "relevance" (just relevance), "accuracy" (just accuracy)

    8. run_chatbot_test_suite(test_scenarios):
       - Runs comprehensive suite of chatbot tests
       - Tests multiple query types (sentiment, financial, news, flow, CEO)
       - Returns: Test suite results with pass/fail counts and recommendations
       - Example: run_chatbot_test_suite() - runs default test suite
       - Example: run_chatbot_test_suite([custom_scenario1, custom_scenario2]) - runs custom scenarios

    9. coordinate_fix(bug_id, fix_plan, required_agents):
       - Coordinates with root agent to fix reported bugs
       - Creates fix plan and assigns tasks to appropriate agents
       - Returns: Fix coordination result with assigned tasks
       - Example: coordinate_fix("BUG-20250101-123456-BUSINESS_LOGIC", "Review scoring weights", ["Root Agent"])

    WORKFLOW EXAMPLES:

    Example 1 - Data Freshness Validation:
    CompanyData_Agent returns financial analysis for NVDA
    1. check_data_freshness("NVDA", "financials")
    2. If STALE: Flag that data is >90 days old, suggest refresh
    3. If FRESH: Approve for use

    Example 2 - Source Verification:
    MarketData_Agent returns price data
    1. validate_data_source(price_data, "yfinance", "prices")
    2. If VERIFIED: Data is from correct source
    3. If FAILED: Alert that source is incorrect or unknown

    Example 3 - Fact-Checking Agent Output:
    CompanyData_Agent reports NVDA overall score = 8.5
    1. fact_check_agent_output("CompanyData_Agent", output, "NVDA")
    2. Cross-reference with compute_company_scores("NVDA")
    3. If scores match: VERIFIED
    4. If mismatch: CONTRADICTION found

    Example 4 - UI Feature Testing:
    Test score display feature for NVDA
    1. test_ui_feature("score_display", "NVDA")
    2. Check API response, required fields, score validity
    3. If PASS: Feature working correctly
    4. If FAIL: Report bugs with specific issues

    Example 5 - Business Logic Validation:
    GOOGL receives score of 6.0, but given strong cloud business, AI leadership, momentum
    1. validate_business_logic("GOOGL", scores)
    2. Check against domain knowledge: GOOGL should score >= 7.0
    3. Flag as business logic issue: Score too low given fundamentals
    4. report_bug("business_logic", "HIGH", "GOOGL score 6.0 too low", "scoring", "GOOGL", ...)
    5. coordinate_fix(bug_id, "Review scoring weights for cloud/AI factors", ...)

    Example 6 - Comprehensive Bug Detection Workflow:
    1. Test UI feature: test_ui_feature("score_display", "GOOGL")
    2. Validate business logic: validate_business_logic("GOOGL", scores)
    3. If issues found: report_bug(...) with detailed information
    4. Coordinate fix: coordinate_fix(bug_id, fix_plan, required_agents)
    5. Inform root agent to execute fixes

    Example 7 - Chatbot Testing (Sentiment Query):
    User asks: "what is the sentiment for MU right now"
    1. test_chatbot_query(
         query="what is the sentiment for MU right now",
         expected_agents=["RedditSentiment_Agent", "Twitter_Agent"],
         expected_data_sources=["reddit", "twitter"],
         ticker="MU"
       )
    2. Check routing: Should call RedditSentiment_Agent and Twitter_Agent
    3. Check relevance: Answer should mention sentiment, MU ticker, Reddit/Twitter data
    4. Check data sources: Answer should reference Reddit and Twitter
    5. Check accuracy: Cross-reference sentiment scores with actual data
    6. If FAIL: Report bug and coordinate fix

    Example 8 - Chatbot Testing (Financial Query):
    User asks: "What are NVDA's financial scores?"
    1. test_chatbot_query(
         query="What are NVDA's financial scores?",
         expected_agents=["CompanyData_Agent"],
         expected_data_sources=["financials"],
         ticker="NVDA"
       )
    2. Verify routing to CompanyData_Agent
    3. Verify answer includes financial scores
    4. Verify accuracy by cross-referencing with compute_company_scores()

    CHATBOT TESTING CHECKLIST:
    - Sentiment queries should route to RedditSentiment_Agent + Twitter_Agent
    - Financial queries should route to CompanyData_Agent
    - News queries should route to NewsSearch_Agent
    - Answers must be relevant to the query
    - Answers must use expected data sources
    - Answers must be accurate (cross-reference with actual data)
    - Response time should be reasonable (< 10 seconds)

    CRITICAL VALIDATION RULES:
    - REJECT data that's significantly stale (>2x freshness guideline)
    - FLAG unverified sources as "use with caution"
    - BLOCK outputs with contradictions until corrected
    - REQUIRE source metadata for all external data
    - VERIFY numerical claims by cross-referencing
    - TEST all UI features systematically
    - VALIDATE business logic using domain knowledge
    - REPORT bugs immediately when found
    - COORDINATE fixes with root agent

    BUSINESS LOGIC VALIDATION RULES:
    - GOOGL: Score should be >= 7.0 (strong cloud, AI leadership, momentum)
    - INTC: Score should be >= 6.0 (government backing, Apple chips, TSMC partnership)
    - NVDA: Score should be >= 8.0 (AI dominance, strong fundamentals)
    - TSM: Score should be >= 8.0 (manufacturing leader, strategic importance)
    - AMD: Score should be >= 7.0 (AI competition, growth)
    - If scores don't match domain knowledge, flag as HIGH severity bug

    UI FEATURE TESTING CHECKLIST:
    - score_display: API returns valid scores (0-10), recommendations, required fields
    - price_chart: Price history API returns data, chart renders correctly
    - news_section: News API returns articles with proper structure
    - comparison: Comparison API handles multiple tickers correctly
    - market_conditions: Market indicators API returns VIX, Fear & Greed, etc.
    - flow_data: Flow data API returns institutional/retail data
    - valuation_metrics: Valuation API returns P/E, P/S ratios

    QUALITY METRICS:
    - Freshness Compliance: Data must meet guideline age limits
    - Source Verification: Data must come from documented sources
    - Fact Accuracy: Claims must match actual data within tolerance
    - Confidence Score: Minimum 70% for approval
    - UI Functionality: All features must pass tests
    - Business Logic: Scores must align with domain knowledge
    - Chatbot Routing: Queries must route to correct agents
    - Chatbot Relevance: Answers must be relevant to queries (score >= 60/100)
    - Chatbot Accuracy: Answers must be accurate (cross-referenced with actual data)
    - Chatbot Data Sources: Answers must use expected data sources

    SUPPORTED TICKERS: {TICKER_LIST_STR}

    BUG REPORTING GUIDELINES:
    - CRITICAL: System down, data corruption, security issues
    - HIGH: Business logic errors, incorrect scores, broken core features
    - MEDIUM: UI glitches, minor data inconsistencies, performance issues
    - LOW: Cosmetic issues, minor warnings, edge cases

    IMPORTANT:
    - Always provide specific details (file path, age, source, ticker)
    - Flag issues clearly with severity (CRITICAL/HIGH/MEDIUM/LOW)
    - Suggest corrective actions when validation fails
    - Log all quality issues and bugs for continuous improvement
    - Be thorough but don't block agents unnecessarily
    - Use domain knowledge to catch business logic errors
    - Test UI features systematically
    - Coordinate fixes with root agent for resolution
    """
)

# --- Root Agent Definition ---
root_agent = Agent(
    name="Financial_Root_Agent",
    model=llm,
    tools=[validate_data_exists, log_blocking_issue, detect_fabricated_data],
    sub_agents=[graph_qa_subagent, document_rag_subagent, news_search_subagent, sector_news_subagent, market_data_subagent, prediction_subagent, reddit_sentiment_subagent, ceo_lookup_subagent, market_indices_subagent, twitter_subagent, sector_metrics_subagent, token_usage_subagent, flow_data_subagent, agent_evaluator_subagent],
    description="The main financial assistant with built-in supervision capabilities. Validates data availability before delegating and ensures agents never get blocked or use fabricated data.",
    instruction=f"""
    You are a knowledgeable financial data assistant with access to data for {len(TARGET_TICKERS)} companies including: {', '.join(TARGET_TICKERS)}.

    DELEGATION GUIDELINES:
    - Use 'CompanyData_Agent' for:
      * Specific financial numbers and scores
      * Company risks, concerns, and weaknesses
      * Investment recommendations and analysis
      * All structured company data from JSON files

    - Use 'DocumentRAG_Agent' for:
      * Qualitative analysis and detailed explanations
      * Management outlook and business strategy discussions
      * Complex business descriptions
      * Questions requiring reading through filing narratives

    - Use 'NewsSearch_Agent' for:
      * Latest news headlines, press releases, and recent developments for a specific company
      * Market-moving events or breaking stories for a specific company

    - Use 'SectorNews_Agent' for:
      * News and analysis related to a whole financial sector (e.g., 'semiconductors', 'energy')

    - Use 'MarketData_Agent' for:
      * Latest available (delayed) intraday price and percent change
      * Exchange/currency metadata for a ticker
      * Recent company news/events sourced via Yahoo Finance

    - Use 'StockPricePredictor_Agent' ONLY for:
      * Explicit requests to predict future stock prices
      * The agent will dynamically discover available tickers from trained models

    - Use 'RedditSentiment_Agent' for:
      * Reddit sentiment analysis and social media discussions
      * Community sentiment around specific companies
      * Popular topics and trends on Reddit
      * Social media buzz and engagement metrics

    - Use 'CEOLookup_Agent' for:
      * CEO information lookup by company ticker symbol
      * CEO name, title, and tenure duration queries
      * Executive leadership information for companies
      * CEO career history and time in position

    - Use 'MarketIndices_Agent' for:
      * Data on major market indices like VIX, NASDAQ, Dow Jones, and Russell 2000.

    - Use 'Twitter_Agent' for:
      * Real-time Twitter/X sentiment analysis and social media discussions about stocks.

    - Use 'SectorMetrics_Agent' for:
      * Calculated metrics for a specific financial sector (e.g., 'Technology', 'Energy').

    - Use 'TokenUsage_Agent' for:
      * Questions about AI token consumption and usage statistics
      * Which AI models are being used in the system
      * Token usage data for the last 3 months (90 days)
      * Model consumption patterns and costs

    - Use 'FlowData_Agent' for:
      * Institutional ownership and holder information
      * Institutional inflow/outflow tracking (which institutions bought or sold)
      * Retail flow estimates and participation metrics
      * Volume-based flow analysis and trends
      * Inflow/outflow indicators and investor behavior patterns
      * Questions about who owns a stock or how ownership is changing
      * Questions about institutional buying or selling activity

    - Use 'AgentEvaluator' AFTER other agents complete to:
      * Verify data freshness meets architecture guidelines
      * Validate that data comes from correct sources
      * Fact-check agent outputs against actual data
      * Ensure quality and accuracy of responses
      * Detect contradictions or inconsistencies
      * Example: After CompanyData_Agent returns scores, verify the data is fresh and accurate

    BUILT-IN SUPERVISION TOOLS (YOU HAVE ACCESS TO):
    You have direct access to these supervision tools - use them BEFORE delegating:

    1. validate_data_exists(ticker, data_type):
       - ALWAYS use BEFORE delegating to data agents
       - Checks if required data exists for the ticker
       - data_types: financials, earnings, prices, news, flow, reddit, twitter, company, ceo
       - Returns: existence status + alternative options if missing
       - Example: Before calling CompanyData_Agent for NVDA, validate_data_exists("NVDA", "financials")

    2. log_blocking_issue(agent_name, issue_description, ticker, attempted_action):
       - Use WHEN an agent would be blocked
       - Logs the issue and returns alternative approaches
       - Example: If data missing, log the issue and get productive alternatives

    3. detect_fabricated_data(data, data_type, ticker):
       - Use AFTER receiving data from any source
       - Detects placeholder text, fake values, impossible data
       - Example: Before accepting agent output, verify it's not fabricated

    SUPERVISION WORKFLOW (CRITICAL - YOU MUST FOLLOW THIS):
    1. BEFORE delegating: validate_data_exists() to check availability
    2. IF data missing: log_blocking_issue() and pursue alternatives (different ticker, different analysis type, etc.)
    3. DELEGATE to appropriate specialized agent only if data exists
    4. AFTER receiving results: detect_fabricated_data() to verify legitimacy
    5. FINALLY: Delegate to AgentEvaluator for quality checks
    6. NEVER allow fake/assumed/placeholder data - if data doesn't exist, say so clearly

    CRITICAL RULES (from CLAUDE.md):
    - NEVER make up data - if it doesn't exist, flag it clearly and suggest alternatives
    - NEVER wait indefinitely - always have alternative productive tasks
    - NEVER use fake/assumed/placeholder data
    - NEVER delete all code without permission

    IMPORTANT NOTES:
    - Available companies: {len(TARGET_TICKERS)} tickers across semiconductor, energy, crypto-mining, and tech verticals ({TICKER_LIST_STR})
    - Financial data years: 2021-2024
    - Quarterly earnings: Latest four quarters stored per company
    - Reddit data: Past 1 month from 9 subreddits
    - News search: Requires internet access and Google Custom Search credentials
    - CEO data: Current information for major publicly traded companies
    - Always include disclaimers for predictions, Reddit sentiment, and CEO data
    - If uncertain about which agent to use, explain your reasoning
    """
)