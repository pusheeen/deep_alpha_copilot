"""
BigQuery table schemas for deep_alpha_copilot data pipeline.
Maintains the same structure as local data/ directory.
"""

from google.cloud import bigquery

# Dataset name
DATASET_ID = "deep_alpha_copilot"

# Table schemas matching data/ structure

CEO_PROFILES_SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("company_name", "STRING"),
    bigquery.SchemaField("ceo_name", "STRING"),
    bigquery.SchemaField("ceo_title", "STRING"),
    bigquery.SchemaField("tenure_duration", "STRING"),
    bigquery.SchemaField("start_date", "STRING"),
    bigquery.SchemaField("linkedin_url", "STRING"),
    bigquery.SchemaField("source", "STRING"),
    bigquery.SchemaField("past_experience", "STRING", mode="REPEATED"),
    bigquery.SchemaField("education", "STRING"),
    bigquery.SchemaField("career_highlights", "STRING", mode="REPEATED"),
    bigquery.SchemaField("fetch_timestamp", "TIMESTAMP"),
    bigquery.SchemaField("age", "INTEGER"),
    bigquery.SchemaField("year_born", "INTEGER"),
    bigquery.SchemaField("total_pay", "FLOAT"),
]

QUARTERLY_EARNINGS_SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("period", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("revenue", "FLOAT"),
    bigquery.SchemaField("earnings", "FLOAT"),
    bigquery.SchemaField("net_income", "FLOAT"),
    bigquery.SchemaField("eps", "FLOAT"),
    bigquery.SchemaField("fetch_timestamp", "TIMESTAMP"),
]

