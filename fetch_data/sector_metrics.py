import os
import json
import logging
import time
import numpy as np
import pandas as pd
import yfinance as yf
from .utils import retry_on_failure, SECTOR_METRICS_DIR, COMPANIES_CSV_PATH

logger = logging.getLogger(__name__)

def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    if len(prices) < period + 1:
        return None
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1] if not pd.isna(rsi.iloc[-1]) else None

def calculate_macd(prices: pd.Series) -> dict:
    if len(prices) < 26:
        return {'macd': None, 'signal': None, 'histogram': None}
    exp1 = prices.ewm(span=12, adjust=False).mean()
    exp2 = prices.ewm(span=26, adjust=False).mean()
    macd = exp1 - exp2
    signal = macd.ewm(span=9, adjust=False).mean()
    histogram = macd - signal
    return {
        'macd': macd.iloc[-1] if not pd.isna(macd.iloc[-1]) else None,
        'signal': signal.iloc[-1] if not pd.isna(signal.iloc[-1]) else None,
        'histogram': histogram.iloc[-1] if not pd.isna(histogram.iloc[-1]) else None
    }

def calculate_cagr(prices: pd.Series) -> float:
    if len(prices) < 2:
        return None
    start_value = prices.iloc[0]
    end_value = prices.iloc[-1]
    if start_value <= 0 or end_value <= 0:
        return None
    years = len(prices) / 252
    if years <= 0:
        return None
    cagr = (pow(end_value / start_value, 1 / years) - 1) * 100
    return cagr

def calculate_volatility(prices: pd.Series, period: int = 252) -> float:
    if len(prices) < 2:
        return None
    returns = prices.pct_change().dropna()
    if len(returns) == 0:
        return None
    volatility = returns.std() * np.sqrt(period)
    return volatility * 100

def calculate_beta(prices: pd.Series, market_prices: pd.Series) -> float:
    if len(prices) < 2 or len(market_prices) < 2:
        return None
    aligned = pd.DataFrame({'stock': prices, 'market': market_prices}).dropna()
    if len(aligned) < 2:
        return None
    stock_returns = aligned['stock'].pct_change().dropna()
    market_returns = aligned['market'].pct_change().dropna()
    if len(stock_returns) < 2 or len(market_returns) < 2:
        return None
    covariance = np.cov(stock_returns, market_returns)[0, 1]
    market_variance = np.var(market_returns)
    if market_variance == 0:
        return None
    beta = covariance / market_variance
    return beta

def calculate_sharpe_ratio(prices: pd.Series, risk_free_rate: float = 0.04) -> float:
    if len(prices) < 2:
        return None
    returns = prices.pct_change().dropna()
    if len(returns) == 0:
        return None
    total_return = (prices.iloc[-1] / prices.iloc[0]) - 1
    years = len(prices) / 252
    annualized_return = (pow(1 + total_return, 1 / years) - 1) if years > 0 else 0
    volatility = returns.std() * np.sqrt(252)
    if volatility == 0:
        return None
    sharpe = (annualized_return - risk_free_rate) / volatility
    return sharpe

def calculate_momentum_score(prices: pd.Series) -> dict:
    if len(prices) < 2:
        return {'1m': None, '3m': None, '6m': None, '1y': None}
    momentum = {}
    if len(prices) >= 21:
        momentum['1m'] = ((prices.iloc[-1] / prices.iloc[-21]) - 1) * 100
    else:
        momentum['1m'] = None
    if len(prices) >= 63:
        momentum['3m'] = ((prices.iloc[-1] / prices.iloc[-63]) - 1) * 100
    else:
        momentum['3m'] = None
    if len(prices) >= 126:
        momentum['6m'] = ((prices.iloc[-1] / prices.iloc[-126]) - 1) * 100
    else:
        momentum['6m'] = None
    momentum['1y'] = ((prices.iloc[-1] / prices.iloc[0]) - 1) * 100
    return momentum

