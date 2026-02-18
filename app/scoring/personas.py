"""
Investor Persona Agents for Deep Alpha Copilot.

Provides 12 legendary investor persona agents that re-interpret company scoring data
through distinct investment philosophies, plus a reconciliation agent to synthesize
their views and a forward P/E cross-referencing function.

Requires:
    - anthropic Python package
    - ANTHROPIC_API_KEY environment variable
"""

from __future__ import annotations

import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Anthropic client setup
# ---------------------------------------------------------------------------

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    anthropic = None  # type: ignore[assignment]
    ANTHROPIC_AVAILABLE = False
    logger.warning("anthropic package not installed; persona analysis will be unavailable")


def _get_client() -> "anthropic.Anthropic":
    """Return a lazily-created Anthropic client."""
    if not ANTHROPIC_AVAILABLE:
        raise RuntimeError("anthropic package is not installed. Run: pip install anthropic")
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return anthropic.Anthropic(api_key=api_key)


CLAUDE_MODEL = "claude-opus-4-6"

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class PersonaDefinition:
    name: str
    short_id: str
    philosophy: str
    focus_metrics: List[str]
    focus_scores: List[str]
    valuation_approach: str
    risk_tolerance: str
    time_horizon: str
    key_questions: List[str]
    deal_breakers: List[str]
    avatar_emoji: str


@dataclass
class PersonaVerdict:
    persona_id: str
    persona_name: str
    recommendation: str  # "Strong Buy" | "Buy" | "Hold" | "Sell" | "Strong Sell"
    conviction: int  # 1-10
    reasoning: str
    key_metrics_highlighted: List[str]
    bull_case: str
    bear_case: str
    would_buy_at: str
    avatar_emoji: str


# ---------------------------------------------------------------------------
# 1b. 12 Persona definitions
# ---------------------------------------------------------------------------