FINANCIAL_STATEMENTS_SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("statement_type", "STRING", mode="REQUIRED"),  # income_statement, balance_sheet, cash_flow
    bigquery.SchemaField("fiscal_date", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("metric_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("metric_value", "FLOAT"),
    bigquery.SchemaField("fetch_date", "TIMESTAMP"),
]

STOCK_PRICES_SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("date", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("open", "FLOAT"),
    bigquery.SchemaField("high", "FLOAT"),
    bigquery.SchemaField("low", "FLOAT"),
    bigquery.SchemaField("close", "FLOAT"),
    bigquery.SchemaField("volume", "INTEGER"),
    bigquery.SchemaField("fetch_timestamp", "TIMESTAMP"),
]

SECTOR_METRICS_SCHEMA = [
    bigquery.SchemaField("sector", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("fetch_timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("num_companies", "INTEGER"),
    bigquery.SchemaField("total_market_cap", "FLOAT"),
    bigquery.SchemaField("avg_market_cap", "FLOAT"),
    bigquery.SchemaField("total_revenue", "FLOAT"),
    bigquery.SchemaField("avg_revenue", "FLOAT"),
    bigquery.SchemaField("avg_gross_margin", "FLOAT"),
    bigquery.SchemaField("median_gross_margin", "FLOAT"),
    bigquery.SchemaField("avg_net_margin", "FLOAT"),
    bigquery.SchemaField("median_net_margin", "FLOAT"),
    bigquery.SchemaField("avg_pe_ratio", "FLOAT"),
    bigquery.SchemaField("median_pe_ratio", "FLOAT"),
    bigquery.SchemaField("avg_rsi", "FLOAT"),
    bigquery.SchemaField("quality_score", "FLOAT"),
    bigquery.SchemaField("metrics_json", "JSON"),  # Store full nested structure
]

COMPANY_METRICS_SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("fetch_timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("company_name", "STRING"),
    bigquery.SchemaField("sector", "STRING"),
    bigquery.SchemaField("market_cap", "FLOAT"),
    bigquery.SchemaField("revenue", "FLOAT"),
    bigquery.SchemaField("gross_margin", "FLOAT"),
    bigquery.SchemaField("net_margin", "FLOAT"),
    bigquery.SchemaField("pe_ratio", "FLOAT"),
    bigquery.SchemaField("eps", "FLOAT"),
    bigquery.SchemaField("roe", "FLOAT"),
    bigquery.SchemaField("roa", "FLOAT"),
    bigquery.SchemaField("metrics_json", "JSON"),  # Store full nested structure
]

REDDIT_POSTS_SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("post_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("title", "STRING"),
    bigquery.SchemaField("selftext", "STRING"),
    bigquery.SchemaField("score", "INTEGER"),
    bigquery.SchemaField("upvote_ratio", "FLOAT"),
    bigquery.SchemaField("num_comments", "INTEGER"),
    bigquery.SchemaField("created_utc", "TIMESTAMP"),
    bigquery.SchemaField("subreddit", "STRING"),
    bigquery.SchemaField("url", "STRING"),
    bigquery.SchemaField("mentioned_tickers", "STRING", mode="REPEATED"),
    bigquery.SchemaField("sentiment", "STRING"),
    bigquery.SchemaField("compound_score", "FLOAT"),
    bigquery.SchemaField("positive_score", "FLOAT"),
    bigquery.SchemaField("negative_score", "FLOAT"),
    bigquery.SchemaField("topics", "STRING", mode="REPEATED"),
    bigquery.SchemaField("fetch_timestamp", "TIMESTAMP"),
]

X_POSTS_SCHEMA = [
    bigquery.SchemaField("ticker", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("post_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("text", "STRING"),
    bigquery.SchemaField("created_at", "TIMESTAMP"),
    bigquery.SchemaField("author_username", "STRING"),
    bigquery.SchemaField("author_name", "STRING"),
    bigquery.SchemaField("author_verified", "BOOLEAN"),
    bigquery.SchemaField("like_count", "INTEGER"),
    bigquery.SchemaField("retweet_count", "INTEGER"),
    bigquery.SchemaField("reply_count", "INTEGER"),
    bigquery.SchemaField("quote_count", "INTEGER"),
    bigquery.SchemaField("bookmark_count", "INTEGER"),
    bigquery.SchemaField("impression_count", "INTEGER"),
    bigquery.SchemaField("url", "STRING"),
    bigquery.SchemaField("sentiment", "STRING"),
    bigquery.SchemaField("compound_score", "FLOAT"),
    bigquery.SchemaField("fetch_timestamp", "TIMESTAMP"),
]

# Table definitions
TABLES = {
    "ceo_profiles": CEO_PROFILES_SCHEMA,
    "quarterly_earnings": QUARTERLY_EARNINGS_SCHEMA,
    "financial_statements": FINANCIAL_STATEMENTS_SCHEMA,
    "stock_prices": STOCK_PRICES_SCHEMA,
    "sector_metrics": SECTOR_METRICS_SCHEMA,
    "company_metrics": COMPANY_METRICS_SCHEMA,
    "reddit_posts": REDDIT_POSTS_SCHEMA,
    "x_posts": X_POSTS_SCHEMA,
}


def create_dataset(client, project_id, dataset_id=DATASET_ID, location="US"):
    """Create BigQuery dataset if it doesn't exist."""
    dataset_ref = f"{project_id}.{dataset_id}"

    try:
        client.get_dataset(dataset_ref)
        print(f"Dataset {dataset_ref} already exists")
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = location
        dataset = client.create_dataset(dataset, exists_ok=True)
        print(f"Created dataset {dataset_ref}")

    return dataset_ref


def create_all_tables(client, project_id, dataset_id=DATASET_ID):
    """Create all tables in the dataset."""
    dataset_ref = create_dataset(client, project_id, dataset_id)

    for table_name, schema in TABLES.items():
        table_ref = f"{dataset_ref}.{table_name}"

        try:
            client.get_table(table_ref)
            print(f"Table {table_ref} already exists")
        except Exception:
            table = bigquery.Table(table_ref, schema=schema)

            # Add partitioning for time-series tables
            if table_name in ["stock_prices", "reddit_posts", "x_posts", "quarterly_earnings"]:
                table.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field="fetch_timestamp" if "fetch_timestamp" in [f.name for f in schema] else "created_utc"
                )

            table = client.create_table(table, exists_ok=True)
            print(f"Created table {table_ref}")


if __name__ == "__main__":
    import os
    from google.cloud import bigquery
    from dotenv import load_dotenv

    # Load environment variables from .env
    load_dotenv()

    # Initialize BigQuery client
    project_id = os.getenv("GCP_PROJECT_ID")
    if not project_id:
        print("❌ Error: GCP_PROJECT_ID not found in environment variables")
        print("Please set GCP_PROJECT_ID in your .env file or environment")
        exit(1)

    print(f"Using GCP Project: {project_id}")
    client = bigquery.Client(project=project_id)

    # Create all tables
    create_all_tables(client, project_id)
    print("\n✅ All BigQuery tables created successfully!")