def get_company_metrics(ticker: str, market_prices: pd.Series = None) -> dict:
    metrics = {
        'ticker': ticker,
        'sector': None,
        'industry': None,
        'market_cap': None,
        'revenue': None,
        'gross_margin': None,
        'net_margin': None,
        'free_cash_flow': None,
        'eps': None,
        'pe_ratio': None,
        'ps_ratio': None,
        'pb_ratio': None,
        'rsi': None,
        'macd': None,
        'macd_signal': None,
        'macd_histogram': None,
        'cagr': None,
        'volatility': None,
        'beta': None,
        'sharpe_ratio': None,
        'momentum_1m': None,
        'momentum_3m': None,
        'momentum_6m': None,
        'momentum_1y': None,
        'roe': None,
        'roa': None,
        'roic': None,
        'debt_to_equity': None,
        'current_ratio': None,
        'quick_ratio': None,
        'interest_coverage': None,
        'error': None
    }
    try:
        stock = yf.Ticker(ticker)
        info = stock.info
        metrics['sector'] = info.get('sector', 'Unknown')
        metrics['industry'] = info.get('industry', 'Unknown')
        metrics['market_cap'] = info.get('marketCap')
        metrics['pe_ratio'] = info.get('trailingPE') or info.get('forwardPE')
        metrics['ps_ratio'] = info.get('priceToSalesTrailing12Months')
        metrics['pb_ratio'] = info.get('priceToBook')
        metrics['eps'] = info.get('trailingEps') or info.get('forwardEps')
        metrics['roe'] = info.get('returnOnEquity')
        if metrics['roe']:
            metrics['roe'] = metrics['roe'] * 100
        metrics['roa'] = info.get('returnOnAssets')
        if metrics['roa']:
            metrics['roa'] = metrics['roa'] * 100
        metrics['debt_to_equity'] = info.get('debtToEquity')
        metrics['current_ratio'] = info.get('currentRatio')
        metrics['quick_ratio'] = info.get('quickRatio')
        financials = stock.financials
        if not financials.empty:
            if 'Total Revenue' in financials.index:
                metrics['revenue'] = financials.loc['Total Revenue'].iloc[0]
            if 'Gross Profit' in financials.index and 'Total Revenue' in financials.index:
                gross_profit = financials.loc['Gross Profit'].iloc[0]
                revenue = financials.loc['Total Revenue'].iloc[0]
                if revenue and revenue != 0:
                    metrics['gross_margin'] = (gross_profit / revenue) * 100
            if 'Net Income' in financials.index and 'Total Revenue' in financials.index:
                net_income = financials.loc['Net Income'].iloc[0]
                revenue = financials.loc['Total Revenue'].iloc[0]
                if revenue and revenue != 0:
                    metrics['net_margin'] = (net_income / revenue) * 100
        if not financials.empty:
            if 'EBIT' in financials.index and 'Interest Expense' in financials.index:
                ebit = financials.loc['EBIT'].iloc[0]
                interest_expense = financials.loc['Interest Expense'].iloc[0]
                if interest_expense and interest_expense != 0:
                    metrics['interest_coverage'] = ebit / abs(interest_expense)
        balance_sheet = stock.balance_sheet
        if not balance_sheet.empty and not financials.empty:
            tax_rate = 0.21
            if 'Tax Provision' in financials.index and 'Pretax Income' in financials.index:
                tax_provision = financials.loc['Tax Provision'].iloc[0]
                pretax_income = financials.loc['Pretax Income'].iloc[0]
                if pretax_income and pretax_income != 0:
                    tax_rate = tax_provision / pretax_income
            net_income = financials.loc['Net Income'].iloc[0] if 'Net Income' in financials.index else 0
            interest_expense = financials.loc['Interest Expense'].iloc[0] if 'Interest Expense' in financials.index else 0
            nopat = net_income + interest_expense * (1 - tax_rate)
            total_debt = balance_sheet.loc['Total Debt'].iloc[0] if 'Total Debt' in balance_sheet.index else 0
            total_equity = balance_sheet.loc['Total Equity Gross Minority Interest'].iloc[0] if 'Total Equity Gross Minority Interest' in balance_sheet.index else 0
            invested_capital = total_debt + total_equity
            if invested_capital and invested_capital != 0:
                metrics['roic'] = (nopat / invested_capital) * 100
        cashflow = stock.cashflow
        if not cashflow.empty:
            if 'Free Cash Flow' in cashflow.index:
                metrics['free_cash_flow'] = cashflow.loc['Free Cash Flow'].iloc[0]
        hist = stock.history(period="1y")
        if not hist.empty:
            prices = hist['Close']
            metrics['rsi'] = calculate_rsi(prices)
            macd_data = calculate_macd(prices)
            metrics['macd'] = macd_data['macd']
            metrics['macd_signal'] = macd_data['signal']
            metrics['macd_histogram'] = macd_data['histogram']
            metrics['cagr'] = calculate_cagr(prices)
            metrics['volatility'] = calculate_volatility(prices)
            metrics['sharpe_ratio'] = calculate_sharpe_ratio(prices)
            momentum = calculate_momentum_score(prices)
            metrics['momentum_1m'] = momentum['1m']
            metrics['momentum_3m'] = momentum['3m']
            metrics['momentum_6m'] = momentum['6m']
            metrics['momentum_1y'] = momentum['1y']
            if market_prices is not None:
                metrics['beta'] = calculate_beta(prices, market_prices)
        return metrics
    except Exception as e:
        logger.error(f"Error fetching metrics for {ticker}: {e}")
        metrics['error'] = str(e)
        return metrics