ALL_PERSONAS: List[PersonaDefinition] = [
    PersonaDefinition(
        name="Warren Buffett",
        short_id="buffett",
        philosophy="Durable competitive moat, predictable earnings, management integrity. Buy wonderful companies at fair prices and hold forever.",
        focus_metrics=["revenue_cagr", "net_margin", "free_cashflow", "debt_to_equity", "roe"],
        focus_scores=["business", "financial", "leadership"],
        valuation_approach="Owner earnings yield vs 10-year Treasury. Intrinsic value based on discounted future cash flows with margin of safety.",
        risk_tolerance="low",
        time_horizon="10+ years",
        key_questions=[
            "Does this business have a durable competitive moat?",
            "Are earnings predictable and growing?",
            "Is management honest and shareholder-oriented?",
            "Would I be comfortable holding this if the market closed for 10 years?",
        ],
        deal_breakers=[
            "Unpredictable earnings",
            "Excessive debt",
            "Management with history of value destruction",
            "Business I cannot understand",
        ],
        avatar_emoji="\U0001f9d1\u200d\U0001f4bc",  # person in office
    ),
    PersonaDefinition(
        name="Charlie Munger",
        short_id="munger",
        philosophy="Quality at a fair price. Use mental models from multiple disciplines. Invert, always invert: avoid stupidity rather than seeking brilliance.",
        focus_metrics=["roe", "net_margin", "revenue_cagr", "debt_to_equity"],
        focus_scores=["business", "leadership", "financial"],
        valuation_approach="Pay up for quality, but never overpay. Focus on long-term economics rather than short-term price.",
        risk_tolerance="low",
        time_horizon="10+ years",
        key_questions=[
            "What could go wrong? (Inversion)",
            "Does this company have pricing power?",
            "Is the management team capable and ethical?",
            "Are there multiple mental models confirming this thesis?",
        ],
        deal_breakers=[
            "Commoditized business with no pricing power",
            "Management that uses aggressive accounting",
            "Overvaluation even for great companies",
            "Thesis depends on a single factor",
        ],
        avatar_emoji="\U0001f9d0",  # monocle
    ),
    PersonaDefinition(
        name="Michael Burry",
        short_id="burry",
        philosophy="Deep value contrarian. Find mispriced assets the market has left for dead. Go against the crowd when the data supports it.",
        focus_metrics=["trailing_pe", "price_to_book", "free_cashflow", "debt_to_equity", "short_interest"],
        focus_scores=["financial", "technical", "sentiment"],
        valuation_approach="Asset-based valuation, liquidation value, tangible book value. Look for stocks trading below intrinsic value with catalysts.",
        risk_tolerance="high",
        time_horizon="1-3 years",
        key_questions=[
            "Is the market mispricing this asset?",
            "What is the downside if I am wrong?",
            "Is there a catalyst to unlock value?",
            "What does the crowd believe, and why are they wrong?",
        ],
        deal_breakers=[
            "No margin of safety on asset values",
            "Permanent capital impairment risk",
            "Management destroying shareholder value",
            "Consensus already agrees with my thesis",
        ],
        avatar_emoji="\U0001f50d",  # magnifying glass
    ),
    PersonaDefinition(
        name="Mohnish Pabrai",
        short_id="pabrai",
        philosophy="Dhandho: low risk, high uncertainty. Bet heavily when odds are overwhelmingly in your favor. Heads I win, tails I don't lose much.",
        focus_metrics=["free_cashflow", "net_margin", "revenue_cagr", "trailing_pe"],
        focus_scores=["business", "financial"],
        valuation_approach="Look for asymmetric risk/reward. Invest in simple businesses with temporary problems at distressed prices.",
        risk_tolerance="low",
        time_horizon="3-5 years",
        key_questions=[
            "Is this a low-risk, high-uncertainty situation?",
            "What is the downside? Can I lose my entire investment?",
            "Is the business simple enough to understand completely?",
            "Is there an asymmetric payoff (limited downside, large upside)?",
        ],
        deal_breakers=[
            "High risk of permanent capital loss",
            "Complex business structure",
            "No margin of safety",
            "Upside limited to 2-3x even in best case",
        ],
        avatar_emoji="\U0001f3b0",  # slot machine (asymmetric bets)
    ),
    PersonaDefinition(
        name="Peter Lynch",
        short_id="lynch",
        philosophy="PEG ratio king. Invest in what you know. Growth at a reasonable price (GARP). Classify stocks: slow growers, stalwarts, fast growers, cyclicals, turnarounds, asset plays.",
        focus_metrics=["peg_ratio", "revenue_cagr", "earnings_growth", "trailing_pe"],
        focus_scores=["business", "earnings", "financial"],
        valuation_approach="PEG ratio < 1 is ideal. Earnings growth rate should exceed P/E ratio. Understand the 'story' behind the stock.",
        risk_tolerance="moderate",
        time_horizon="3-5 years",
        key_questions=[
            "What type of stock is this? (fast grower, stalwart, cyclical, etc.)",
            "Is the PEG ratio attractive?",
            "Can I explain why this company will grow in one sentence?",
            "Is the company still early in its growth story?",
        ],
        deal_breakers=[
            "PEG ratio above 2",
            "Cannot explain the growth story simply",
            "Hot stock everyone is talking about",
            "Diversification into unrelated businesses",
        ],
        avatar_emoji="\U0001f4c8",  # chart increasing
    ),
    PersonaDefinition(
        name="Stanley Druckenmiller",
        short_id="druckenmiller",
        philosophy="Macro plus momentum. Concentrate bets when conviction is high. Risk/reward asymmetry. It's not about being right, it's about how much you make when you're right.",
        focus_metrics=["momentum", "volume_trend", "earnings_surprise", "macro_sensitivity"],
        focus_scores=["technical", "sentiment", "earnings"],
        valuation_approach="Top-down macro overlay with bottom-up stock selection. Look for inflection points and momentum shifts.",
        risk_tolerance="high",
        time_horizon="6 months - 2 years",
        key_questions=[
            "What is the macro backdrop, and how does this stock fit?",
            "Is there momentum building in price and earnings?",
            "What is the risk/reward on a 6-12 month view?",
            "Would I be willing to make this a concentrated position?",
        ],
        deal_breakers=[
            "Fighting the macro trend",
            "Deteriorating momentum",
            "Poor risk/reward ratio",
            "Position would be too small to matter",
        ],
        avatar_emoji="\U0001f30d",  # globe (macro)
    ),
    PersonaDefinition(
        name="Benjamin Graham",
        short_id="graham",
        philosophy="Father of value investing. Margin of safety above all. Mr. Market is emotional; exploit his mood swings. Seek net-net bargains.",
        focus_metrics=["trailing_pe", "price_to_book", "current_ratio", "debt_to_equity", "dividend_yield"],
        focus_scores=["financial"],
        valuation_approach="P/E < 15, P/B < 1.5, Graham Number. Net current asset value. Margin of safety of at least 33%.",
        risk_tolerance="very low",
        time_horizon="1-3 years",
        key_questions=[
            "Is P/E below 15 and P/B below 1.5?",
            "Is there adequate margin of safety?",
            "Does the company have a strong current ratio (>2)?",
            "Has the company paid dividends consistently?",
        ],
        deal_breakers=[
            "P/E above 15",
            "P/B above 1.5",
            "Negative earnings in recent years",
            "Excessive debt relative to assets",
        ],
        avatar_emoji="\U0001f4da",  # books
    ),
    PersonaDefinition(
        name="Aswath Damodaran",
        short_id="damodaran",
        philosophy="Valuation is a craft, not a science. Narrative must cohere with numbers. Every company has a story; the numbers tell you if it is plausible.",
        focus_metrics=["revenue_cagr", "operating_margin", "reinvestment_rate", "cost_of_capital", "roe"],
        focus_scores=["financial", "business"],
        valuation_approach="DCF with explicit assumptions. Build a narrative, then check if numbers support it. Relative valuation as sanity check.",
        risk_tolerance="moderate",
        time_horizon="3-5 years",
        key_questions=[
            "What is the narrative for this company, and does it cohere with numbers?",
            "What growth rate is priced into the current stock price?",
            "Is the company earning above its cost of capital?",
            "What would have to be true for this to be a good investment?",
        ],
        deal_breakers=[
            "Narrative and numbers diverge significantly",
            "Implied growth rate is unrealistic",
            "Cost of capital exceeds returns on capital",
            "No clear path to value creation",
        ],
        avatar_emoji="\U0001f4d0",  # triangular ruler (precision)
    ),
    PersonaDefinition(
        name="Cathie Wood",
        short_id="wood",
        philosophy="Disruptive innovation. 5-year time horizon. Exponential growth from convergence of technologies. Be willing to endure short-term volatility for long-term transformation.",
        focus_metrics=["revenue_cagr", "r_and_d_spend", "tam_expansion", "adoption_curve"],
        focus_scores=["business", "critical", "sentiment"],
        valuation_approach="Total addressable market expansion. Wright's Law cost curves. 5-year price target based on disruptive potential.",
        risk_tolerance="very high",
        time_horizon="5+ years",
        key_questions=[
            "Is this company riding a disruptive innovation wave?",
            "What is the 5-year revenue potential if disruption succeeds?",
            "Are costs declining on a learning curve (Wright's Law)?",
            "Is the market underestimating the pace of adoption?",
        ],
        deal_breakers=[
            "Incremental innovation, not disruptive",
            "TAM is not expanding",
            "Management lacks vision for transformation",
            "Too much legacy business drag",
        ],
        avatar_emoji="\U0001f680",  # rocket
    ),
    PersonaDefinition(
        name="Rakesh Jhunjhunwala",
        short_id="jhunjhunwala",
        philosophy="India's Warren Buffett. Growth plus value. Back strong management teams in growing industries. Be bullish on the long-term story.",
        focus_metrics=["revenue_cagr", "earnings_growth", "roe", "promoter_holding"],
        focus_scores=["business", "earnings", "leadership"],
        valuation_approach="Reasonable valuation in high-growth context. Willing to pay for growth if management is proven. Industry tailwinds matter.",
        risk_tolerance="moderate-high",
        time_horizon="3-10 years",
        key_questions=[
            "Is this company in a growing industry with secular tailwinds?",
            "Does management have a track record of execution?",
            "Is the valuation reasonable relative to growth?",
            "Will this company be significantly larger in 5 years?",
        ],
        deal_breakers=[
            "Declining industry",
            "Management with poor track record",
            "Overvaluation with no growth to justify it",
            "Corporate governance concerns",
        ],
        avatar_emoji="\U0001f406",  # leopard (bold)
    ),
    PersonaDefinition(
        name="Bill Ackman",
        short_id="ackman",
        philosophy="Activist-minded investor. Focus on free cash flow generative businesses with identifiable catalysts. Simple, predictable, dominant businesses.",
        focus_metrics=["free_cashflow", "fcf_yield", "operating_margin", "market_share"],
        focus_scores=["business", "leadership", "financial"],
        valuation_approach="FCF yield relative to growth. Look for catalysts: management change, restructuring, spin-offs, share buybacks.",
        risk_tolerance="moderate",
        time_horizon="2-5 years",
        key_questions=[
            "Is this a simple, predictable, free-cash-flow generative business?",
            "Is there an identifiable catalyst to unlock value?",
            "Could activist pressure improve operations or capital allocation?",
            "Is the business dominant in its niche?",
        ],
        deal_breakers=[
            "Negative or declining free cash flow",
            "No identifiable catalyst",
            "Management resistant to change with no activist path",
            "Complex conglomerate structure",
        ],
        avatar_emoji="\U0001f3af",  # target
    ),
    PersonaDefinition(
        name="Philip Fisher",
        short_id="fisher",
        philosophy="Scuttlebutt investor. Focus on R&D effectiveness and quality growth. Buy great companies and hold them forever. Management quality is paramount.",
        focus_metrics=["r_and_d_spend", "revenue_cagr", "net_margin_trend", "employee_growth"],
        focus_scores=["business", "leadership"],
        valuation_approach="Willing to pay premium for exceptional quality. Focus on long-term earnings power rather than current valuation ratios.",
        risk_tolerance="low",
        time_horizon="10+ years",
        key_questions=[
            "Does this company have above-average potential for sales growth?",
            "Is R&D effective at producing profitable products?",
            "Does management have integrity and depth?",
            "Is the company doing things competitors cannot easily replicate?",
        ],
        deal_breakers=[
            "Stagnant R&D pipeline",
            "Management focused on short-term metrics",
            "No competitive differentiation",
            "Labor relations problems",
        ],
        avatar_emoji="\U0001f52c",  # microscope (scuttlebutt research)
    ),
]

