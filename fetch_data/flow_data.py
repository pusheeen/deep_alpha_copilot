import os
import logging
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from .utils import retry_on_failure
import json
import glob
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np

logger = logging.getLogger(__name__)

def get_date_suffix() -> str:
    """Returns today's date in YYYYMMDD format for filename suffix."""
    return datetime.utcnow().strftime('%Y%m%d')

def load_previous_institutional_data(ticker: str, flow_dir: str, days_back: int = 90) -> dict:
    """
    Loads the most recent previous institutional data file for comparison.

    Args:
        ticker: Stock ticker symbol
        flow_dir: Directory containing flow data files
        days_back: How many days back to search for previous data

    Returns:
        dict: Previous institutional data or None if not found
    """
    pattern = os.path.join(flow_dir, f"{ticker}_institutional_flow_*.json")
    files = glob.glob(pattern)

    if not files:
        return None

    # Sort by date suffix (newest first)
    files.sort(reverse=True)

    # Get today's date suffix to skip today's file if it exists
    today_suffix = get_date_suffix()

    for file in files:
        # Extract date from filename
        basename = os.path.basename(file)
        if today_suffix in basename:
            continue  # Skip today's file

        try:
            with open(file, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Error loading previous institutional data from {file}: {e}")
            continue

    return None

def calculate_institutional_changes(current_data: dict, previous_data: dict) -> dict:
    """
    Calculates institutional inflow/outflow by comparing current vs previous holdings.

    Args:
        current_data: Current institutional holdings data
        previous_data: Previous institutional holdings data

    Returns:
        dict: Changes in institutional holdings
    """
    if not previous_data or 'top_10_holders' not in previous_data:
        return {
            "has_comparison": False,
            "message": "No previous data available for comparison"
        }

    current_holders = {h['holder']: h for h in current_data.get('top_10_holders', [])}
    previous_holders = {h['holder']: h for h in previous_data.get('top_10_holders', [])}

    changes = []
    total_shares_change = 0
    total_value_change = 0

    # Track all holders from both periods
    all_holders = set(current_holders.keys()) | set(previous_holders.keys())

    for holder in all_holders:
        current = current_holders.get(holder, {})
        previous = previous_holders.get(holder, {})

        current_shares = current.get('shares', 0)
        previous_shares = previous.get('shares', 0)
        current_value = current.get('value', 0)
        previous_value = previous.get('value', 0)

        shares_change = current_shares - previous_shares
        value_change = current_value - previous_value

        if shares_change != 0:
            pct_change = (shares_change / previous_shares * 100) if previous_shares > 0 else 100 if current_shares > 0 else 0

            change_entry = {
                "holder": holder,
                "current_shares": current_shares,
                "previous_shares": previous_shares,
                "shares_change": shares_change,
                "pct_change": round(pct_change, 2),
                "value_change": value_change,
                "action": "bought" if shares_change > 0 else "sold" if shares_change < 0 else "no change",
                "current_date": current.get('date_reported', 'N/A'),
                "previous_date": previous.get('date_reported', 'N/A')
            }
            changes.append(change_entry)

            total_shares_change += shares_change
            total_value_change += value_change

    # Sort by absolute change magnitude
    changes.sort(key=lambda x: abs(x['shares_change']), reverse=True)

    # Calculate aggregate metrics
    current_total_shares = current_data.get('total_institutional_shares', 0)
    previous_total_shares = previous_data.get('total_institutional_shares', 0)
    net_shares_change = current_total_shares - previous_total_shares

    current_total_value = current_data.get('total_institutional_value', 0)
    previous_total_value = previous_data.get('total_institutional_value', 0)
    net_value_change = current_total_value - previous_total_value

    buyers = [c for c in changes if c['action'] == 'bought']
    sellers = [c for c in changes if c['action'] == 'sold']

    return {
        "has_comparison": True,
        "comparison_date": previous_data.get('timestamp', 'Unknown'),
        "current_date": current_data.get('timestamp'),
        "net_institutional_flow": {
            "shares_change": net_shares_change,
            "value_change": net_value_change,
            "direction": "inflow" if net_shares_change > 0 else "outflow" if net_shares_change < 0 else "neutral",
            "current_total_shares": current_total_shares,
            "previous_total_shares": previous_total_shares,
            "current_total_value": current_total_value,
            "previous_total_value": previous_total_value
        },
        "holder_changes": changes,
        "summary": {
            "total_holders_tracked": len(all_holders),
            "holders_increased": len(buyers),
            "holders_decreased": len(sellers),
            "top_5_buyers": buyers[:5],
            "top_5_sellers": sellers[:5]
        }
    }

@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_institutional_flow(ticker: str, flow_dir: str) -> dict:
    """
    Fetches institutional ownership data and calculates flow metrics.

    Args:
        ticker: Stock ticker symbol
        flow_dir: Directory to save flow data

    Returns:
        dict: Institutional flow data including ownership changes
    """
    logger.info(f"Fetching institutional flow data for {ticker}...")

    try:
        stock = yf.Ticker(ticker)

        # Get institutional holders
        institutional_holders = stock.institutional_holders

        if institutional_holders is None or institutional_holders.empty:
            logger.warning(f"No institutional holder data found for {ticker}")
            return {
                "ticker": ticker,
                "error": "No institutional data available",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Get major holders summary
        major_holders = stock.major_holders

        # Get shares outstanding for calculating percentage
        shares_outstanding = None
        try:
            info = stock.info
            shares_outstanding = info.get('sharesOutstanding')
        except Exception as e:
            logger.warning(f"Could not get shares outstanding for {ticker}: {e}")

        # Calculate institutional metrics
        total_shares = institutional_holders['Shares'].sum() if 'Shares' in institutional_holders.columns else 0
        total_value = institutional_holders['Value'].sum() if 'Value' in institutional_holders.columns else 0

        # Get top holders
        top_holders = []
        for idx, row in institutional_holders.head(10).iterrows():
            # Try to get pct_out from the data, or calculate it if we have shares outstanding
            pct_out = None
            if '% Out' in row and row.get('% Out'):
                pct_out = float(row.get('% Out'))
            elif shares_outstanding and shares_outstanding > 0:
                holder_shares = row.get('Shares', 0)
                pct_out = (holder_shares / shares_outstanding) * 100

            # Get quarterly change from Yahoo Finance (factual data from SEC filings)
            pct_change = row.get('pctChange', None)
            if pct_change is not None:
                pct_change = float(pct_change) * 100  # Convert to percentage

            holder_info = {
                "holder": str(row.get('Holder', 'Unknown')),
                "shares": int(row.get('Shares', 0)),
                "date_reported": str(row.get('Date Reported', '')),
                "pct_out": round(pct_out, 2) if pct_out is not None else None,
                "value": int(row.get('Value', 0)),
                "quarterly_change_pct": round(pct_change, 2) if pct_change is not None else None
            }
            top_holders.append(holder_info)

        # Parse major holders info
        institutional_pct = None
        insiders_pct = None
        if major_holders is not None and not major_holders.empty:
            try:
                # The index contains the description, and 'Value' column contains the value
                for idx, row in major_holders.iterrows():
                    desc = str(idx).lower()
                    value = row['Value'] if 'Value' in major_holders.columns else row.iloc[0]
                    if value is None:
                        continue

                    # Convert to percentage (multiply by 100 if it's a decimal)
                    value_float = float(value)
                    if value_float < 1:  # It's a decimal like 0.68999
                        value_float *= 100

                    if 'institutionspercent' in desc or ('institutions' in desc and 'held' in desc):
                        institutional_pct = value_float
                    elif 'insiderspercent' in desc or ('insiders' in desc and 'held' in desc):
                        insiders_pct = value_float
            except Exception as e:
                logger.warning(f"Error parsing major holders for {ticker}: {e}")

        # Fallback: Try to get ownership data from stock.info if not found in major_holders
        if institutional_pct is None or insiders_pct is None:
            try:
                info = stock.info
                if institutional_pct is None and 'heldPercentInstitutions' in info:
                    institutional_pct = float(info['heldPercentInstitutions']) * 100  # Convert to percentage
                if insiders_pct is None and 'heldPercentInsiders' in info:
                    insiders_pct = float(info['heldPercentInsiders']) * 100  # Convert to percentage
            except Exception as e:
                logger.warning(f"Error getting ownership from stock.info for {ticker}: {e}")

        # Calculate aggregate institutional changes from quarterly filings
        holders_with_changes = [h for h in top_holders if h.get('quarterly_change_pct') is not None]

        # Extract data freshness information
        latest_filing_date = None
        quarter_str = "Unknown"
        if top_holders and len(top_holders) > 0:
            latest_filing_date = top_holders[0].get('date_reported', '')
            if latest_filing_date:
                # Parse quarter from date (e.g., "2025-06-30" → "Q2 2025")
                try:
                    from datetime import datetime as dt
                    filing_dt = dt.strptime(latest_filing_date.split(' ')[0], '%Y-%m-%d')
                    quarter = (filing_dt.month - 1) // 3 + 1
                    quarter_str = f"Q{quarter} {filing_dt.year}"
                except:
                    quarter_str = latest_filing_date.split(' ')[0]

        if holders_with_changes:
            # Count institutions that increased, decreased, or stayed same
            increased = sum(1 for h in holders_with_changes if h['quarterly_change_pct'] > 0.1)
            decreased = sum(1 for h in holders_with_changes if h['quarterly_change_pct'] < -0.1)
            unchanged = len(holders_with_changes) - increased - decreased

            # Calculate net flow (positive changes - negative changes)
            net_change_pct = sum(h['quarterly_change_pct'] for h in holders_with_changes) / len(holders_with_changes)

            quarterly_summary = {
                "has_data": True,
                "institutions_increased": increased,
                "institutions_decreased": decreased,
                "institutions_unchanged": unchanged,
                "net_change_pct": round(net_change_pct, 2),
                "data_source": "Yahoo Finance (SEC 13F filings)",
                "note": "Factual quarterly changes from SEC filings",
                "filing_quarter": quarter_str,
                "filing_date": latest_filing_date
            }
        else:
            quarterly_summary = {
                "has_data": False,
                "note": "No quarterly change data available",
                "filing_quarter": quarter_str,
                "filing_date": latest_filing_date
            }

        flow_data = {
            "ticker": ticker,
            "timestamp": datetime.utcnow().isoformat(),
            "institutional_ownership_pct": institutional_pct,
            "insider_ownership_pct": insiders_pct,
            "total_institutional_shares": int(total_shares),
            "total_institutional_value": int(total_value),
            "number_of_institutions": len(institutional_holders),
            "top_10_holders": top_holders,
            "quarterly_changes": quarterly_summary,
            "data_source": "Yahoo Finance"
        }

        # Save to file with date suffix
        os.makedirs(flow_dir, exist_ok=True)
        date_suffix = get_date_suffix()
        filename = os.path.join(flow_dir, f"{ticker}_institutional_flow_{date_suffix}.json")
        with open(filename, 'w') as f:
            json.dump(flow_data, f, indent=2)

        logger.info(f"✅ Saved institutional flow data for {ticker} to {filename}")
        return flow_data

    except Exception as e:
        logger.error(f"Error fetching institutional flow for {ticker}: {e}")
        raise


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def fetch_retail_flow(ticker: str, flow_dir: str, period: str = "3mo") -> dict:
    """
    Estimates retail flow based on volume patterns and trade sizes using improved heuristics.

    IMPORTANT: This is ESTIMATED data. Real order flow data requires professional terminals.

    Estimation methodology based on academic research:
    - Barber & Odean (2000): Retail investors trade on momentum, buy winners
    - Kaniel et al. (2008): Retail investors are contrarian, buy on dips (panic sell large drops)
    - Lee & Radhakrishna (2000): Volume spikes correlate with institutional block trades
    - Hasbrouck (2009): High intraday volatility indicates informed (institutional) trading

    Args:
        ticker: Stock ticker symbol
        flow_dir: Directory to save flow data
        period: Time period for historical data (default: 3 months)

    Returns:
        dict: Retail flow estimates and metrics (clearly marked as estimated)
    """
    logger.info(f"Fetching retail flow estimates for {ticker}...")

    try:
        stock = yf.Ticker(ticker)

        # Get historical data with volume
        hist = stock.history(period=period)

        if hist.empty:
            logger.warning(f"No price/volume data found for {ticker}")
            return {
                "ticker": ticker,
                "error": "No volume data available",
                "timestamp": datetime.utcnow().isoformat()
            }

        # Calculate volume metrics
        avg_volume = hist['Volume'].mean()
        recent_volume = hist['Volume'].tail(30).mean()  # Last 30 days
        volume_trend = ((recent_volume - avg_volume) / avg_volume * 100) if avg_volume > 0 else 0

        # Estimate retail vs institutional based on volume patterns
        # High volume days often indicate institutional activity
        # Small, consistent volumes typically suggest retail
        volume_std = hist['Volume'].std()
        volume_coefficient_variation = (volume_std / avg_volume) if avg_volume > 0 else 0

        # Calculate daily flow metrics with improved heuristics
        daily_flows = []
        hist_tail = hist.tail(60)  # Last 60 days

        for i, (idx, row) in enumerate(hist_tail.iterrows()):
            date = idx.strftime('%Y-%m-%d')
            volume = row['Volume']
            price_change = ((row['Close'] - row['Open']) / row['Open'] * 100) if row['Open'] > 0 else 0

            # IMPROVED HEURISTICS FOR RETAIL ESTIMATION
            # Start with base assumption
            estimated_retail_pct = 50

            # Factor 1: Price movement magnitude (larger moves → more institutional)
            abs_price_change = abs(price_change)
            if abs_price_change > 5:
                estimated_retail_pct -= 20  # Large moves suggest institutional activity
            elif abs_price_change > 3:
                estimated_retail_pct -= 10
            elif abs_price_change < 0.5:
                estimated_retail_pct += 10  # Small moves suggest retail trickle

            # Factor 2: Volume spike detection (high volume → more institutional)
            volume_ratio = (volume / avg_volume) if avg_volume > 0 else 1
            if volume_ratio > 2.5:
                estimated_retail_pct -= 25  # Major volume spike → definitely institutional
            elif volume_ratio > 1.5:
                estimated_retail_pct -= 15
            elif volume_ratio < 0.7:
                estimated_retail_pct += 10  # Low volume → more retail dominated

            # Factor 3: Momentum trading behavior (retail FOMO on uptrends)
            if price_change > 3:
                estimated_retail_pct += 15  # Retail buys on strong momentum
            elif price_change > 1.5:
                estimated_retail_pct += 8

            # Factor 4: Panic selling (retail sells on drops)
            if price_change < -3:
                estimated_retail_pct -= 10  # Institutional selling + retail panic = net institutional
            elif price_change < -1.5:
                estimated_retail_pct -= 5

            # Factor 5: Intraday volatility (high-low spread indicates institutional activity)
            intraday_range = ((row['High'] - row['Low']) / row['Low'] * 100) if row['Low'] > 0 else 0
            if intraday_range > 4:
                estimated_retail_pct -= 10  # High volatility → institutional trading

            # Clamp between realistic bounds (20-80% to avoid extreme estimates)
            estimated_retail_pct = max(20, min(80, estimated_retail_pct))

            flow_entry = {
                "date": date,
                "volume": int(volume),
                "price_change_pct": round(price_change, 2),
                "estimated_retail_participation_pct": round(estimated_retail_pct, 1),
                "estimated_institutional_participation_pct": round(100 - estimated_retail_pct, 1),
                "volume_vs_average": round(volume_ratio, 2)
            }
            daily_flows.append(flow_entry)

        # Calculate aggregated metrics
        recent_30d = [f for f in daily_flows[-30:]]
        avg_retail_participation = sum(f['estimated_retail_participation_pct'] for f in recent_30d) / len(recent_30d) if recent_30d else 50

        # Inflow vs Outflow heuristic based on price-volume relationship
        inflow_days = [f for f in recent_30d if f['price_change_pct'] > 0]
        outflow_days = [f for f in recent_30d if f['price_change_pct'] < 0]

        avg_inflow_volume = sum(f['volume'] for f in inflow_days) / len(inflow_days) if inflow_days else 0
        avg_outflow_volume = sum(f['volume'] for f in outflow_days) / len(outflow_days) if outflow_days else 0

        net_flow_indicator = ((avg_inflow_volume - avg_outflow_volume) / avg_volume * 100) if avg_volume > 0 else 0

        flow_data = {
            "ticker": ticker,
            "timestamp": datetime.utcnow().isoformat(),
            "period_analyzed": period,
            "metrics": {
                "average_daily_volume": int(avg_volume),
                "recent_30d_avg_volume": int(recent_volume),
                "volume_trend_pct": round(volume_trend, 2),
                "volume_volatility": round(volume_coefficient_variation, 3),
                "estimated_avg_retail_participation_pct": round(avg_retail_participation, 1),
                "net_flow_indicator_pct": round(net_flow_indicator, 2),
                "inflow_days_count": len(inflow_days),
                "outflow_days_count": len(outflow_days)
            },
            "daily_flows": daily_flows,
            "interpretation": {
                "retail_trend": "increasing" if avg_retail_participation > 55 else "decreasing" if avg_retail_participation < 45 else "stable",
                "flow_direction": "net inflow" if net_flow_indicator > 5 else "net outflow" if net_flow_indicator < -5 else "balanced",
                "volume_pattern": "high volatility" if volume_coefficient_variation > 0.5 else "stable"
            },
            "disclaimer": "Retail flow estimates are based on volume patterns and heuristics. Actual retail participation may vary.",
            "data_source": "Yahoo Finance with algorithmic estimation"
        }

        # Save to file with date suffix
        os.makedirs(flow_dir, exist_ok=True)
        date_suffix = get_date_suffix()
        filename = os.path.join(flow_dir, f"{ticker}_retail_flow_{date_suffix}.json")
        with open(filename, 'w') as f:
            json.dump(flow_data, f, indent=2)

        logger.info(f"✅ Saved retail flow estimates for {ticker} to {filename}")
        return flow_data

    except Exception as e:
        logger.error(f"Error fetching retail flow for {ticker}: {e}")
        raise


@retry_on_failure(max_retries=3, delay=2.0, backoff=2.0)
def plot_flow_time_series(ticker: str, daily_flows: list, flow_dir: str) -> str:
    """
    Generate and save time series plots for retail and institutional volume.

    Args:
        ticker: Stock ticker symbol
        daily_flows: List of daily flow data points
        flow_dir: Directory to save the plot

    Returns:
        Path to saved plot file
    """
    if not daily_flows:
        logger.warning(f"No daily flow data to plot for {ticker}")
        return None

    # Extract data
    dates = [datetime.strptime(d['date'], '%Y-%m-%d') for d in daily_flows]
    volumes = [d['volume'] for d in daily_flows]
    retail_pcts = [d.get('estimated_retail_participation_pct', 50) for d in daily_flows]
    inst_pcts = [d.get('estimated_institutional_participation_pct', 50) for d in daily_flows]

    # Calculate retail and institutional volumes
    retail_volumes = [vol * (pct / 100) for vol, pct in zip(volumes, retail_pcts)]
    inst_volumes = [vol * (pct / 100) for vol, pct in zip(volumes, inst_pcts)]

    # Convert to millions for better readability
    retail_volumes_m = [v / 1e6 for v in retail_volumes]
    inst_volumes_m = [v / 1e6 for v in inst_volumes]

    # Create figure with single plot
    fig, ax = plt.subplots(1, 1, figsize=(14, 8))

    # Colors
    retail_color = '#3b82f6'  # Blue
    inst_color = '#8b5cf6'    # Purple

    # Plot both curves on same chart
    ax.fill_between(dates, retail_volumes_m, alpha=0.15, color=retail_color)
    ax.plot(dates, retail_volumes_m, marker='o', linewidth=2.5, markersize=4,
            color=retail_color, markerfacecolor=retail_color, markeredgecolor='white',
            markeredgewidth=1.5, alpha=0.9, label='Retail Volume')

    ax.fill_between(dates, inst_volumes_m, alpha=0.15, color=inst_color)
    ax.plot(dates, inst_volumes_m, marker='s', linewidth=2.5, markersize=4,
            color=inst_color, markerfacecolor=inst_color, markeredgecolor='white',
            markeredgewidth=1.5, alpha=0.9, label='Institutional Volume')

    ax.set_xlabel('Date', fontsize=12, fontweight='bold')
    ax.set_ylabel('Volume (Millions)', fontsize=12, fontweight='bold')
    ax.set_title(f'{ticker} - Retail vs Institutional Volume Over Time', fontsize=14, fontweight='bold', pad=15)
    ax.grid(True, alpha=0.3, linestyle='--')
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(interval=2))
    plt.setp(ax.xaxis.get_majorticklabels(), rotation=45, ha='right')

    # Add legend
    ax.legend(loc='upper left', fontsize=11, frameon=True, shadow=True, fancybox=True)

    # Add note
    first_date = daily_flows[0]['date']
    last_date = daily_flows[-1]['date']
    ax.text(0.98, 0.02, f'Period: {first_date} to {last_date}\n' +
            'Volume breakdown estimated based on daily trading patterns\n' +
            'Yahoo Finance provides quarterly institutional ownership only',
            transform=ax.transAxes, fontsize=8, alpha=0.6,
            ha='right', va='bottom', style='italic')

    # Tight layout
    plt.tight_layout()

    # Save the plot
    date_suffix = get_date_suffix()
    plot_filename = f"{ticker}_flow_plot_{date_suffix}.png"
    plot_filepath = os.path.join(flow_dir, plot_filename)

    plt.savefig(plot_filepath, dpi=200, bbox_inches='tight')
    plt.close()

    logger.info(f"✅ Saved flow time series plot to {plot_filepath}")
    return plot_filepath


def fetch_combined_flow_data(ticker: str, flow_dir: str) -> dict:
    """
    Fetches both institutional and retail flow data for a ticker.
    Also calculates institutional changes by comparing with previous data.

    Args:
        ticker: Stock ticker symbol
        flow_dir: Directory to save flow data

    Returns:
        dict: Combined flow data with institutional change tracking
    """
    logger.info(f"Fetching combined flow data for {ticker}...")

    # Fetch current data
    institutional_data = fetch_institutional_flow(ticker, flow_dir)
    retail_data = fetch_retail_flow(ticker, flow_dir)

    # Use quarterly changes from Yahoo Finance (already included in institutional_data)
    institutional_changes = institutional_data.get('quarterly_changes', {
        "has_data": False,
        "note": "No quarterly change data available"
    })

    combined = {
        "ticker": ticker,
        "timestamp": datetime.utcnow().isoformat(),
        "institutional": institutional_data,
        "retail": retail_data,
        "institutional_changes": institutional_changes
    }

    # Save combined data with date suffix
    os.makedirs(flow_dir, exist_ok=True)
    date_suffix = get_date_suffix()
    filename = os.path.join(flow_dir, f"{ticker}_combined_flow_{date_suffix}.json")
    with open(filename, 'w') as f:
        json.dump(combined, f, indent=2)

    logger.info(f"✅ Saved combined flow data for {ticker} to {filename}")

    # Generate time series plot if we have daily flow data
    if retail_data and 'daily_flows' in retail_data and retail_data['daily_flows']:
        try:
            plot_filepath = plot_flow_time_series(ticker, retail_data['daily_flows'], flow_dir)
            if plot_filepath:
                logger.info(f"Flow plot generated: {plot_filepath}")
        except Exception as e:
            logger.warning(f"Failed to generate flow plot for {ticker}: {e}")

    return combined
