"""
Main entry point for Google Cloud deployment.
Supports both Cloud Functions and Cloud Run.
"""

import os
import json
import logging
from datetime import datetime
from flask import Flask, request, jsonify

# Import local modules
from target_tickers import TARGET_TICKERS
from bigquery_uploader import BigQueryUploader
from bigquery_schemas import create_all_tables
from google.cloud import bigquery, secretmanager
# Email notifications
from email_notifier import EmailNotifier

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Flask app for Cloud Run
app = Flask(__name__)

# Get GCP project ID from environment
PROJECT_ID = os.getenv("GCP_PROJECT_ID", os.getenv("GOOGLE_CLOUD_PROJECT"))
DATASET_ID = "deep_alpha_copilot"


def get_secret(secret_name):
    """Retrieve secret from Google Cloud Secret Manager."""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def setup_environment():
    """Setup environment variables from Secret Manager."""
    try:
        # Retrieve secrets and set as environment variables
        secrets = {
            "SEC_USER_AGENT": "SEC_USER_AGENT",
            "REDDIT_CLIENT_ID": "REDDIT_CLIENT_ID",
            "REDDIT_CLIENT_SECRET": "REDDIT_CLIENT_SECRET",
            "REDDIT_USER_AGENT": "REDDIT_USER_AGENT",
            "X_BEARER_TOKEN": "X_BEARER_TOKEN",
        }

        for env_var, secret_name in secrets.items():
            if env_var not in os.environ:
                try:
                    os.environ[env_var] = get_secret(secret_name)
                    logger.info(f"✅ Loaded secret: {secret_name}")
                except Exception as e:
                    logger.warning(f"⚠️  Could not load secret {secret_name}: {e}")

    except Exception as e:
        logger.error(f"Error setting up environment: {e}")


def fetch_and_upload_data(tickers=None):
    """
    Main data fetching and uploading function.
    Fetches data for all tickers and uploads to BigQuery.
    """
    if tickers is None:
        tickers = TARGET_TICKERS

    # Setup environment
    setup_environment()

    # Initialize BigQuery uploader
    uploader = BigQueryUploader(PROJECT_ID, DATASET_ID)

    # Ensure tables exist
    bq_client = bigquery.Client(project=PROJECT_ID)
    create_all_tables(bq_client, PROJECT_ID, DATASET_ID)

    results = {
        "status": "success",
        "timestamp": datetime.now().isoformat(),
        "tickers_processed": [],
        "errors": [],
    }

    # Import fetch functions dynamically to avoid loading if not needed
    try:
        from fetch_data import (
            fetch_ceo_data,
            fetch_quarterly_earnings,
            fetch_financial_statements,
            fetch_stock_prices,
            fetch_reddit_data,
            fetch_x_data_for_company,
            calculate_sector_metrics,
        )

        logger.info(f"Starting data fetch for {len(tickers)} tickers: {tickers}")

        for ticker in tickers:
            try:
                logger.info(f"\n{'='*60}")
                logger.info(f"Processing {ticker}")
                logger.info(f"{'='*60}")

                # 1. CEO Profile
                try:
                    ceo_data = fetch_ceo_data(ticker)
                    if ceo_data:
                        uploader.upload_ceo_profile(ceo_data)
                except Exception as e:
                    logger.error(f"Error fetching CEO data for {ticker}: {e}")
                    results["errors"].append({"ticker": ticker, "type": "ceo", "error": str(e)})

                # 2. Quarterly Earnings
                try:
                    earnings_data = fetch_quarterly_earnings(ticker)
                    if earnings_data:
                        uploader.upload_quarterly_earnings(ticker, earnings_data)
                except Exception as e:
                    logger.error(f"Error fetching earnings for {ticker}: {e}")
                    results["errors"].append({"ticker": ticker, "type": "earnings", "error": str(e)})

                # 3. Financial Statements
                try:
                    financials_data = fetch_financial_statements(ticker)
                    if financials_data:
                        uploader.upload_financial_statements(ticker, financials_data)
                except Exception as e:
                    logger.error(f"Error fetching financials for {ticker}: {e}")
                    results["errors"].append({"ticker": ticker, "type": "financials", "error": str(e)})

                # 4. Stock Prices
                try:
                    prices_df = fetch_stock_prices(ticker, period="5y")
                    if prices_df is not None and not prices_df.empty:
                        uploader.upload_stock_prices(ticker, prices_df)
                except Exception as e:
                    logger.error(f"Error fetching prices for {ticker}: {e}")
                    results["errors"].append({"ticker": ticker, "type": "prices", "error": str(e)})

                # 5. Reddit Posts
                try:
                    reddit_data = fetch_reddit_data(ticker, days=7)
                    if reddit_data:
                        uploader.upload_reddit_posts(ticker, reddit_data)
                except Exception as e:
                    logger.error(f"Error fetching Reddit data for {ticker}: {e}")
                    results["errors"].append({"ticker": ticker, "type": "reddit", "error": str(e)})

                # 6. X/Twitter Posts
                try:
                    x_data = fetch_x_data_for_company(ticker)
                    if x_data:
                        uploader.upload_x_posts(ticker, x_data)
                except Exception as e:
                    logger.error(f"Error fetching X data for {ticker}: {e}")
                    results["errors"].append({"ticker": ticker, "type": "x", "error": str(e)})

                results["tickers_processed"].append(ticker)
                logger.info(f"✅ Completed processing {ticker}")

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                results["errors"].append({"ticker": ticker, "type": "general", "error": str(e)})

        # 7. Calculate and upload sector metrics
        try:
            logger.info("\n" + "="*60)
            logger.info("Calculating sector metrics")
            logger.info("="*60)
            sector_data = calculate_sector_metrics(tickers)
            if sector_data:
                uploader.upload_sector_metrics(sector_data)

                # Also upload company-level metrics if available
                if "company_metrics" in sector_data:
                    uploader.upload_company_metrics(sector_data)

        except Exception as e:
            logger.error(f"Error calculating sector metrics: {e}")
            results["errors"].append({"type": "sector_metrics", "error": str(e)})

        logger.info(f"\n{'='*60}")
        logger.info(f"✅ Data fetch and upload complete!")
        logger.info(f"Processed {len(results['tickers_processed'])} tickers")
        logger.info(f"Errors: {len(results['errors'])}")
        logger.info(f"{'='*60}\n")

    except Exception as e:
        logger.error(f"Fatal error during data fetch: {e}")
        results["status"] = "error"
        results["fatal_error"] = str(e)

    return results


