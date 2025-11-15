"""
DeepAlpha News Analysis Module

This module provides AI-powered news interpretation using the DeepAlpha 7-Pillar Stock Evaluation Framework.
Separates news analysis logic from news fetching for better modularity.
"""

import os
import json
import logging
import yfinance as yf
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False

from .utils import NEWS_INTERPRETATION_DIR

logger = logging.getLogger(__name__)

# Directory for sector metrics
DATA_DIR = "data"
SECTOR_METRICS_DIR = os.path.join(DATA_DIR, "structured", "sector_metrics")

# AI Infrastructure Layer Mapping
AI_LAYER_SECTOR_DEFAULTS: Dict[str, str] = {
    "technology": "Compute",
    "communication services": "Interconnect",
    "industrials": "Interconnect",
    "energy": "Energy",
    "utilities": "Energy",
    "materials": "Materials",
    "basic materials": "Materials",
    "consumer defensive": "Services",
    "consumer cyclical": "Services",
    "healthcare": "Healthcare",
    "financial services": "Services",
}

AI_LAYER_INDUSTRY_KEYWORDS: Dict[str, str] = {
    "semiconductor": "Compute",
    "chip": "Compute",
    "cloud": "Compute",
    "software": "Compute",
    "hardware": "Compute",
    "ai": "Compute",
    "network": "Interconnect",
    "communication": "Interconnect",
    "telecom": "Interconnect",
    "defense": "Energy",
    "battery": "Energy",
    "solar": "Energy",
    "wind": "Energy",
    "uranium": "Materials",
    "lithium": "Materials",
    "mining": "Materials",
    "chemical": "Materials",
    "insurance": "Services",
    "bank": "Services",
    "retail": "Services",
    "logistics": "Interconnect",
}


def _safe_float(value: Any) -> Optional[float]:
    """Safely convert a value to float, returning None if conversion fails."""
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def infer_ai_layer(sector: Optional[str], industry: Optional[str]) -> str:
    """
    Infer the AI infrastructure layer based on sector and industry.

    Returns one of: Compute, Interconnect, Energy, Materials, Services, Healthcare, N/A
    """
    sector_key = (sector or "").strip().lower()
    industry_key = (industry or "").strip().lower()

    if not sector_key and not industry_key:
        return "N/A"

    # Check industry keywords first (more specific)
    for keyword, layer in AI_LAYER_INDUSTRY_KEYWORDS.items():
        if keyword in industry_key:
            return layer

    # Check sector defaults
    inferred = AI_LAYER_SECTOR_DEFAULTS.get(sector_key)
    if inferred:
        return inferred

    # Check sector keywords as fallback
    for keyword, layer in AI_LAYER_INDUSTRY_KEYWORDS.items():
        if keyword in sector_key:
            return layer

    return "N/A"


def infer_conviction_quadrant(metrics: Optional[Dict[str, Any]]) -> str:
    """
    Infer the conviction quadrant based on company metrics.

    Returns one of:
    - Strategic Compounder
    - High-Growth Challenger
    - Expansion Flywheel
    - Turnaround Risk
    - Balanced Execution (default)
    """
    if not isinstance(metrics, dict) or not metrics:
        return "Balanced Execution"

    momentum_6m = _safe_float(metrics.get("momentum_6m"))
    volatility = _safe_float(metrics.get("volatility"))
    debt_to_equity = _safe_float(metrics.get("debt_to_equity"))
    cagr = _safe_float(metrics.get("cagr"))

    if momentum_6m is not None and volatility is not None:
        if momentum_6m >= 40 and volatility >= 45:
            return "High-Growth Challenger"
        if momentum_6m >= 10 and volatility < 45 and (debt_to_equity is None or debt_to_equity < 120):
            return "Strategic Compounder"
        if momentum_6m <= -5 and debt_to_equity and debt_to_equity > 200:
            return "Turnaround Risk"

    if cagr is not None and cagr >= 25 and (debt_to_equity is None or debt_to_equity < 100):
        return "Expansion Flywheel"

    return "Balanced Execution"