PERSONA_MAP: Dict[str, PersonaDefinition] = {p.short_id: p for p in ALL_PERSONAS}

# ---------------------------------------------------------------------------
# Narrative Fragility Score
# ---------------------------------------------------------------------------


def compute_narrative_fragility(ticker: str) -> Dict[str, Any]:
    """Compute how vulnerable a stock is to a sentiment-driven price cascade.

    Measures the gap between price behavior and fundamental anchoring.
    A high fragility score means the stock is priced on narrative/momentum
    and is vulnerable to sharp reversals on negative sentiment events.

    Returns:
        Dict with fragility_score (1-10), risk_level, components, and interpretation.
    """
    try:
        import yfinance as yf
    except ImportError:
        return {"fragility_score": None, "error": "yfinance not available"}

    try:
        info = yf.Ticker(ticker).info
    except Exception as e:
        return {"fragility_score": None, "error": str(e)}

    components: Dict[str, Any] = {}
    sub_scores: List[float] = []

    # 1. Extension from 200-day MA — how far has price run from its anchor?
    price = info.get("currentPrice") or info.get("regularMarketPrice", 0)
    ma200 = info.get("twoHundredDayAverage", 0)
    if price and ma200 and ma200 > 0:
        extension_pct = ((price / ma200) - 1) * 100
        components["extension_from_200ma"] = round(extension_pct, 1)
        # >40% = very extended, >20% = extended, <-10% = oversold
        if abs(extension_pct) > 50:
            sub_scores.append(9.0)
        elif abs(extension_pct) > 30:
            sub_scores.append(7.5)
        elif abs(extension_pct) > 15:
            sub_scores.append(5.5)
        else:
            sub_scores.append(3.0)

    # 2. Beta — amplification of market-wide sentiment shifts
    beta = info.get("beta")
    if beta is not None:
        components["beta"] = round(beta, 2)
        if beta > 2.0:
            sub_scores.append(8.5)
        elif beta > 1.5:
            sub_scores.append(7.0)
        elif beta > 1.0:
            sub_scores.append(5.0)
        else:
            sub_scores.append(3.0)

    # 3. Institutional concentration — herd behavior risk
    inst_pct = info.get("heldPercentInstitutions")
    if inst_pct is not None:
        components["institutional_ownership_pct"] = round(inst_pct * 100, 1)
        # >80% = very concentrated, vulnerable to institutional cascades
        if inst_pct > 0.80:
            sub_scores.append(8.0)
        elif inst_pct > 0.65:
            sub_scores.append(6.0)
        elif inst_pct > 0.40:
            sub_scores.append(4.0)
        else:
            sub_scores.append(3.0)

    # 4. Short interest — bearish pressure + squeeze potential
    short_pct = info.get("shortPercentOfFloat")
    short_ratio = info.get("shortRatio")  # days to cover
    if short_pct is not None:
        components["short_percent_of_float"] = round(short_pct * 100, 2)
        components["short_ratio_days"] = short_ratio
        if short_pct > 0.10:
            sub_scores.append(8.0)
        elif short_pct > 0.05:
            sub_scores.append(6.0)
        else:
            sub_scores.append(3.0)

    # 5. Valuation vs fundamentals gap — how much is "hope"?
    pe = info.get("trailingPE") or info.get("forwardPE")
    profit_margin = info.get("profitMargins")
    if pe is not None and profit_margin is not None:
        components["pe_ratio"] = round(pe, 1)
        components["profit_margin"] = round(profit_margin * 100, 1)
        # Negative margins + high P/E = pure narrative pricing
        if profit_margin < 0 and pe > 30:
            sub_scores.append(9.5)
        elif pe > 60:
            sub_scores.append(8.0)
        elif pe > 35:
            sub_scores.append(6.0)
        elif pe > 20:
            sub_scores.append(4.0)
        else:
            sub_scores.append(2.5)

    # 6. Volume deviation — recent volume vs average (narrative shift in progress?)
    avg_vol = info.get("averageVolume", 0)
    vol_10d = info.get("averageVolume10days", 0)
    if avg_vol and vol_10d:
        vol_ratio = vol_10d / avg_vol
        components["volume_10d_vs_avg"] = round(vol_ratio, 2)
        if vol_ratio > 2.0:
            sub_scores.append(8.0)
        elif vol_ratio > 1.3:
            sub_scores.append(6.0)
        else:
            sub_scores.append(3.0)

    if not sub_scores:
        return {"fragility_score": None, "error": "Insufficient data"}

    fragility_score = round(sum(sub_scores) / len(sub_scores), 1)

    # Risk level classification
    if fragility_score >= 7.5:
        risk_level = "very_high"
        interpretation = (
            "Extremely vulnerable to sentiment cascades. Price is driven primarily by "
            "narrative/momentum, not fundamentals. A single negative headline from an "
            "influential voice could trigger a sharp reversal."
        )
    elif fragility_score >= 6.0:
        risk_level = "high"
        interpretation = (
            "Significantly vulnerable to narrative shifts. Price has run ahead of fundamentals. "
            "Institutional herding and momentum amplify both up and down moves."
        )
    elif fragility_score >= 4.5:
        risk_level = "moderate"
        interpretation = (
            "Moderate narrative risk. Price is somewhat extended but has fundamental support. "
            "Would need a significant catalyst to trigger a cascade."
        )
    else:
        risk_level = "low"
        interpretation = (
            "Well-anchored to fundamentals. Low vulnerability to sentiment-driven cascades. "
            "Price is near historical averages with balanced positioning."
        )

    return {
        "fragility_score": fragility_score,
        "risk_level": risk_level,
        "interpretation": interpretation,
        "components": components,
    }


