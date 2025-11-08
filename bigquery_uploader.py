"""
BigQuery uploader utility for deep_alpha_copilot data pipeline.
Handles uploading JSON data to BigQuery tables.
"""

import json
import pandas as pd
from datetime import datetime
from google.cloud import bigquery
from google.cloud.exceptions import NotFound
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BigQueryUploader:
    """Upload data to BigQuery tables matching local data/ structure."""

    def __init__(self, project_id, dataset_id="deep_alpha_copilot"):
        self.client = bigquery.Client(project=project_id)
        self.project_id = project_id
        self.dataset_id = dataset_id
        self.dataset_ref = f"{project_id}.{dataset_id}"

    def upload_ceo_profile(self, profile_data):
        """Upload CEO profile data to BigQuery with deduplication (check before insert)."""
        table_ref = f"{self.dataset_ref}.ceo_profiles"
        ticker = profile_data["ticker"]

        # Check if profile already exists
        query = f"""
            SELECT ticker
            FROM `{table_ref}`
            WHERE ticker = '{ticker}'
            LIMIT 1
        """
        try:
            result = list(self.client.query(query).result())
            if result:
                logger.info(f"CEO profile for {ticker} already exists, skipping")
                return False  # Skipped
        except Exception as e:
            # Table might be empty or not exist yet
            logger.debug(f"Could not query existing CEO profiles: {e}")

        # Prepare data
        row = {
            "ticker": ticker,
            "company_name": profile_data.get("company_name"),
            "ceo_name": profile_data.get("ceo_name"),
            "ceo_title": profile_data.get("ceo_title"),
            "tenure_duration": profile_data.get("tenure_duration"),
            "start_date": profile_data.get("start_date"),
            "linkedin_url": profile_data.get("linkedin_url"),
            "source": profile_data.get("source"),
            "past_experience": profile_data.get("past_experience", []),
            "education": profile_data.get("education"),
            "career_highlights": profile_data.get("career_highlights", []),
            "fetch_timestamp": profile_data.get("fetch_timestamp", datetime.now().isoformat()),
            "age": profile_data.get("age"),
            "year_born": profile_data.get("year_born"),
            "total_pay": profile_data.get("total_pay"),
        }

        # Insert new profile
        errors = self.client.insert_rows_json(table_ref, [row])
        if errors:
            logger.error(f"Error uploading CEO profile for {ticker}: {errors}")
            return False
        else:
            logger.info(f"✅ Uploaded CEO profile for {ticker}")
            return True  # New upload

    def upload_quarterly_earnings(self, ticker, earnings_list):
        """Upload quarterly earnings data to BigQuery with deduplication (time series by period)."""
        table_ref = f"{self.dataset_ref}.quarterly_earnings"

        if not earnings_list:
            return

        # Get existing periods for this ticker
        query = f"""
            SELECT DISTINCT TIMESTAMP(period) as period
            FROM `{table_ref}`
            WHERE ticker = '{ticker}'
        """
        try:
            result = self.client.query(query).result()
            existing_periods = set(row.period for row in result)
            logger.info(f"Found {len(existing_periods)} existing earnings periods for {ticker}")
        except Exception as e:
            logger.warning(f"Could not query existing periods for {ticker}: {e}")
            existing_periods = set()

        rows = []
        fetch_timestamp = datetime.now().isoformat()
        total_earnings = len(earnings_list)
        new_earnings = 0

        for earning in earnings_list:
            period = earning.get("period")
            # Convert period string to datetime for comparison
            try:
                period_dt = pd.to_datetime(period)
                if period_dt not in existing_periods:
                    rows.append({
                        "ticker": ticker,
                        "period": period,
                        "revenue": earning.get("revenue"),
                        "earnings": earning.get("earnings"),
                        "net_income": earning.get("net_income"),
                        "eps": earning.get("eps"),
                        "fetch_timestamp": fetch_timestamp,
                    })
                    new_earnings += 1
            except Exception as e:
                logger.warning(f"Could not parse period {period}: {e}")

        if not rows:
            logger.info(f"No new quarterly earnings to upload for {ticker} (all {total_earnings} periods already exist)")
            return (0, total_earnings)

        errors = self.client.insert_rows_json(table_ref, rows)
        if errors:
            logger.error(f"Error uploading quarterly earnings for {ticker}: {errors}")
        else:
            logger.info(f"✅ Uploaded {new_earnings} new quarterly earnings for {ticker} (skipped {total_earnings - new_earnings} existing periods)")
        return (new_earnings, total_earnings - new_earnings)

    def upload_financial_statements(self, ticker, financials_data):
        """Upload financial statements to BigQuery with deduplication (time series by fiscal_date)."""
        table_ref = f"{self.dataset_ref}.financial_statements"

        # Get existing fiscal dates for this ticker
        query = f"""
            SELECT DISTINCT TIMESTAMP(fiscal_date) as fiscal_date
            FROM `{table_ref}`
            WHERE ticker = '{ticker}'
        """
        try:
            result = self.client.query(query).result()
            existing_fiscal_dates = set(row.fiscal_date for row in result)
            logger.info(f"Found {len(existing_fiscal_dates)} existing fiscal dates for {ticker}")
        except Exception as e:
            logger.warning(f"Could not query existing fiscal dates for {ticker}: {e}")
            existing_fiscal_dates = set()

        rows = []
        fetch_date = financials_data.get("fetch_date", datetime.now().isoformat())
        total_fiscal_dates = set()

        # Flatten nested structure: income_statement, balance_sheet, cash_flow
        for statement_type in ["income_statement", "balance_sheet", "cash_flow"]:
            if statement_type in financials_data:
                statement_data = financials_data[statement_type]

                for fiscal_date, metrics in statement_data.items():
                    total_fiscal_dates.add(fiscal_date)

                    # Convert fiscal_date string to datetime for comparison
                    try:
                        fiscal_date_dt = pd.to_datetime(fiscal_date)

                        # Only add if this fiscal date doesn't exist yet
                        if fiscal_date_dt not in existing_fiscal_dates:
                            for metric_name, metric_value in metrics.items():
                                # Convert NaN to None for BigQuery compatibility
                                if metric_value is not None:
                                    try:
                                        value = float(metric_value)
                                        if pd.isna(value):
                                            value = None
                                    except (ValueError, TypeError):
                                        value = None
                                else:
                                    value = None

                                rows.append({
                                    "ticker": ticker,
                                    "statement_type": statement_type,
                                    "fiscal_date": fiscal_date,
                                    "metric_name": metric_name,
                                    "metric_value": value,
                                    "fetch_date": fetch_date,
                                })
                    except Exception as e:
                        logger.warning(f"Could not parse fiscal_date {fiscal_date}: {e}")

        if not rows:
            logger.info(f"No new financial statements to upload for {ticker} (all {len(total_fiscal_dates)} fiscal dates already exist)")
            return 0

        new_fiscal_dates = len(total_fiscal_dates) - len(existing_fiscal_dates.intersection(total_fiscal_dates))

        # Upload in batches of 10000 rows
        batch_size = 10000
        total_uploaded = 0
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            errors = self.client.insert_rows_json(table_ref, batch)
            if errors:
                logger.error(f"Error uploading financial statements batch for {ticker}: {errors}")
            else:
                total_uploaded += len(batch)

        logger.info(f"✅ Uploaded {total_uploaded} financial statement rows for {ticker} ({new_fiscal_dates} new fiscal dates)")
        return total_uploaded

    def upload_stock_prices(self, ticker, prices_df):
        """Upload stock price data from DataFrame to BigQuery with deduplication (time series)."""
        table_ref = f"{self.dataset_ref}.stock_prices"

        if prices_df is None or len(prices_df) == 0:
            logger.info(f"No price data to upload for {ticker}")
            return (0, 0)

        # Add ticker and fetch_timestamp
        prices_df = prices_df.copy()
        prices_df['ticker'] = ticker
        prices_df['fetch_timestamp'] = datetime.now()

        # Reset index to make date a column
        if prices_df.index.name == 'Date':
            prices_df = prices_df.reset_index()
            prices_df.rename(columns={'Date': 'date'}, inplace=True)

        # Rename columns to match schema
        column_mapping = {
            'Open': 'open',
            'High': 'high',
            'Low': 'low',
            'Close': 'close',
            'Volume': 'volume',
        }
        prices_df.rename(columns=column_mapping, inplace=True)

        # Drop columns not in BigQuery schema
        columns_to_drop = ['Dividends', 'Stock Splits']
        prices_df = prices_df.drop(columns=[col for col in columns_to_drop if col in prices_df.columns], errors='ignore')

        # Get existing dates for this ticker from BigQuery
        query = f"""
            SELECT DISTINCT DATE(date) as date
            FROM `{table_ref}`
            WHERE ticker = '{ticker}'
        """
        try:
            result = self.client.query(query).result()
            existing_dates = set(row.date for row in result)
            logger.info(f"Found {len(existing_dates)} existing price dates for {ticker}")
        except Exception as e:
            logger.warning(f"Could not query existing dates for {ticker}: {e}")
            existing_dates = set()

        # Filter to only new dates
        total_rows = len(prices_df)
        if existing_dates:
            # Convert date column to date only (remove time component) for comparison
            prices_df['date_only'] = pd.to_datetime(prices_df['date']).dt.date
            prices_df = prices_df[~prices_df['date_only'].isin(existing_dates)]
            prices_df = prices_df.drop(columns=['date_only'])

        new_rows = len(prices_df)
        skipped_rows = total_rows - new_rows

        if new_rows == 0:
            logger.info(f"No new price data to upload for {ticker} (all {total_rows} dates already exist)")
            return (0, skipped_rows)

        # Upload to BigQuery
        job_config = bigquery.LoadJobConfig(
            write_disposition="WRITE_APPEND",
        )

        job = self.client.load_table_from_dataframe(
            prices_df, table_ref, job_config=job_config
        )
        job.result()  # Wait for job to complete

        logger.info(f"✅ Uploaded {new_rows} new price rows for {ticker} (skipped {skipped_rows} existing dates)")
        return (new_rows, skipped_rows)

    def upload_sector_metrics(self, sector_data):
        """Upload sector-level metrics to BigQuery (appends new snapshot)."""
        table_ref = f"{self.dataset_ref}.sector_metrics"

        fetch_timestamp = sector_data.get("fetch_timestamp", datetime.now().isoformat())

        rows = []
        for sector_name, metrics in sector_data.get("sectors", {}).items():
            rows.append({
                "sector": sector_name,
                "fetch_timestamp": fetch_timestamp,
                "num_companies": metrics.get("num_companies"),
                "total_market_cap": metrics.get("total_market_cap"),
                "avg_market_cap": metrics.get("avg_market_cap"),
                "total_revenue": metrics.get("total_revenue"),
                "avg_revenue": metrics.get("avg_revenue"),
                "avg_gross_margin": metrics.get("avg_gross_margin"),
                "median_gross_margin": metrics.get("median_gross_margin"),
                "avg_net_margin": metrics.get("avg_net_margin"),
                "median_net_margin": metrics.get("median_net_margin"),
                "avg_pe_ratio": metrics.get("avg_pe_ratio"),
                "median_pe_ratio": metrics.get("median_pe_ratio"),
                "avg_rsi": metrics.get("avg_rsi"),
                "quality_score": metrics.get("quality_score"),
                "metrics_json": json.dumps(metrics),  # Convert dict to JSON string
            })

        if not rows:
            return 0

        # For sector metrics, we append each new snapshot (time series)
        # This allows tracking how sector metrics change over time
        errors = self.client.insert_rows_json(table_ref, rows)
        if errors:
            logger.error(f"Error uploading sector metrics: {errors}")
        else:
            logger.info(f"✅ Uploaded {len(rows)} sector metrics")
        return len(rows)

    def upload_company_metrics(self, metrics_data):
        """Upload company-level metrics to BigQuery (appends new snapshot)."""
        table_ref = f"{self.dataset_ref}.company_metrics"

        rows = []
        fetch_timestamp = datetime.now().isoformat()

        # Handle both list and dict formats
        companies = metrics_data if isinstance(metrics_data, list) else metrics_data.get("companies", [])

        for company in companies:
            rows.append({
                "ticker": company.get("ticker"),
                "fetch_timestamp": fetch_timestamp,
                "company_name": company.get("company_name"),
                "sector": company.get("sector"),
                "market_cap": company.get("market_cap"),
                "revenue": company.get("revenue"),
                "gross_margin": company.get("gross_margin"),
                "net_margin": company.get("net_margin"),
                "pe_ratio": company.get("pe_ratio"),
                "eps": company.get("eps"),
                "roe": company.get("roe"),
                "roa": company.get("roa"),
                "metrics_json": json.dumps(company),  # Convert dict to JSON string
            })

        if not rows:
            return 0

        # For company metrics, we append each new snapshot (time series)
        # This allows tracking how company metrics change over time
        errors = self.client.insert_rows_json(table_ref, rows)
        if errors:
            logger.error(f"Error uploading company metrics: {errors}")
        else:
            logger.info(f"✅ Uploaded {len(rows)} company metrics")
        return len(rows)

    def upload_reddit_posts(self, ticker, posts_data):
        """Upload Reddit posts to BigQuery with deduplication (skip existing post_ids)."""
        table_ref = f"{self.dataset_ref}.reddit_posts"

        rows = []
        fetch_timestamp = datetime.now().isoformat()

        # Get list of existing post IDs for this ticker
        query = f"""
            SELECT DISTINCT post_id
            FROM `{table_ref}`
            WHERE ticker = '{ticker}'
        """
        try:
            existing_post_ids = set(row.post_id for row in self.client.query(query).result())
        except Exception:
            existing_post_ids = set()

        # Only add posts that don't already exist
        new_posts = 0
        for post in posts_data.get("posts", []):
            post_id = post.get("id")
            if post_id not in existing_post_ids:
                rows.append({
                    "ticker": ticker,
                    "post_id": post_id,
                    "title": post.get("title"),
                    "selftext": post.get("selftext"),
                    "score": post.get("score"),
                    "upvote_ratio": post.get("upvote_ratio"),
                    "num_comments": post.get("num_comments"),
                    "created_utc": datetime.fromtimestamp(post.get("created_utc", 0)).isoformat(),
                    "subreddit": post.get("subreddit"),
                    "url": post.get("url"),
                    "mentioned_tickers": post.get("mentioned_tickers", []),
                    "sentiment": post.get("sentiment"),
                    "compound_score": post.get("compound_score"),
                    "positive_score": post.get("positive_score"),
                    "negative_score": post.get("negative_score"),
                    "topics": post.get("topics", []),
                    "fetch_timestamp": fetch_timestamp,
                })
                new_posts += 1

        if not rows:
            logger.info(f"No new Reddit posts to upload for {ticker}")
            return 0

        # Upload in batches
        batch_size = 1000
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            errors = self.client.insert_rows_json(table_ref, batch)
            if errors:
                logger.error(f"Error uploading Reddit posts for {ticker}: {errors}")
            else:
                logger.info(f"✅ Uploaded {len(batch)} new Reddit posts for {ticker} (skipped {len(posts_data.get('posts', [])) - new_posts} duplicates)")

        return new_posts

    def upload_x_posts(self, ticker, posts_data):
        """Upload X/Twitter posts to BigQuery with deduplication (skip existing post_ids)."""
        table_ref = f"{self.dataset_ref}.x_posts"

        rows = []
        fetch_timestamp = datetime.now().isoformat()

        # Get list of existing post IDs for this ticker
        query = f"""
            SELECT DISTINCT post_id
            FROM `{table_ref}`
            WHERE ticker = '{ticker}'
        """
        try:
            existing_post_ids = set(row.post_id for row in self.client.query(query).result())
        except Exception:
            existing_post_ids = set()

        # Only add posts that don't already exist
        all_posts = posts_data.get("company_posts", []) + posts_data.get("ceo_posts", [])
        new_posts = 0

        for post in all_posts:
            post_id = post.get("id")
            if post_id not in existing_post_ids:
                rows.append({
                    "ticker": ticker,
                    "post_id": post_id,
                    "text": post.get("text"),
                    "created_at": post.get("created_at"),
                    "author_username": post.get("author_username"),
                    "author_name": post.get("author_name"),
                    "author_verified": post.get("author_verified"),
                    "like_count": post.get("public_metrics", {}).get("like_count"),
                    "retweet_count": post.get("public_metrics", {}).get("retweet_count"),
                    "reply_count": post.get("public_metrics", {}).get("reply_count"),
                    "quote_count": post.get("public_metrics", {}).get("quote_count"),
                    "bookmark_count": post.get("public_metrics", {}).get("bookmark_count"),
                    "impression_count": post.get("public_metrics", {}).get("impression_count"),
                    "url": post.get("url"),
                    "sentiment": post.get("sentiment"),
                    "compound_score": post.get("compound_score"),
                    "fetch_timestamp": fetch_timestamp,
                })
                new_posts += 1

        if rows:
            errors = self.client.insert_rows_json(table_ref, rows)
            if errors:
                logger.error(f"Error uploading X posts for {ticker}: {errors}")
            else:
                logger.info(f"✅ Uploaded {len(rows)} new X posts for {ticker} (skipped {len(all_posts) - new_posts} duplicates)")
        else:
            if len(all_posts) > 0:
                logger.info(f"No new X posts to upload for {ticker} (all {len(all_posts)} posts already exist)")
            else:
                logger.info(f"No X posts to upload for {ticker}")

        return new_posts


if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Load environment variables from .env
    load_dotenv()

    # Example usage
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print("❌ Error: GCP_PROJECT_ID not found in environment variables")
        print("Please set GCP_PROJECT_ID in your .env file or environment")
        exit(1)

    uploader = BigQueryUploader(project_id)

    print("✅ BigQuery Uploader initialized")
    print(f"Project: {project_id}")
    print(f"Dataset: {uploader.dataset_id}")
