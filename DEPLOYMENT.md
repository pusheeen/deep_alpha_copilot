# Deep Alpha Copilot - Deployment Guide

Step-by-step guide to deploy the application to Google Cloud with automated data fetching.

## Prerequisites

1. Google Cloud account
2. `gcloud` CLI installed and authenticated
3. Local data in `./data/` folder (run `python fetch_data.py` first)

## Step 1: Authenticate with Google Cloud

```bash
# Login to Google Cloud
gcloud auth login

# Set your project
gcloud config set project financial-agent-474022

# Set default region
gcloud config set run/region us-central1
```

## Step 2: Enable Required APIs

```bash
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com
```

## Step 3: Create Cloud Storage Bucket

```bash
# Create bucket for data persistence
gsutil mb -l us-central1 gs://deep-alpha-copilot-data

# Upload your current local data (optional but recommended)
gsutil -m cp -r data/* gs://deep-alpha-copilot-data/data/

# Verify upload
gsutil ls -r gs://deep-alpha-copilot-data/data/
```

## Step 4: Create BigQuery Dataset

```bash
# Create dataset
python3 << EOF
from google.cloud import bigquery
from bigquery_schemas import create_all_tables

project_id = "financial-agent-474022"
dataset_id = "deep_alpha_copilot"

client = bigquery.Client(project=project_id)
create_all_tables(client, project_id, dataset_id)
print("✅ BigQuery dataset and tables created")
EOF
```

## Step 5: Setup Secrets in Secret Manager (Optional)

If using Cloud Run with Secret Manager for API keys:

```bash
# SEC API User Agent
echo -n "YourName your.email@example.com" | \
    gcloud secrets create SEC_USER_AGENT --data-file=-

# Reddit API
echo -n "your_reddit_client_id" | \
    gcloud secrets create REDDIT_CLIENT_ID --data-file=-

echo -n "your_reddit_client_secret" | \
    gcloud secrets create REDDIT_CLIENT_SECRET --data-file=-

# X/Twitter API
echo -n "your_x_bearer_token" | \
    gcloud secrets create X_BEARER_TOKEN --data-file=-

# Gemini API
echo -n "your_gemini_api_key" | \
    gcloud secrets create GEMINI_API_KEY --data-file=-
```

## Step 6: Deploy to Cloud Run

```bash
cd /path/to/deep_alpha_copilot

# Deploy
gcloud run deploy deep-alpha-copilot \
    --source . \
    --region=us-central1 \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --cpu=2 \
    --timeout=900s \
    --max-instances=5 \
    --min-instances=0 \
    --set-env-vars=GCP_PROJECT_ID=financial-agent-474022,DATA_ROOT=/tmp/data

# Get service URL
SERVICE_URL=$(gcloud run services describe deep-alpha-copilot \
    --region=us-central1 --format='value(status.url)')

echo "✅ Deployed to: $SERVICE_URL"
```

## Step 7: Test Deployment

```bash
# Health check
curl $SERVICE_URL/

# Manual data fetch (test)
curl -X POST $SERVICE_URL/fetch \
    -H "Content-Type: application/json" \
    -d '{"tickers": ["NVDA"]}'

# Check API endpoint
curl $SERVICE_URL/api/scores/NVDA | jq .
```

## Step 8: Setup Cloud Scheduler (Automated Daily Runs)

```bash
# Delete existing job if it exists
gcloud scheduler jobs delete daily-fetch-job \
    --location=us-central1 --quiet 2>/dev/null || true

# Create new scheduler job (runs daily at 6 AM UTC)
gcloud scheduler jobs create http daily-fetch-job \
    --location=us-central1 \
    --schedule="0 6 * * *" \
    --uri="$SERVICE_URL/fetch" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{}' \
    --time-zone="UTC" \
    --attempt-deadline=900s

echo "✅ Cloud Scheduler configured (daily at 6 AM UTC)"
```

## Step 9: Verify Everything Works

```bash
# 1. Check Cloud Storage has data
gsutil ls gs://deep-alpha-copilot-data/data/structured/financials/ | head -5

# 2. Check BigQuery has data
bq query --use_legacy_sql=false \
    'SELECT ticker, COUNT(*) as row_count
     FROM `financial-agent-474022.deep_alpha_copilot.financial_statements`
     GROUP BY ticker
     ORDER BY row_count DESC
     LIMIT 5'

# 3. Test scheduler manually
gcloud scheduler jobs run daily-fetch-job --location=us-central1

# 4. Check Cloud Run logs
gcloud run logs read deep-alpha-copilot --region=us-central1 --limit=50

# 5. Test agent API
curl $SERVICE_URL/api/scores/NVDA | jq .data.overall
```

## Local Development Workflow

After deployment, you can still develop locally:

```bash
# 1. Run local data fetch (saves to ./data/)
python fetch_data.py

# 2. Run local server
uvicorn app.main:app --reload --port 8000

# 3. Test locally
curl http://localhost:8000/api/scores/NVDA

# 4. When ready, deploy updates
gcloud run deploy deep-alpha-copilot --source .
```

## Environment Variables