# ---------------------------------------------------------------------------
# 1c. Forward P/E reliability
# ---------------------------------------------------------------------------


def compute_forward_pe_reliability(
    trailing_pe: Optional[float],
    forward_pe: Optional[float],
    revenue_growth_yoy: Optional[float],
    earnings_inputs: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Cross-reference forward P/E vs trailing P/E to assess reliability.

    Returns a dict with trailing_pe, forward_pe, implied_earnings_growth,
    reliability ('credible' | 'moderate' | 'skeptical'), divergence_pct, and notes.
    """
    result: Dict[str, Any] = {
        "trailing_pe": trailing_pe,
        "forward_pe": forward_pe,
        "implied_earnings_growth": None,
        "reliability": "moderate",
        "divergence_pct": None,
        "notes": [],
    }

    if not trailing_pe or trailing_pe <= 0 or not forward_pe or forward_pe <= 0:
        result["notes"].append("Insufficient P/E data for cross-referencing.")
        return result

    implied_earnings_growth = (trailing_pe / forward_pe - 1) * 100
    result["implied_earnings_growth"] = round(implied_earnings_growth, 2)

    divergence_pct = abs(trailing_pe - forward_pe) / trailing_pe * 100
    result["divergence_pct"] = round(divergence_pct, 2)

    notes: List[str] = []

    # Compare implied earnings growth against revenue growth
    if revenue_growth_yoy is not None:
        growth_gap = implied_earnings_growth - revenue_growth_yoy
        if growth_gap > 30:
            notes.append(
                f"Implied earnings growth ({implied_earnings_growth:.1f}%) far exceeds "
                f"revenue growth ({revenue_growth_yoy:.1f}%) — aggressive margin expansion assumed."
            )
            result["reliability"] = "skeptical"
        elif growth_gap > 10:
            notes.append(
                f"Implied earnings growth ({implied_earnings_growth:.1f}%) moderately exceeds "
                f"revenue growth ({revenue_growth_yoy:.1f}%) — some margin expansion priced in."
            )
            result["reliability"] = "moderate"
        else:
            notes.append(
                f"Implied earnings growth ({implied_earnings_growth:.1f}%) is consistent "
                f"with revenue growth ({revenue_growth_yoy:.1f}%)."
            )
            result["reliability"] = "credible"
    else:
        notes.append("Revenue growth unavailable; reliability based on P/E divergence only.")
        if divergence_pct > 40:
            result["reliability"] = "skeptical"
        elif divergence_pct > 20:
            result["reliability"] = "moderate"
        else:
            result["reliability"] = "credible"

    # Additional checks from earnings_inputs
    if earnings_inputs:
        beat_rate = earnings_inputs.get("beat_rate")
        if beat_rate is not None and beat_rate < 0.5:
            notes.append(
                f"Company beats estimates only {beat_rate*100:.0f}% of the time — forward estimates may be optimistic."
            )
            if result["reliability"] == "credible":
                result["reliability"] = "moderate"

    if implied_earnings_growth > 50:
        notes.append("Forward P/E implies >50% earnings growth — very aggressive assumption.")
    elif implied_earnings_growth < -20:
        notes.append("Forward P/E implies earnings decline — negative outlook priced in.")

    result["notes"] = notes
    return result


# ---------------------------------------------------------------------------
# 1d. Extract persona context from scores data
# ---------------------------------------------------------------------------


def extract_persona_context(
    scores_data: Dict[str, Any],
    persona: PersonaDefinition,
    strategic_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Extract the subset of scores_data that a specific persona cares about.

    Args:
        scores_data: Full output from compute_company_scores().
        persona: The persona definition to extract context for.
        strategic_context: Optional user-supplied strategic/geopolitical context
            that the scoring engine may not capture (e.g. government subsidies,
            regulatory developments, macro-industrial policy).
    """
    context: Dict[str, Any] = {
        "ticker": scores_data.get("company", {}).get("ticker", "UNKNOWN"),
        "company_name": scores_data.get("company", {}).get("name", "Unknown Company"),
    }

    # Quick facts
    quick_facts = scores_data.get("quick_facts", {})
    context["quick_facts"] = quick_facts

    # Focused scores
    all_scores = scores_data.get("scores", {})
    context["focused_scores"] = {}
    for score_key in persona.focus_scores:
        if score_key in all_scores:
            score_obj = all_scores[score_key]
            if hasattr(score_obj, "__dict__"):
                context["focused_scores"][score_key] = {
                    "score": getattr(score_obj, "score", None),
                    "summary": getattr(score_obj, "summary", ""),
                    "inputs": getattr(score_obj, "inputs", {}),
                    "notes": getattr(score_obj, "notes", []),
                }
            elif isinstance(score_obj, dict):
                context["focused_scores"][score_key] = score_obj
            else:
                context["focused_scores"][score_key] = {"score": score_obj}

    # Overall score
    context["overall"] = scores_data.get("overall", {})

    # Recommendation
    recommendation = scores_data.get("recommendation", {})
    context["recommendation"] = {
        "recommendation": recommendation.get("recommendation"),
        "strengths": recommendation.get("strengths", []),
        "weaknesses": recommendation.get("weaknesses", []),
        "risks": recommendation.get("risks", []),
        "action": recommendation.get("action"),
    }

    # Industry comparison
    context["industry_comparison"] = scores_data.get("industry_comparison", {})

    # Event timeline / recent news
    timeline = scores_data.get("event_timeline", [])
    if timeline:
        context["recent_events"] = [
            {
                "title": e.get("title", ""),
                "source": e.get("source", ""),
                "sentiment": e.get("sentiment"),
                "published_at": e.get("published_at", ""),
            }
            for e in timeline[:10]
        ]

    # Price trend context (1-year performance)
    price_history = scores_data.get("price_history", {})
    if price_history:
        context["price_trend"] = {
            "period_return": price_history.get("period_return"),
            "current_price": price_history.get("current_price"),
            "period_high": price_history.get("period_high"),
            "period_low": price_history.get("period_low"),
        }

    # Strategic / geopolitical context (user-supplied)
    if strategic_context:
        context["strategic_context"] = strategic_context

    # Narrative fragility — how vulnerable to sentiment cascades
    context["narrative_fragility"] = compute_narrative_fragility(context["ticker"])

    # Forward P/E reliability analysis
    trailing_pe = quick_facts.get("pe_ratio") or quick_facts.get("trailing_pe")
    forward_pe = quick_facts.get("forward_pe")
    revenue_growth = quick_facts.get("revenue_growth_yoy")
    financial_inputs = {}
    if "financial" in all_scores:
        fin = all_scores["financial"]
        if hasattr(fin, "inputs"):
            financial_inputs = fin.inputs if hasattr(fin.inputs, "__iter__") else {}
        elif isinstance(fin, dict):
            financial_inputs = fin.get("inputs", {})
    context["forward_pe_analysis"] = compute_forward_pe_reliability(
        trailing_pe, forward_pe, revenue_growth, financial_inputs
    )

    return context


# ---------------------------------------------------------------------------
# 1e. Build prompt for persona
# ---------------------------------------------------------------------------


def build_persona_prompt(persona: PersonaDefinition, context: Dict[str, Any]) -> tuple:
    """Build system and user prompts for Claude analysis.

    Returns (system_prompt, user_message).
    """
    system_prompt = f"""You are {persona.name}, the legendary investor. You will analyze a stock
strictly through the lens of your investment philosophy.

YOUR PHILOSOPHY: {persona.philosophy}

YOUR VALUATION APPROACH: {persona.valuation_approach}

YOUR RISK TOLERANCE: {persona.risk_tolerance}
YOUR TIME HORIZON: {persona.time_horizon}

KEY QUESTIONS YOU ALWAYS ASK:
{chr(10).join(f'- {q}' for q in persona.key_questions)}

YOUR DEAL BREAKERS:
{chr(10).join(f'- {d}' for d in persona.deal_breakers)}

You MUST respond with valid JSON only. No markdown, no code fences, no explanation outside the JSON.
The JSON must have exactly these keys:
{{
    "recommendation": "Strong Buy" | "Buy" | "Hold" | "Sell" | "Strong Sell",
    "conviction": <integer 1-10>,
    "reasoning": "<2-4 sentences explaining your view as {persona.name}>",
    "key_metrics_highlighted": ["<metric1>", "<metric2>", ...],
    "bull_case": "<1-2 sentences>",
    "bear_case": "<1-2 sentences>",
    "would_buy_at": "<price level or condition, e.g. '20% lower' or 'current price is fair'>"
}}"""

    # Build optional context sections
    optional_sections = ""

    recent_events = context.get("recent_events")
    if recent_events:
        optional_sections += f"""
RECENT NEWS & EVENTS:
{json.dumps(recent_events, indent=2, default=str)}
"""

    price_trend = context.get("price_trend")
    if price_trend:
        optional_sections += f"""
PRICE TREND:
{json.dumps(price_trend, indent=2, default=str)}
"""

    fragility = context.get("narrative_fragility")
    if fragility and fragility.get("fragility_score") is not None:
        optional_sections += f"""
NARRATIVE FRAGILITY ANALYSIS (how vulnerable is this stock to sentiment cascades):
{json.dumps(fragility, indent=2, default=str)}
Remember: "The market can stay irrational longer than you can stay solvent." Consider how a single
negative headline, influential investor comment, or macro shock could trigger a cascade regardless
of fundamentals. Factor this into your conviction level and entry price.
"""

    strategic = context.get("strategic_context")
    if strategic:
        optional_sections += f"""
STRATEGIC & GEOPOLITICAL CONTEXT (important — factor this into your analysis):
{strategic}
"""

    user_message = f"""Analyze {context['ticker']} ({context['company_name']}) with the following data:

QUICK FACTS:
{json.dumps(context.get('quick_facts', {}), indent=2, default=str)}

FOCUSED SCORES (the categories you care about most):
{json.dumps(context.get('focused_scores', {}), indent=2, default=str)}

OVERALL SCORE: {json.dumps(context.get('overall', {}), indent=2, default=str)}

RECOMMENDATION (from the scoring engine):
{json.dumps(context.get('recommendation', {}), indent=2, default=str)}

INDUSTRY COMPARISON:
{json.dumps(context.get('industry_comparison', {}), indent=2, default=str)}

FORWARD P/E ANALYSIS:
{json.dumps(context.get('forward_pe_analysis', {}), indent=2, default=str)}
{optional_sections}
As {persona.name}, what is your verdict on {context['ticker']}?"""

    return system_prompt, user_message


# ---------------------------------------------------------------------------
# 1f. Analyze single persona
# ---------------------------------------------------------------------------


def analyze_single_persona(
    persona: PersonaDefinition,
    scores_data: Dict[str, Any],
    strategic_context: Optional[str] = None,
) -> PersonaVerdict:
    """Run a single persona analysis using Claude Opus 4.6.

    Returns a PersonaVerdict. On failure, returns a fallback verdict.
    """
    try:
        client = _get_client()
        context = extract_persona_context(scores_data, persona, strategic_context)
        system_prompt, user_message = build_persona_prompt(persona, context)

        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}],
        )

        raw_text = response.content[0].text.strip()
        # Try to parse JSON (handle possible markdown code fences)
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        parsed = json.loads(raw_text)

        return PersonaVerdict(
            persona_id=persona.short_id,
            persona_name=persona.name,
            recommendation=parsed.get("recommendation", "Hold"),
            conviction=max(1, min(10, int(parsed.get("conviction", 5)))),
            reasoning=parsed.get("reasoning", ""),
            key_metrics_highlighted=parsed.get("key_metrics_highlighted", []),
            bull_case=parsed.get("bull_case", ""),
            bear_case=parsed.get("bear_case", ""),
            would_buy_at=parsed.get("would_buy_at", "N/A"),
            avatar_emoji=persona.avatar_emoji,
        )
    except Exception as e:
        logger.error("Persona %s analysis failed: %s", persona.short_id, e)
        return PersonaVerdict(
            persona_id=persona.short_id,
            persona_name=persona.name,
            recommendation="Hold",
            conviction=3,
            reasoning=f"Analysis unavailable due to error: {str(e)[:120]}",
            key_metrics_highlighted=[],
            bull_case="Unable to assess",
            bear_case="Unable to assess",
            would_buy_at="N/A",
            avatar_emoji=persona.avatar_emoji,
        )