def calculate_sector_metrics():
    logger.info("=" * 60)
    logger.info("CALCULATING SECTOR METRICS")
    logger.info("=" * 60)

    if not os.path.exists(COMPANIES_CSV_PATH):
        logger.error(f"Companies file not found: {COMPANIES_CSV_PATH}")
        return

    companies_df = pd.read_csv(COMPANIES_CSV_PATH)
    logger.info(f"Loaded {len(companies_df)} companies")

    try:
        spy = yf.Ticker("SPY")
        market_prices = spy.history(period="1y")['Close']
    except Exception as e:
        logger.warning(f"Could not fetch SPY data for beta calculation: {e}")
        market_prices = None

    all_metrics = []
    for index, row in companies_df.iterrows():
        ticker = row['ticker']
        logger.info(f"Fetching metrics for {ticker} ({index + 1}/{len(companies_df)})..." )
        metrics = get_company_metrics(ticker, market_prices)
        all_metrics.append(metrics)
        time.sleep(1)

    metrics_df = pd.DataFrame(all_metrics)
    sector_groups = metrics_df.groupby('sector')
    sector_summary = {}
    for sector, group in sector_groups:
        logger.info(f"Calculating metrics for sector: {sector}")
        group = group.dropna(subset=['market_cap'])
        if group.empty:
            logger.warning(f"No valid data for sector: {sector}")
            continue

        total_market_cap = group['market_cap'].sum()

        def weighted_avg(col_name):
            if col_name not in group.columns or total_market_cap == 0:
                return None
            valid_group = group.dropna(subset=[col_name, 'market_cap'])
            if valid_group.empty:
                return None
            return (valid_group[col_name] * valid_group['market_cap']).sum() / valid_group['market_cap'].sum()

        sector_summary[sector] = {
            'num_companies': len(group),
            'total_market_cap': total_market_cap,
            'avg_pe_ratio': weighted_avg('pe_ratio'),
            'avg_ps_ratio': weighted_avg('ps_ratio'),
            'avg_pb_ratio': weighted_avg('pb_ratio'),
            'avg_gross_margin': weighted_avg('gross_margin'),
            'avg_net_margin': weighted_avg('net_margin'),
            'avg_roe': weighted_avg('roe'),
            'avg_roic': weighted_avg('roic'),
            'avg_debt_to_equity': weighted_avg('debt_to_equity'),
            'avg_cagr': weighted_avg('cagr'),
            'avg_volatility': weighted_avg('volatility'),
            'avg_beta': weighted_avg('beta'),
            'avg_sharpe_ratio': weighted_avg('sharpe_ratio'),
            'avg_momentum_1m': weighted_avg('momentum_1m'),
            'avg_momentum_3m': weighted_avg('momentum_3m'),
            'avg_momentum_6m': weighted_avg('momentum_6m'),
            'avg_momentum_1y': weighted_avg('momentum_1y'),
            'companies': group.to_dict(orient='records')
        }

    output_file = os.path.join(SECTOR_METRICS_DIR, "sector_metrics.json")
    with open(output_file, 'w') as f:
        json.dump(sector_summary, f, indent=2)

    logger.info(f"✅ Saved sector metrics to {output_file}")
