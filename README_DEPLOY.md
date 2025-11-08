# Deep Alpha Copilot - Google Cloud Deployment Guide

This guide explains how to deploy the deep_alpha_copilot data pipeline to Google Cloud Platform with automated daily runs.

## Architecture

- **Cloud Run**: Hosts the data fetching service
- **BigQuery**: Stores all fetched data in structured tables
- **Cloud Scheduler**: Triggers daily data fetches
- **Secret Manager**: Securely stores API credentials
- **Cloud Build**: Automated CI/CD pipeline

## Prerequisites

1. Google Cloud Platform account
2. `gcloud` CLI installed and authenticated
3. Required API credentials:
   - SEC API user agent
   - Reddit API (client ID, secret, user agent)
   - X/Twitter API (bearer token)

## Step 1: Setup Google Cloud Project

```bash
# Set your project ID
export PROJECT_ID="your-project-id"
export REGION="us-central1"

# Set the active project
gcloud config set project $PROJECT_ID

# Enable required APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com
```

## Step 2: Store Secrets in Secret Manager

Store your API credentials securely in Google Cloud Secret Manager:

```bash
# SEC API User Agent
echo -n "YourName your.email@example.com" | \
    gcloud secrets create SEC_USER_AGENT --data-file=-

# Reddit API
echo -n "your_reddit_client_id" | \
    gcloud secrets create REDDIT_CLIENT_ID --data-file=-

echo -n "your_reddit_client_secret" | \
    gcloud secrets create REDDIT_CLIENT_SECRET --data-file=-

echo -n "YourApp/1.0 by u/YourUsername" | \
    gcloud secrets create REDDIT_USER_AGENT --data-file=-

# X/Twitter API
echo -n "your_x_bearer_token" | \
    gcloud secrets create X_BEARER_TOKEN --data-file=-
```

## Step 3: Create BigQuery Dataset and Tables

```bash
# Run the schema setup script
python bigquery_schemas.py
```

Or manually create tables:

```python
from google.cloud import bigquery
from bigquery_schemas import create_all_tables

project_id = "your-project-id"
client = bigquery.Client(project=project_id)
create_all_tables(client, project_id)
```

## Step 4: Deploy to Cloud Run

### Option A: Deploy using gcloud CLI

```bash
# Build and deploy
gcloud run deploy deep-alpha-copilot \
    --source . \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --timeout=900s \
    --max-instances=1 \
    --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID
```

### Option B: Deploy using Cloud Build (CI/CD)

1. Connect your GitHub repository to Cloud Build
2. Push code to the main branch
3. Cloud Build automatically builds and deploys

```bash
# Trigger manual build
gcloud builds submit --config=cloudbuild.yaml
```

## Step 5: Test the Deployment

```bash
# Get the Cloud Run service URL
SERVICE_URL=$(gcloud run services describe deep-alpha-copilot \
    --region=$REGION --format='value(status.url)')

# Test health endpoint
curl $SERVICE_URL/

# Test data fetch (manually)
curl -X POST $SERVICE_URL/fetch \
    -H "Content-Type: application/json" \
    -d '{"tickers": ["NVDA"]}'
```

## Step 6: Setup Cloud Scheduler for Daily Runs

Create a Cloud Scheduler job to run the pipeline daily at 6 AM UTC:

```bash
# Create the scheduler job
gcloud scheduler jobs create http daily-fetch-job \
    --location=$REGION \
    --schedule="0 6 * * *" \
    --uri="$SERVICE_URL/fetch" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{}' \
    --time-zone="UTC"
```

To run with specific tickers:

```bash
gcloud scheduler jobs create http daily-fetch-job \
    --location=$REGION \
    --schedule="0 6 * * *" \
    --uri="$SERVICE_URL/fetch" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{"tickers": ["NVDA", "TSM", "AMD", "AVGO", "ORCL"]}' \
    --time-zone="UTC"
```

## Step 7: Grant Permissions

Ensure the Cloud Run service account has necessary permissions:

```bash
# Get the service account
SERVICE_ACCOUNT=$(gcloud run services describe deep-alpha-copilot \
    --region=$REGION --format='value(spec.template.spec.serviceAccountName)')

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/bigquery.jobUser"

# Grant Secret Manager permissions
gcloud projects add-iam-policy-binding $PROJECT_ID \
    --member="serviceAccount:$SERVICE_ACCOUNT" \
    --role="roles/secretmanager.secretAccessor"
```

## BigQuery Table Structure

The pipeline creates the following tables in the `deep_alpha_copilot` dataset:

- `ceo_profiles` - CEO information and compensation
- `quarterly_earnings` - Quarterly financial results
- `financial_statements` - Income statements, balance sheets, cash flow (flattened)
- `stock_prices` - Historical daily stock prices
- `sector_metrics` - Sector-level aggregated metrics
- `company_metrics` - Company-level metrics
- `reddit_posts` - Reddit posts mentioning tickers
- `x_posts` - X/Twitter posts from official accounts

## Querying Data in BigQuery

```sql
-- Get latest CEO profiles
SELECT * FROM `your-project-id.deep_alpha_copilot.ceo_profiles`
ORDER BY fetch_timestamp DESC
LIMIT 10;

-- Get latest stock prices for NVDA
SELECT * FROM `your-project-id.deep_alpha_copilot.stock_prices`
WHERE ticker = 'NVDA'
ORDER BY date DESC
LIMIT 30;

-- Get sentiment from Reddit posts
SELECT
    ticker,
    DATE(created_utc) as date,
    AVG(compound_score) as avg_sentiment,
    COUNT(*) as post_count
FROM `your-project-id.deep_alpha_copilot.reddit_posts`
GROUP BY ticker, date
ORDER BY date DESC;
```

## Monitoring and Logs

View logs in Cloud Console:

```bash
# View Cloud Run logs
gcloud run services logs read deep-alpha-copilot --region=$REGION

# View Cloud Scheduler logs
gcloud scheduler jobs describe daily-fetch-job --location=$REGION
```

## Cost Estimation

Approximate monthly costs:
- Cloud Run: ~$10-20 (1 instance, 2GB, 15 min/day)
- BigQuery: ~$5-10 storage + ~$5 queries
- Cloud Scheduler: ~$0.10
- Secret Manager: ~$0.10
- **Total: ~$20-35/month**

## Troubleshooting

### "Permission denied" errors
- Ensure service account has proper IAM roles
- Check Secret Manager permissions

### "Timeout" errors
- Increase `--timeout` in Cloud Run deployment
- Consider processing fewer tickers per run

### "Memory exceeded" errors
- Increase `--memory` in Cloud Run deployment
- Process tickers in batches

## Updating the Pipeline

```bash
# Make code changes locally
# git commit and push

# Cloud Build automatically rebuilds and redeploys
# Or manually deploy:
gcloud run deploy deep-alpha-copilot --source . --region=$REGION
```

## Cleanup

To delete all resources:

```bash
# Delete Cloud Run service
gcloud run services delete deep-alpha-copilot --region=$REGION

# Delete Cloud Scheduler job
gcloud scheduler jobs delete daily-fetch-job --location=$REGION

# Delete BigQuery dataset (WARNING: deletes all data)
bq rm -r -f -d $PROJECT_ID:deep_alpha_copilot

# Delete secrets
gcloud secrets delete SEC_USER_AGENT
gcloud secrets delete REDDIT_CLIENT_ID
gcloud secrets delete REDDIT_CLIENT_SECRET
gcloud secrets delete REDDIT_USER_AGENT
gcloud secrets delete X_BEARER_TOKEN
```

## Support

For issues or questions, please check the logs or contact the development team.