# ---------------------------------------------------------------------------
# 1g. Analyze all personas (parallel)
# ---------------------------------------------------------------------------


def analyze_all_personas(
    scores_data: Dict[str, Any],
    persona_ids: Optional[List[str]] = None,
    max_workers: int = 4,
    strategic_context: Optional[str] = None,
) -> Dict[str, Any]:
    """Run all (or selected) persona analyses in parallel.

    Args:
        scores_data: Output from compute_company_scores().
        persona_ids: Optional list of persona short_ids to run. None = all 12.
        max_workers: Thread pool size (4 to respect Anthropic rate limits).
        strategic_context: Optional user-supplied geopolitical/strategic context
            (e.g. government subsidies, regulatory tailwinds, national security value).

    Returns:
        Dict with ticker, personas list, summary, and generated_at.
    """
    if persona_ids:
        personas_to_run = [PERSONA_MAP[pid] for pid in persona_ids if pid in PERSONA_MAP]
    else:
        personas_to_run = ALL_PERSONAS

    if not personas_to_run:
        return {
            "ticker": scores_data.get("company", {}).get("ticker", "UNKNOWN"),
            "personas": [],
            "summary": {},
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    verdicts: List[PersonaVerdict] = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_persona = {
            executor.submit(analyze_single_persona, persona, scores_data, strategic_context): persona
            for persona in personas_to_run
        }
        for future in as_completed(future_to_persona):
            verdicts.append(future.result())

    # Sort by persona order in ALL_PERSONAS
    id_order = {p.short_id: i for i, p in enumerate(ALL_PERSONAS)}
    verdicts.sort(key=lambda v: id_order.get(v.persona_id, 99))

    # Compute summary
    buy_count = sum(1 for v in verdicts if v.recommendation in ("Strong Buy", "Buy"))
    sell_count = sum(1 for v in verdicts if v.recommendation in ("Strong Sell", "Sell"))
    hold_count = sum(1 for v in verdicts if v.recommendation == "Hold")
    avg_conviction = round(sum(v.conviction for v in verdicts) / len(verdicts), 1) if verdicts else 0

    if buy_count > sell_count and buy_count > hold_count:
        consensus = "Bullish"
    elif sell_count > buy_count and sell_count > hold_count:
        consensus = "Bearish"
    else:
        consensus = "Mixed"

    return {
        "ticker": scores_data.get("company", {}).get("ticker", "UNKNOWN"),
        "personas": [asdict(v) for v in verdicts],
        "summary": {
            "buy_count": buy_count,
            "sell_count": sell_count,
            "hold_count": hold_count,
            "average_conviction": avg_conviction,
            "consensus": consensus,
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# 1h. Reconciliation
# ---------------------------------------------------------------------------

_DEFAULT_RECONCILIATION_TEMPLATE = """You are the Chief Investment Officer presiding over an investment committee
of 12 legendary investors. Each has independently analyzed {ticker} and provided their verdict.

COMPANY FINANCIALS:
{financial_summary}

{strategic_context_section}

PERSONA VERDICTS (full reasoning):
{persona_summaries}

VOTE TALLY: {consensus} (Buy: {buy_count}, Hold: {hold_count}, Sell: {sell_count})
AVERAGE CONVICTION: {avg_conviction}/10
OVERALL SCORING ENGINE SCORE: {overall_score}

As CIO, synthesize these perspectives into a single committee recommendation.
- Consider where the investors agree and disagree, and WHY
- Weight higher-conviction views more heavily
- Account for both quantitative fundamentals AND qualitative/strategic factors
- If there is strategic context (government investment, geopolitical factors), weigh it appropriately

Respond with valid JSON only:
{{
    "committee_recommendation": "Strong Buy" | "Buy" | "Hold" | "Sell" | "Strong Sell",
    "committee_conviction": <integer 1-10>,
    "synthesis": "<3-5 sentence synthesis of the committee discussion>",
    "key_agreement": "<1-2 sentences on what most investors agree on>",
    "key_disagreement": "<1-2 sentences on the main point of contention>",
    "final_verdict": "<2-3 sentence final verdict as CIO>"
}}"""


def run_reconciliation(
    persona_results: Dict[str, Any],
    scores_data: Dict[str, Any],
    custom_prompt: Optional[str] = None,
) -> Dict[str, Any]:
    """Reconcile all persona verdicts into a committee recommendation.

    Args:
        persona_results: Output from analyze_all_personas().
        scores_data: Output from compute_company_scores().
        custom_prompt: Optional format string template overriding the default.

    Returns:
        Dict with committee_recommendation, committee_conviction, synthesis, etc.
    """
    ticker = persona_results.get("ticker", "UNKNOWN")
    summary = persona_results.get("summary", {})
    personas = persona_results.get("personas", [])

    # Build full persona summaries — include reasoning, bull/bear, key metrics
    persona_lines = []
    for p in personas:
        line = (
            f"- {p['persona_name']} ({p['avatar_emoji']}): {p['recommendation']} "
            f"(conviction {p['conviction']}/10)\n"
            f"  Reasoning: {p['reasoning']}\n"
            f"  Bull case: {p.get('bull_case', 'N/A')}\n"
            f"  Bear case: {p.get('bear_case', 'N/A')}\n"
            f"  Would buy at: {p.get('would_buy_at', 'N/A')}"
        )
        metrics = p.get("key_metrics_highlighted", [])
        if metrics:
            line += f"\n  Key metrics: {', '.join(metrics)}"
        persona_lines.append(line)
    persona_summaries = "\n\n".join(persona_lines)

    # Build financial summary for CIO context
    quick_facts = scores_data.get("quick_facts", {})
    recommendation = scores_data.get("recommendation", {})
    financial_summary_parts = []
    for label, key in [
        ("Revenue (TTM)", "revenue_ttm"),
        ("Profit Margin", "profit_margin"),
        ("P/E Ratio", "pe_ratio"),
        ("Forward P/E", "forward_pe"),
        ("PEG Ratio", "peg_ratio"),
        ("P/B Ratio", "price_to_book"),
        ("Beta", "beta"),
        ("Market Cap", "market_cap"),
        ("Sector", "sector"),
        ("Industry", "industry"),
    ]:
        val = quick_facts.get(key)
        if val is not None:
            if key == "profit_margin":
                financial_summary_parts.append(f"  {label}: {val:.1f}%")
            elif key in ("revenue_ttm", "market_cap"):
                if isinstance(val, (int, float)) and val > 1e9:
                    financial_summary_parts.append(f"  {label}: ${val/1e9:.1f}B")
                else:
                    financial_summary_parts.append(f"  {label}: {val}")
            else:
                financial_summary_parts.append(f"  {label}: {val}")
    strengths = recommendation.get("strengths", [])
    weaknesses = recommendation.get("weaknesses", [])
    risks = recommendation.get("risks", [])
    if strengths:
        financial_summary_parts.append(f"  Strengths: {'; '.join(strengths[:3])}")
    if weaknesses:
        financial_summary_parts.append(f"  Weaknesses: {'; '.join(weaknesses[:3])}")
    if risks:
        financial_summary_parts.append(f"  Key Risks: {'; '.join(risks[:3])}")
    financial_summary = "\n".join(financial_summary_parts) if financial_summary_parts else "Not available"

    # Include strategic context if personas had it
    strategic_context_section = ""
    # Check if any persona verdict mentions strategic themes (heuristic)
    all_reasoning = " ".join(p.get("reasoning", "") for p in personas)
    if any(kw in all_reasoning.lower() for kw in ["chips act", "national security", "government", "geopolitical", "strategic"]):
        strategic_context_section = (
            "NOTE: Strategic/geopolitical factors were provided to the committee members. "
            "Their verdicts already incorporate this context. Weigh both financial fundamentals "
            "and strategic considerations in your synthesis."
        )

    overall_score = scores_data.get("overall", {})
    if isinstance(overall_score, dict):
        overall_score_val = overall_score.get("score", "N/A")
    elif hasattr(overall_score, "score"):
        overall_score_val = overall_score.score
    else:
        overall_score_val = overall_score

    template = custom_prompt or _DEFAULT_RECONCILIATION_TEMPLATE
    prompt_text = template.format(
        ticker=ticker,
        financial_summary=financial_summary,
        strategic_context_section=strategic_context_section,
        persona_summaries=persona_summaries,
        consensus=summary.get("consensus", "Mixed"),
        buy_count=summary.get("buy_count", 0),
        hold_count=summary.get("hold_count", 0),
        sell_count=summary.get("sell_count", 0),
        avg_conviction=summary.get("average_conviction", 0),
        overall_score=overall_score_val,
    )

    try:
        client = _get_client()
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt_text}],
        )
        raw_text = response.content[0].text.strip()
        if raw_text.startswith("```"):
            raw_text = raw_text.split("```")[1]
            if raw_text.startswith("json"):
                raw_text = raw_text[4:]
            raw_text = raw_text.strip()
        return json.loads(raw_text)
    except Exception as e:
        logger.error("Reconciliation failed: %s", e)
        return {
            "committee_recommendation": summary.get("consensus", "Hold"),
            "committee_conviction": int(summary.get("average_conviction", 5)),
            "synthesis": f"Reconciliation unavailable due to error: {str(e)[:120]}",
            "key_agreement": "Unable to determine",
            "key_disagreement": "Unable to determine",
            "final_verdict": "Committee analysis unavailable. Refer to individual persona verdicts.",
        }