# Cloud Function entry point
def fetch_data_cloud_function(request):
    """
    Cloud Function entry point.
    Triggered by HTTP request or Cloud Scheduler.
    """
    try:
        # Parse request data
        request_json = request.get_json(silent=True)
        tickers = request_json.get("tickers") if request_json else None

        # Run fetch and upload
        results = fetch_and_upload_data(tickers)

        # Send summary email
        try:
            notifier = EmailNotifier()
            # Use number of tickers processed as summary for company_metrics
            summary_stats = {'company_metrics': {'new': len(results.get('tickers_processed', []))}}
            notifier.send_summary_email(summary_stats, results.get('errors', []))
        except Exception as e:
            logger.error(f"Error sending summary email: {e}")
        return jsonify(results), 200 if results["status"] == "success" else 500

    except Exception as e:
        logger.error(f"Error in Cloud Function: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


# Cloud Run entry points
@app.route("/", methods=["GET", "POST"])
def index():
    """Health check endpoint."""
    return jsonify({
        "service": "deep_alpha_copilot",
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


@app.route("/fetch", methods=["POST"])
def fetch_data_cloud_run():
    """
    Cloud Run endpoint for data fetching.
    POST /fetch
    Body: {"tickers": ["NVDA", "AMD"]} (optional)
    """
    try:
        request_json = request.get_json(silent=True)
        tickers = request_json.get("tickers") if request_json else None

        results = fetch_and_upload_data(tickers)

        # Send summary email
        try:
            notifier = EmailNotifier()
            summary_stats = {'company_metrics': {'new': len(results.get('tickers_processed', []))}}
            notifier.send_summary_email(summary_stats, results.get('errors', []))
        except Exception as e:
            logger.error(f"Error sending summary email: {e}")
        return jsonify(results), 200 if results["status"] == "success" else 500

    except Exception as e:
        logger.error(f"Error in Cloud Run endpoint: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


@app.route("/setup", methods=["POST"])
def setup_bigquery():
    """Setup BigQuery tables."""
    try:
        bq_client = bigquery.Client(project=PROJECT_ID)
        create_all_tables(bq_client, PROJECT_ID, DATASET_ID)
        return jsonify({"status": "success", "message": "BigQuery tables created"}), 200
    except Exception as e:
        logger.error(f"Error setting up BigQuery: {e}")
        return jsonify({"status": "error", "error": str(e)}), 500


if __name__ == "__main__":
    # For local testing
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=True)