The application automatically detects the environment:

| Environment | DATA_ROOT | Where Agent Reads From |
|-------------|-----------|------------------------|
| Local dev | `./data` | Local JSON files |
| Docker (local) | `/app/data` | Mounted files |
| Cloud Run | `/tmp/data` | Cloud Storage cache |

You can override with:
```bash
export DATA_ROOT=/custom/path
```

## Updating Data

### Option 1: Let Cloud Scheduler Do It (Recommended)
- Runs automatically daily at 6 AM UTC
- No manual intervention needed

### Option 2: Manual Trigger
```bash
# Trigger scheduler job manually
gcloud scheduler jobs run daily-fetch-job --location=us-central1

# Or call /fetch endpoint directly
curl -X POST $SERVICE_URL/fetch \
    -H "Content-Type: application/json"
```

### Option 3: Upload Local Data
```bash
# If you have fresh local data, upload it directly
gsutil -m cp -r data/* gs://deep-alpha-copilot-data/data/

# Container will download it on next startup
```

## Monitoring

### Check Scheduler Status
```bash
gcloud scheduler jobs describe daily-fetch-job --location=us-central1
```

### View Cloud Run Logs
```bash
# Recent logs
gcloud run logs read deep-alpha-copilot --region=us-central1 --limit=100

# Follow logs in real-time
gcloud run logs tail deep-alpha-copilot --region=us-central1

# Filter for errors
gcloud run logs read deep-alpha-copilot --region=us-central1 | grep ERROR
```

### Check Cloud Storage Usage
```bash
# List recent files
gsutil ls -lh gs://deep-alpha-copilot-data/data/structured/financials/ | head -10

# Check bucket size
gsutil du -sh gs://deep-alpha-copilot-data
```

### Monitor BigQuery
```bash
# Check table sizes
bq ls --format=pretty financial-agent-474022:deep_alpha_copilot

# Recent data
bq query --use_legacy_sql=false \
    'SELECT MAX(fetch_timestamp) as latest_update
     FROM `financial-agent-474022.deep_alpha_copilot.stock_prices`'
```

## Troubleshooting

### Problem: "Permission denied" errors

```bash
# Get service account
SA=$(gcloud run services describe deep-alpha-copilot \
    --region=us-central1 \
    --format='value(spec.template.spec.serviceAccount)')

# Grant Storage permissions
gcloud projects add-iam-policy-binding financial-agent-474022 \
    --member="serviceAccount:$SA" \
    --role="roles/storage.objectAdmin"

# Grant BigQuery permissions
gcloud projects add-iam-policy-binding financial-agent-474022 \
    --member="serviceAccount:$SA" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding financial-agent-474022 \
    --member="serviceAccount:$SA" \
    --role="roles/bigquery.jobUser"
```

### Problem: Container crashes or timeouts

```bash
# Increase timeout and memory
gcloud run services update deep-alpha-copilot \
    --region=us-central1 \
    --timeout=900s \
    --memory=4Gi \
    --cpu=2
```

### Problem: Data not updating

```bash
# Check if scheduler is enabled
gcloud scheduler jobs describe daily-fetch-job --location=us-central1

# Check last run
gcloud scheduler jobs describe daily-fetch-job --location=us-central1 \
    | grep lastAttemptTime

# Trigger manually
gcloud scheduler jobs run daily-fetch-job --location=us-central1

# Check logs
gcloud run logs read deep-alpha-copilot --region=us-central1 --limit=100
```

## Cost Optimization

### Reduce Costs
```bash
# Set min instances to 0 (scale to zero when idle)
gcloud run services update deep-alpha-copilot \
    --region=us-central1 \
    --min-instances=0

# Reduce memory if not needed
gcloud run services update deep-alpha-copilot \
    --region=us-central1 \
    --memory=1Gi
```

### Monitor Costs
```bash
# Check Cloud Run costs
gcloud run services describe deep-alpha-copilot \
    --region=us-central1 \
    --format='value(status.url)'

# View in Cloud Console
# https://console.cloud.google.com/billing
```

## Cleanup (if needed)

```bash
# Delete Cloud Run service
gcloud run services delete deep-alpha-copilot --region=us-central1

# Delete Cloud Scheduler job
gcloud scheduler jobs delete daily-fetch-job --location=us-central1

# Delete Cloud Storage bucket (WARNING: deletes all data!)
# gsutil -m rm -r gs://deep-alpha-copilot-data

# Delete BigQuery dataset (WARNING: deletes all data!)
# bq rm -r -f financial-agent-474022:deep_alpha_copilot
```

## Next Steps

- See [ARCHITECTURE.md](ARCHITECTURE.md) for system architecture details
- Check [README.md](README.md) for feature documentation
- View logs regularly to monitor data fetch success

## Support

If you encounter issues:
1. Check Cloud Run logs: `gcloud run logs read deep-alpha-copilot --limit=100`
2. Verify Cloud Storage has data: `gsutil ls gs://deep-alpha-copilot-data/data/`
3. Test endpoints manually: `curl $SERVICE_URL/api/scores/NVDA`