def compute_technical_snapshot(ticker: str) -> Tuple[str, str, str]:
    """
    Compute lightweight technical indicators for the analysis.

    Returns:
        Tuple of (rsi_value, sma_position, volume_change) as formatted strings
    """
    try:
        history = yf.Ticker(ticker).history(period="6mo", interval="1d")
        if history.empty:
            return ("N/A", "Insufficient data", "N/A")

        closes = history["Close"].dropna()
        volumes = history["Volume"].dropna()

        # RSI (14-day)
        if len(closes) >= 15:
            delta = closes.diff()
            gain = delta.clip(lower=0)
            loss = -delta.clip(upper=0)
            avg_gain = gain.rolling(window=14, min_periods=14).mean()
            avg_loss = loss.rolling(window=14, min_periods=14).mean()
            rs = avg_gain / avg_loss.replace({0: np.nan})
            rsi_series = 100 - (100 / (1 + rs))
            rsi_value = rsi_series.iloc[-1]
            rsi_text = f"{rsi_value:.1f}"
        else:
            rsi_text = "N/A"

        # Simple moving averages
        sma_50 = closes.rolling(window=50, min_periods=20).mean().iloc[-1] if len(closes) >= 20 else None
        sma_200 = closes.rolling(window=200, min_periods=60).mean().iloc[-1] if len(closes) >= 60 else None
        if sma_50 is not None and sma_200 is not None:
            if sma_50 > sma_200:
                sma_position = "50 above 200"
            elif sma_50 < sma_200:
                sma_position = "50 below 200"
            else:
                sma_position = "50 equals 200"
        else:
            sma_position = "Insufficient data"

        # Volume change vs 30-day average
        if len(volumes) >= 30:
            recent_volume = volumes.iloc[-1]
            avg_volume = volumes.tail(30).mean()
            if avg_volume:
                volume_pct = ((recent_volume - avg_volume) / avg_volume) * 100
                volume_change = f"{volume_pct:+.1f}%"
            else:
                volume_change = "N/A"
        else:
            volume_change = "N/A"

        return (rsi_text, sma_position, volume_change)

    except Exception as exc:
        logger.warning(f"Unable to compute technical snapshot for {ticker}: {exc}")
        return ("N/A", "Insufficient data", "N/A")


def strip_code_fence(text: str) -> str:
    """Remove Markdown-style code fences from a string."""
    cleaned = (text or "").strip()
    if cleaned.startswith("```"):
        cleaned = cleaned[3:]
        newline_index = cleaned.find("\n")
        if newline_index != -1:
            cleaned = cleaned[newline_index + 1:]
        else:
            cleaned = ""
    cleaned = cleaned.rstrip()
    if cleaned.endswith("```"):
        cleaned = cleaned[:-3].rstrip()
    return cleaned


