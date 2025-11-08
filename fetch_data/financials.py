import os
import json
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime
from typing import Dict, List, Any, Optional
from .utils import retry_on_failure, FINANCIALS_DIR, EARNINGS_DIR

logger = logging.getLogger(__name__)

def _clean_numeric(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        if isinstance(value, (int, float)):
            if pd.isna(value):
                return None
            return float(value)
        if isinstance(value, str):
            value = value.strip().replace(',', '')
            if not value:
                return None
            return float(value)
    except (ValueError, TypeError):
        return None
    return None

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_quarterly_earnings(ticker: str) -> List[Dict[str, Any]]:
    logger.info(f"Fetching quarterly earnings for {ticker}...")
    records: List[Dict[str, Any]] = []

    try:
        stock = yf.Ticker(ticker)
        quarterly_earnings = stock.quarterly_earnings
        quarterly_financials = stock.quarterly_financials

        financials_lookup = {}
        if quarterly_financials is not None and not quarterly_financials.empty:
            normalized_financials = quarterly_financials.copy()
            normalized_financials.columns = normalized_financials.columns.map(lambda c: str(c))
            for label in normalized_financials.index:
                financials_lookup[label] = normalized_financials.loc[label].to_dict()

        if quarterly_earnings is not None and not quarterly_earnings.empty:
            quarterly_earnings = quarterly_earnings.head(4)
            quarterly_earnings.index = quarterly_earnings.index.map(lambda idx: str(idx))
            for period, row in quarterly_earnings.iterrows():
                record = {
                    "ticker": ticker,
                    "period": period,
                    "revenue": _clean_numeric(row.get("Revenue")),
                    "earnings": _clean_numeric(row.get("Earnings")),
                    "net_income": None,
                    "eps": None,
                }

                if financials_lookup:
                    potential_keys = {
                        "net_income": ["Net Income", "NetIncome", "Net Income Applicable To Common Shares"],
                        "eps": ["Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"]
                    }
                    for target_key, candidates in potential_keys.items():
                        for candidate in candidates:
                            values = financials_lookup.get(candidate)
                            if values and period in values:
                                value = _clean_numeric(values[period])
                                if value is not None:
                                    record[target_key] = value
                                    break

                records.append(record)
        elif quarterly_financials is not None and not quarterly_financials.empty:
            logger.info(f"Quarterly earnings not available for {ticker}; falling back to quarterly financials.")
            normalized_financials = quarterly_financials.copy()
            normalized_financials.columns = normalized_financials.columns.map(lambda c: str(c))
            target_columns = list(normalized_financials.columns)[:4]

            for period in target_columns:
                record = {
                    "ticker": ticker,
                    "period": period,
                    "revenue": None,
                    "earnings": None,
                    "net_income": None,
                    "eps": None,
                }

                revenue_candidates = ["Total Revenue", "TotalRevenue", "Revenue"]
                earnings_candidates = ["Gross Profit", "Operating Income"]
                net_income_candidates = ["Net Income", "NetIncome", "Net Income Applicable To Common Shares"]
                eps_candidates = ["Diluted EPS", "Basic EPS", "DilutedEPS", "BasicEPS"]

                for candidate in revenue_candidates:
                    if candidate in normalized_financials.index:
                        record["revenue"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break
                for candidate in earnings_candidates:
                    if candidate in normalized_financials.index:
                        record["earnings"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break
                for candidate in net_income_candidates:
                    if candidate in normalized_financials.index:
                        record["net_income"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break
                for candidate in eps_candidates:
                    if candidate in normalized_financials.index:
                        record["eps"] = _clean_numeric(normalized_financials.loc[candidate, period])
                        break

                records.append(record)
        else:
            logger.warning(f"No quarterly earnings or financial data found for {ticker}")

        if records:
            output_path = os.path.join(EARNINGS_DIR, f"{ticker}_quarterly_earnings.json")
            with open(output_path, 'w') as f:
                json.dump(records, f, indent=2)
            logger.info(f"✅ Saved quarterly earnings for {ticker} to {output_path}")

        return records
    except Exception as exc:
        logger.error(f"Error fetching quarterly earnings for {ticker}: {exc}")
        return []

def fetch_financial_statements(ticker: str):
    logger.info(f"Fetching financial statements for {ticker}...")

    try:
        stock = yf.Ticker(ticker)
        financials_data = {
            "ticker": ticker,
            "fetch_date": datetime.now().isoformat(),
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow": {},
            "quarterly_income_statement": {},
            "quarterly_balance_sheet": {},
            "quarterly_cash_flow": {},
            "key_metrics": {}
        }

        def df_to_json_dict(df):
            if df is None or df.empty:
                return {}
            df_copy = df.copy()
            df_copy.columns = df_copy.columns.map(str)
            return df_copy.to_dict()

        if hasattr(stock, 'financials') and stock.financials is not None and not stock.financials.empty:
            financials_data["income_statement"] = df_to_json_dict(stock.financials)

        if hasattr(stock, 'balance_sheet') and stock.balance_sheet is not None and not stock.balance_sheet.empty:
            financials_data["balance_sheet"] = df_to_json_dict(stock.balance_sheet)

        if hasattr(stock, 'cashflow') and stock.cashflow is not None and not stock.cashflow.empty:
            financials_data["cash_flow"] = df_to_json_dict(stock.cashflow)

        if hasattr(stock, 'quarterly_financials') and stock.quarterly_financials is not None and not stock.quarterly_financials.empty:
            financials_data["quarterly_income_statement"] = df_to_json_dict(stock.quarterly_financials)

        if hasattr(stock, 'quarterly_balance_sheet') and stock.quarterly_balance_sheet is not None and not stock.quarterly_balance_sheet.empty:
            financials_data["quarterly_balance_sheet"] = df_to_json_dict(stock.quarterly_balance_sheet)

        if hasattr(stock, 'quarterly_cashflow') and stock.quarterly_cashflow is not None and not stock.quarterly_cashflow.empty:
            financials_data["quarterly_cash_flow"] = df_to_json_dict(stock.quarterly_cashflow)

        info = stock.info
        financials_data["key_metrics"] = {
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "price_to_sales": info.get("priceToSalesTrailing12Months"),
            "forward_ps": info.get("forwardPS"),  # Add forward P/S
            "profit_margins": info.get("profitMargins"),
            "operating_margins": info.get("operatingMargins"),
            "roe": info.get("returnOnEquity"),
            "roa": info.get("returnOnAssets"),
            "revenue_growth": info.get("revenueGrowth"),
            "earnings_growth": info.get("earningsGrowth"),
            "current_ratio": info.get("currentRatio"),
            "quick_ratio": info.get("quickRatio"),
            "debt_to_equity": info.get("debtToEquity"),
            "total_cash": info.get("totalCash"),
            "total_debt": info.get("totalDebt"),
            "free_cash_flow": info.get("freeCashflow"),
            "operating_cash_flow": info.get("operatingCashflow"),
            "revenue": info.get("totalRevenue"),
            "ebitda": info.get("ebitda"),
            "gross_profits": info.get("grossProfits"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
        }

        output_file = os.path.join(FINANCIALS_DIR, f"{ticker}_financials.json")
        with open(output_file, 'w') as f:
            json.dump(financials_data, f, indent=2, default=str)

        logger.info(f"✅ Saved financial statements for {ticker}")

    except Exception as e:
        logger.error(f"Failed to fetch financials for {ticker}: {e}")