def interpret_news_with_deep_alpha(
    ticker: str,
    news_articles: List[Dict[str, Any]],
    max_retries: int = 3,
    retry_delay: float = 2.0
) -> str:
    """
    Interpret news using the DeepAlpha 7-Pillar Stock Evaluation Framework.

    Args:
        ticker: Stock ticker symbol
        news_articles: List of news article dictionaries
        max_retries: Maximum number of retry attempts
        retry_delay: Base delay between retries (exponential backoff)

    Returns:
        JSON string containing the DeepAlpha analysis structure
    """
    if not GEMINI_AVAILABLE:
        error_msg = "Google Gemini not available. Please install google-generativeai package."
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

    if not news_articles:
        logger.warning(f"No news articles provided for {ticker}")
        return json.dumps({"error": "No news articles to analyze"})

    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")

        # Get company info
        try:
            stock_info = yf.Ticker(ticker).info
            sector = stock_info.get('sector', 'Unknown')
            industry = stock_info.get('industry', 'Unknown')
        except Exception as e:
            logger.warning(f"Could not fetch company info for {ticker}: {e}")
            sector = "Unknown"
            industry = "Unknown"

        # Get latest sector metrics
        sector_context = "Sector metrics not available."
        sector_metrics_files = sorted([
            f for f in os.listdir(SECTOR_METRICS_DIR)
            if f.startswith('sector_metrics_')
        ]) if os.path.exists(SECTOR_METRICS_DIR) else []

        if sector_metrics_files:
            latest_sector_file = os.path.join(SECTOR_METRICS_DIR, sector_metrics_files[-1])
            with open(latest_sector_file, 'r') as f:
                sector_data = json.load(f)
                sectors_dict = sector_data.get('sectors', {})
                sector_metric = sectors_dict.get(sector)

                if sector_metric:
                    quality_val = _safe_float(sector_metric.get('avg_quality_score'))
                    momentum_val = _safe_float(sector_metric.get('avg_momentum_3m'))
                    roe_val = _safe_float(sector_metric.get('avg_roe'))

                    quality_text = f"{quality_val:.2f}" if quality_val is not None else "N/A"
                    momentum_text = f"{momentum_val:+.1f}%" if momentum_val is not None else "N/A"
                    roe_text = f"{roe_val:.1f}%" if roe_val is not None else "N/A"

                    sector_context = (
                        f"Quality Score: {quality_text}, "
                        f"3M Momentum: {momentum_text}, "
                        f"ROE: {roe_text}"
                    )

        # Get latest company metrics
        company_metrics_files = sorted([
            f for f in os.listdir(SECTOR_METRICS_DIR)
            if f.startswith('company_metrics_')
        ]) if os.path.exists(SECTOR_METRICS_DIR) else []

        company_context = "Company fundamentals not available."
        company_metrics: Optional[Dict[str, Any]] = None

        if company_metrics_files:
            latest_company_file = os.path.join(SECTOR_METRICS_DIR, company_metrics_files[-1])
            with open(latest_company_file, 'r') as f:
                company_data = json.load(f)
                company_metrics = next((c for c in company_data if c['ticker'] == ticker), None)
                if company_metrics:
                    pe_ratio_val = _safe_float(company_metrics.get('pe_ratio'))
                    roe_val = _safe_float(company_metrics.get('roe'))
                    momentum_val = _safe_float(company_metrics.get('momentum_3m'))
                    volatility_val = _safe_float(company_metrics.get('volatility'))

                    pe_text = f"{pe_ratio_val:.1f}" if pe_ratio_val is not None else "N/A"
                    roe_text = f"{roe_val:.1f}%" if roe_val is not None else "N/A"
                    momentum_text = f"{momentum_val:+.1f}%" if momentum_val is not None else "N/A"
                    volatility_text = f"{volatility_val:.1f}%" if volatility_val is not None else "N/A"

                    company_context = (
                        f"P/E: {pe_text}, "
                        f"ROE: {roe_text}, "
                        f"3M Return: {momentum_text}, "
                        f"Volatility: {volatility_text}"
                    )

        # Get market index data (NASDAQ)
        try:
            nasdaq = yf.Ticker("^IXIC")
            nasdaq_hist = nasdaq.history(period="1mo")
            nasdaq_change = ((nasdaq_hist['Close'].iloc[-1] / nasdaq_hist['Close'].iloc[0]) - 1) * 100
            market_context = f"NASDAQ 1-month: {nasdaq_change:+.1f}%"
        except:
            market_context = "Market data not available."

        ai_layer = infer_ai_layer(sector, industry)
        conviction_quadrant = infer_conviction_quadrant(company_metrics)
        rsi_value, sma_position, volume_change = compute_technical_snapshot(ticker)

        # Compile news summaries
        news_summaries = []
        for i, article in enumerate(news_articles[:5], 1):  # Limit to 5 most recent
            title = article.get('title') or article.get('headline') or 'Untitled headline'
            publisher = article.get('publisher') or article.get('source') or 'News Source'
            news_summaries.append(f"{i}. {title} ({publisher})")
            summary_snippet = article.get('summary') or article.get('snippet')
            if summary_snippet:
                news_summaries.append(f"   Summary: {summary_snippet[:150]}...")

        news_text = "\n".join(news_summaries)

        # Build the Deep Alpha system prompt for Gemini with sector-aware pillar guidance
        prompt = f"""SYSTEM INSTRUCTION:
You are a Deep Alpha Analyst (DAA) applying the full Deep Alpha Stock Evaluation Framework (Pillars A-G). Your objective is to rigorously determine if a recent news event is mere market 'noise' or if it fundamentally alters the company's long-term value, competitive moat, and conviction index. Based on this analysis, you must generate content suitable for a "Latest News & Investment Analysis" card, providing a clear **Rating** and actionable **Key Takeaways**.

**PRIMARY RULE:** You MUST dynamically select the relevant metrics for Pillars A-F based on the specified {sector} from the list below.

--- INPUT DATA ---
COMPANY: {ticker}
SECTOR: {sector} (E.g., Technology, Energy/Defense/Materials, Consumer/Services, Finance, Healthcare)
INDUSTRY: {industry}

NEWS:
{news_text}

CONTEXTUAL DATA:
AI INFRASTRUCTURE LAYER: {ai_layer} (E.g., Compute, Interconnect, Energy, Materials, N/A)
CURRENT CONVICTION QUADRANT: {conviction_quadrant} (E.g., Strategic Compounder, High-Growth Challenger)
COMPANY FUNDAMENTALS: {company_context}
SECTOR METRICS: {sector_context}
MARKET CONDITIONS: {market_context}
TECHNICAL DATA (REQUIRED for Pillar G):
- Current RSI (14-day): {rsi_value}
- 50-day SMA vs. 200-day SMA Position: {sma_position} (E.g., 50 above 200)
- Recent Volume Change (vs 30-day avg): {volume_change}

--- TASK: DEEP ALPHA PILLAR ASSESSMENT (All 7 Pillars) ---
Interpret the news by systematically assessing its impact on the following seven pillars. The model MUST reference the most appropriate metrics for the given sector in its analysis.

ALWAYS weave in the following investigative checks when relevant, citing concrete data where possible:
- Explain why sector growth is accelerating (government policy, national strategy, secular demand) when the industry is in an explosive phase.
- Comment on technological feasibility or pace of innovation driving the thesis.
- Evaluate leverage and liquidity to confirm debt remains manageable under the updated outlook.
- Highlight backlog or committed revenue visibility and whether it is expanding.
- Discuss valuation (P/E, P/S, EV/Sales) across bull/base/bear framing and whether the stock has recently come down from all-time highs.
- Assess leadership credibility, including recent executive commentary or insider selling activity.
- Surface material deals/partnerships/M&A announced alongside the news.
- Note hiring momentum and whether talent deployment matches stated strategy.
- Briefly situate the company inside the ecosystem (what it builds, whom it serves) using company disclosures or website positioning.
- Call out risks (operational, regulatory/tariff, execution) that could derail the scenario.

**1. Pillar A (Fundamentals & Growth):**
* **Tech/AI:** 3-year/5-year **CAGR**, **R&D Intensity**, Forward EPS.
* **Energy/Defense:** Projected Margin on Backlog, CapEx for Resource Expansion, **Contract Length/Stability**.
* **Consumer:** **Same-Store Sales Growth (SSS)**, Inventory Turnover, Marketing ROI.
* **Finance:** **Net Interest Margin (NIM)**, Loan Growth Rate, Return on Equity (ROE).
* **Healthcare:** **Clinical Trial Phase Progression**, Success Rates, Revenue from Blockbusters.

**2. Pillar B (Valuation & Ratios):**
* **Tech/AI:** **PEG Ratio**, Revenue Multiples (P/S, EV/Sales).
* **Energy/Defense:** **P/B (Book Value)**, Free Cash Flow Yield (FCFY), EV/EBITDA.
* **Consumer:** EV/Sales, **Debt/EBITDA** (Debt management).
* **Finance:** **Price-to-Tangible Book Value (P/TBV)**, Loan Loss Reserves vs. NPLs.
* **Healthcare:** P/S, Sum-of-the-parts (SOTP) Valuation based on pipeline NPV.

**3. Pillar C (Competitive Moat):**
* **Tech/AI:** **Ecosystem Lock-in**, **Developer Dependency**, IP Depth.
* **Energy/Defense:** **Resource Independence/Control**, Regulatory/Permitting Barriers to Entry.
* **Consumer:** **Brand Strength/Loyalty**, Supply Chain/Logistical Advantage.
* **Finance:** Scale of Deposit Base, **Regulatory Barriers**, Fee Income vs. Net Interest Income.
* **Healthcare:** **Patent Expiration/Cliffs**, Drug Uniqueness, Manufacturing Scalability.

**4. Pillar D (Strategic Relevance/Policy):**
* **Tech/AI:** **Export Control Exposure**, CHIPS Act/Government Subsidies, China/US Decoupling.
* **Energy/Defense:** **National Security Mandates**, **DOE/DoD Project Flow**, Resource Scarcity.
* **Consumer:** **Interest Rate Sensitivity**, Labor Law changes, Consumer Confidence Index link.
* **Finance:** **Tier 1 Capital Ratio requirements**, Systemically Important Financial Institution (SIFI) regulation, Rate Hike/Cut Policy.
* **Healthcare:** **FDA Approval Timelines/PDUFA Dates**, Healthcare Policy Changes (e.g., pricing legislation).

**5. Pillar E (Demand Visibility):**
* **Tech/AI:** **New Design Wins**, Backlog/Book-to-Bill ratio.
* **Energy/Defense:** **Long-term Contract Signings**, Backlog Stability.
* **Consumer:** **Booking/Reservation Trends**, Same-Store Sales Guidance.
* **Finance:** Loan Application Volume, Mortgage Origination Trends.
* **Healthcare:** Phase 3 Trial Readouts, Commercialization Timelines.

**6. Pillar F (AI Supply Chain Lens):**
* **All Sectors:** Measures the company's current or potential exposure to AI-driven demand/efficiency gains/risks. Focus on **Substitution Risk** from AI.

**7. Pillar G (Technical Analysis):**
* Analyzes the news-driven stock reaction: Overbought/Oversold (RSI), Trend Confirmation/Reversal (SMAs), and supporting **Volume**.

--- REQUIRED OUTPUT ---
Generate the analysis in the **strict JSON format** below. The entire response must be a single JSON object.

```json
{{
  "rating_buy_hold_sell": "[BUY/HOLD/SELL]",
  "sentiment_confidence": "[High/Medium/Low]",
  "key_takeaways": [
    {{
      "type": "Fundamental Impact (Pillars A/B/E)",
      "summary": "Focus on material changes to growth rates, profitability, or demand visibility metrics."
    }},
    {{
      "type": "Strategic Moat & Policy Shift (Pillars C/D/F)",
      "summary": "Focus on changes to competitive position, policy tailwinds, or AI/Sector vulnerability."
    }},
    {{
      "type": "Technical Noise Filter (Pillar G)",
      "summary": "Focus on whether the reaction is exaggerated (RSI/Volume) or a sustained move."
    }}
  ],
  "investment_conclusion": {{
    "paragraph": "A concise 150-200 word summary for investors. Integrate the impact on 2-3 specific Deep Alpha Pillars (A-F) and state the implied shift in the Scenario Modeling Framework (Bull, Base, or Bear). Explain why the news is *not* noise, or conversely, why it is simply noise.",
    "reasoning_justification": "A 1-2 sentence justification for the rating, explicitly referencing the Conviction Index drivers (Expected CAGR, Moat Strength, and/or Valuation Multiple)."
  }},
  "next_step_focus": {{
    "title": "Next Step: Monitoring Key Alpha Drivers",
    "monitor_points": [
      "The next earnings report's updated guidance for 5-year CAGR.",
      "Competitor reactions impacting the company's Competitive Moat (Pillar C).",
      "Official government announcements regarding relevant Policy Tailwinds (Pillar D)."
    ]
  }}
}}
```

"""

        # Configure Gemini API
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-2.0-flash-exp')

        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                # Generate content with JSON mode for structured output
                response = model.generate_content(
                    prompt,
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=3000,
                        temperature=0.3,
                        response_mime_type="application/json",
                    )
                )

                interpretation = response.text.strip()

                # Validate that we got a meaningful response
                if len(interpretation) < 50:
                    raise ValueError(f"Response too short ({len(interpretation)} chars), likely incomplete")

                # Validate JSON structure
                try:
                    parsed_json = json.loads(interpretation)
                    # Validate required fields for Deep Alpha structure
                    required_fields = ['rating_buy_hold_sell', 'sentiment_confidence', 'key_takeaways', 'investment_conclusion']
                    missing_fields = [field for field in required_fields if field not in parsed_json]
                    if missing_fields:
                        logger.warning(f"JSON missing required fields: {missing_fields}, retrying...")
                        raise ValueError(f"Missing required fields: {missing_fields}")
                except json.JSONDecodeError as je:
                    logger.warning(f"Invalid JSON format: {je}, retrying...")
                    raise ValueError(f"Invalid JSON format: {je}")

                logger.info(f"✅ Generated DeepAlpha news interpretation for {ticker} using Gemini 2.0 Flash Experimental (attempt {attempt + 1})")
                return interpretation

            except Exception as api_error:
                logger.warning(f"Attempt {attempt + 1}/{max_retries} failed for {ticker}: {api_error}")

                if attempt < max_retries - 1:
                    import time
                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # Final attempt failed
                    raise

    except Exception as e:
        logger.error(f"❌ All {max_retries} attempts failed for {ticker}: {e}")
        return json.dumps({
            "error": f"Error generating interpretation after {max_retries} attempts: {str(e)}"
        })


def save_news_interpretation(ticker: str, news_file_path: str) -> Optional[str]:
    """
    Generate and save DeepAlpha news interpretation for a ticker.
    Ensures 1:1 mapping with news file by using exact same timestamp.

    Args:
        ticker: Stock ticker symbol
        news_file_path: Path to the news JSON file

    Returns:
        Path to saved interpretation file, or None if failed
    """
    try:
        # Load news data
        with open(news_file_path, 'r') as f:
            news_data = json.load(f)

        news_articles = news_data.get('articles', [])
        if not news_articles:
            logger.warning(f"No articles found in {news_file_path}")
            return None

        # Check if interpretation already exists
        news_filename = os.path.basename(news_file_path)
        interpretation_filename = news_filename.replace('_news_', '_news_interpretation_')
        interpretation_path = os.path.join(NEWS_INTERPRETATION_DIR, interpretation_filename)

        if os.path.exists(interpretation_path):
            logger.info(f"Interpretation already exists: {interpretation_path}")
            return interpretation_path

        # Generate interpretation using DeepAlpha framework
        logger.info(f"Generating DeepAlpha news interpretation for {ticker}...")
        interpretation_text = interpret_news_with_deep_alpha(ticker, news_articles)
        cleaned_interpretation = strip_code_fence(interpretation_text)

        # Parse JSON
        parsed_interpretation = None
        if cleaned_interpretation:
            try:
                parsed_interpretation = json.loads(cleaned_interpretation)
            except json.JSONDecodeError:
                logger.error(f"Failed to parse DeepAlpha JSON for {ticker}")
                parsed_interpretation = None

        interpretation_payload: Any = parsed_interpretation if parsed_interpretation is not None else cleaned_interpretation

        # Save interpretation with 1:1 mapping to news file
        interpretation_data = {
            'ticker': ticker,
            'interpretation': interpretation_payload,
            'interpretation_raw': interpretation_text,
            'news_file': news_filename,
            'news_timestamp': news_data.get('fetch_timestamp'),
            'interpretation_timestamp': datetime.now().isoformat(),
            'num_articles_analyzed': len(news_articles),
            'articles': news_articles,  # Include articles for reference
            'format': 'deep_alpha_json' if parsed_interpretation is not None else 'text'
        }

        # Ensure directory exists
        os.makedirs(NEWS_INTERPRETATION_DIR, exist_ok=True)

        with open(interpretation_path, 'w') as f:
            json.dump(interpretation_data, f, indent=2)

        logger.info(f"✅ Saved DeepAlpha news interpretation to {interpretation_path}")
        return interpretation_path

    except Exception as e:
        logger.error(f"Error saving news interpretation for {ticker}: {e}")
        return None


def generate_interpretations_for_all_news_files() -> Dict[str, Any]:
    """
    Scan NEWS_DATA_DIR for all news files and generate missing interpretations.

    Returns:
        Dictionary with statistics about the operation
    """
    from .utils import NEWS_DATA_DIR

    stats = {
        'total_news_files': 0,
        'already_interpreted': 0,
        'newly_generated': 0,
        'failed': 0,
        'skipped_no_articles': 0
    }

    # Ensure directories exist
    os.makedirs(NEWS_DATA_DIR, exist_ok=True)
    os.makedirs(NEWS_INTERPRETATION_DIR, exist_ok=True)

    logger.info("=" * 60)
    logger.info("GENERATING DEEP ALPHA NEWS INTERPRETATIONS")
    logger.info("=" * 60)

    # Find all news files
    news_files = sorted([f for f in os.listdir(NEWS_DATA_DIR) if f.endswith('_news_*.json') or f.endswith('.json')])
    stats['total_news_files'] = len(news_files)

    logger.info(f"Found {len(news_files)} news files")

    for news_file in news_files:
        try:
            news_path = os.path.join(NEWS_DATA_DIR, news_file)

            # Check if interpretation already exists
            interpretation_filename = news_file.replace('_news_', '_news_interpretation_')
            interpretation_path = os.path.join(NEWS_INTERPRETATION_DIR, interpretation_filename)

            if os.path.exists(interpretation_path):
                stats['already_interpreted'] += 1
                logger.info(f"⏭️  Skipping {news_file} (already interpreted)")
                continue

            # Load news data to check for articles
            with open(news_path, 'r') as f:
                news_data = json.load(f)

            articles = news_data.get('articles', [])
            if not articles or len(articles) == 0:
                stats['skipped_no_articles'] += 1
                logger.info(f"⏭️  Skipping {news_file} (no articles)")
                continue

            # Extract ticker from filename (format: TICKER_news_TIMESTAMP.json)
            ticker = news_file.split('_news_')[0]

            # Generate interpretation
            logger.info(f"📰 Generating interpretation for {ticker} ({news_file})...")
            result = save_news_interpretation(ticker, news_path)

            if result:
                stats['newly_generated'] += 1
                logger.info(f"✅ Successfully generated interpretation for {ticker}")
            else:
                stats['failed'] += 1
                logger.warning(f"❌ Failed to generate interpretation for {ticker}")

            # Rate limit to avoid API throttling
            import time
            time.sleep(1)

        except Exception as e:
            stats['failed'] += 1
            logger.error(f"Error processing {news_file}: {e}")

    logger.info("")
    logger.info("=" * 60)
    logger.info("INTERPRETATION GENERATION COMPLETE")
    logger.info("=" * 60)
    logger.info(f"Total news files: {stats['total_news_files']}")
    logger.info(f"Already interpreted: {stats['already_interpreted']}")
    logger.info(f"Newly generated: {stats['newly_generated']}")
    logger.info(f"Skipped (no articles): {stats['skipped_no_articles']}")
    logger.info(f"Failed: {stats['failed']}")
    logger.info("=" * 60)

    return stats


# CLI entry point
if __name__ == "__main__":
    import logging

    # Set up logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    print("\n" + "=" * 60)
    print("DeepAlpha News Interpretation Generator")
    print("=" * 60)
    print("This script will scan all news files and generate")
    print("DeepAlpha 7-Pillar analysis for any missing interpretations.")
    print("=" * 60 + "\n")

    # Run the generation
    stats = generate_interpretations_for_all_news_files()

    # Print summary
    print("\n" + "=" * 60)
    print("FINAL SUMMARY")
    print("=" * 60)
    print(f"Total news files found: {stats['total_news_files']}")
    print(f"Already interpreted: {stats['already_interpreted']}")
    print(f"Newly generated: {stats['newly_generated']}")
    print(f"Skipped (no articles): {stats['skipped_no_articles']}")
    print(f"Failed: {stats['failed']}")
    print("=" * 60)

    if stats['newly_generated'] > 0:
        print(f"\n✅ Successfully generated {stats['newly_generated']} new DeepAlpha interpretations!")
    if stats['failed'] > 0:
        print(f"\n⚠️  Warning: {stats['failed']} interpretations failed")

    print("\nDone!")
