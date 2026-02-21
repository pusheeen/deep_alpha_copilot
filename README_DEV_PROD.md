# Deep Alpha Copilot - Development & Production Guide

This guide explains the dual-application architecture and how to run the system locally vs in production.

## 🏗️ Architecture Overview

This project has **two separate applications** for different purposes:

### 1. **Flask App** (`main.py`) - Data Pipeline & Cloud Run
- **Purpose**: Data fetching, BigQuery upload, Cloud Storage sync
- **Used for**: Production deployment on Cloud Run
- **Key endpoints**:
  - `GET /` - Health check
  - `POST /fetch` - Fetch data from APIs and upload to BigQuery
  - `POST /setup` - Create BigQuery tables

### 2. **FastAPI App** (`app/main.py`) - User-Facing API & Chat
- **Purpose**: User interface, chat, scoring API
- **Used for**: Local development and testing
- **Key endpoints**:
  - `GET /` - Main web interface
  - `GET /api/scores/{ticker}` - Get company scores
  - `POST /chat` - AI chat interface
  - Authentication endpoints (login, register, etc.)

## 📋 Prerequisites

- Python 3.11+
- Google Cloud account (for production)
- API keys (see `.env.example`)

## 🔧 Local Development Setup

### Step 1: Clone and Install Dependencies

```bash
cd /path/to/deep_alpha_copilot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Environment Variables

```bash
# Copy example env file
cp .env.example .env

# Edit .env with your actual API keys
nano .env  # or use your preferred editor
```

**Required variables for local dev:**
- `SEC_USER_AGENT` - Your name and email
- `GEMINI_API_KEY` - For AI features
- `SESSION_SECRET_KEY` - Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

**Optional but recommended:**
- `REDDIT_CLIENT_ID`, `REDDIT_CLIENT_SECRET` - For Reddit data
- `X_BEARER_TOKEN` - For Twitter/X data
- `FMP_API_KEY` - For financial data
- `FRED_API_KEY` - For economic data

### Step 3: Fetch Data Locally

```bash
# First time: fetch data to ./data/
python fetch_data.py
```

This will create a `./data/` directory with:
- `structured/financials/` - Financial statements
- `structured/earnings/` - Quarterly earnings
- `structured/prices/` - Stock prices
- `unstructured/news/` - News articles
- `unstructured/reddit/` - Reddit posts

### Step 4: Run Local Development Server

**Option A: FastAPI Server (Recommended for UI development)**

```bash
# Run the FastAPI app with auto-reload
uvicorn app.main:app --reload --port 8000

# Open browser: http://localhost:8000
```

**Option B: Flask Server (For testing data pipeline)**

```bash
# Run the Flask app
python main.py

# Test health: curl http://localhost:8080/
# Test fetch: curl -X POST http://localhost:8080/fetch
```

### Step 5: Test the API

```bash
# Get scores for NVDA
curl http://localhost:8000/api/scores/NVDA | jq .

# Get latest news
curl http://localhost:8000/api/latest-news/NVDA | jq .

# Get price history
curl http://localhost:8000/api/price-history/NVDA?period=1m | jq .
```

## ☁️ Production Deployment (Google Cloud Run)

### Architecture in Production

```
Cloud Scheduler (daily 6 AM UTC)
    ↓
POST /fetch → Flask App (main.py)
    ↓
├── Fetch data from APIs
├── Save to /tmp/data/
├── Upload to BigQuery
└── Upload to Cloud Storage (gs://deep-alpha-copilot-data/)
```

### Deployment Steps

#### 1. Setup Google Cloud

```bash
# Login and set project
gcloud auth login
gcloud config set project financial-agent-474022

# Enable required APIs
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    storage.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com
```

#### 2. Create Cloud Storage Bucket

```bash
# Create bucket
gsutil mb -l us-central1 gs://deep-alpha-copilot-data

# Optional: Upload existing local data
gsutil -m cp -r data/* gs://deep-alpha-copilot-data/data/
```

#### 3. Setup Secrets in Secret Manager

```bash
# Use the provided script
bash setup_secrets.sh

# Or manually create secrets
echo -n "your_gemini_api_key" | \
    gcloud secrets create GEMINI_API_KEY --data-file=-
```

#### 4. Deploy to Cloud Run

```bash
# Option A: Use deployment script
export GCP_PROJECT_ID=financial-agent-474022
bash deploy.sh

# Option B: Manual deployment
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
    --set-env-vars=GCP_PROJECT_ID=financial-agent-474022,DATA_ROOT=/tmp/data,ALLOWED_ORIGINS=https://your-domain.com
```

#### 5. Setup Cloud Scheduler

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe deep-alpha-copilot \
    --region=us-central1 --format='value(status.url)')

# Create scheduler job (runs daily at 6 AM UTC)
gcloud scheduler jobs create http daily-fetch-job \
    --location=us-central1 \
    --schedule="0 6 * * *" \
    --uri="$SERVICE_URL/fetch" \
    --http-method=POST \
    --headers="Content-Type=application/json" \
    --message-body='{}' \
    --time-zone="UTC" \
    --attempt-deadline=900s
```

#### 6. Grant Permissions

```bash
# Get service account
SA=$(gcloud run services describe deep-alpha-copilot \
    --region=us-central1 \
    --format='value(spec.template.spec.serviceAccount)')

# Grant Cloud Storage access
gcloud projects add-iam-policy-binding financial-agent-474022 \
    --member="serviceAccount:$SA" \
    --role="roles/storage.objectAdmin"

# Grant BigQuery access
gcloud projects add-iam-policy-binding financial-agent-474022 \
    --member="serviceAccount:$SA" \
    --role="roles/bigquery.dataEditor"

gcloud projects add-iam-policy-binding financial-agent-474022 \
    --member="serviceAccount:$SA" \
    --role="roles/bigquery.jobUser"

# Grant Secret Manager access
gcloud projects add-iam-policy-binding financial-agent-474022 \
    --member="serviceAccount:$SA" \
    --role="roles/secretmanager.secretAccessor"
```

### Testing Production Deployment

```bash
# Get service URL
SERVICE_URL=$(gcloud run services describe deep-alpha-copilot \
    --region=us-central1 --format='value(status.url)')

# Health check
curl $SERVICE_URL/

# Manual data fetch (test)
curl -X POST $SERVICE_URL/fetch

# Check logs
gcloud run logs read deep-alpha-copilot --region=us-central1 --limit=50
```

## 🔄 Environment Detection

The application automatically detects its environment:

| Environment | DATA_ROOT | Detection Method |
|------------|-----------|------------------|
| **Local Dev** | `./data/` | Default |
| **Docker (local)** | `/app/data/` | `/app/data` exists |
| **Cloud Run** | `/tmp/data/` | `K_SERVICE` env var |
| **Custom** | Custom path | `DATA_ROOT` env var |

## 🐛 Troubleshooting

### Local Development Issues

**Problem: "Module not found" errors**
```bash
# Make sure you're in the virtual environment
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt
```

**Problem: "No data files found"**
```bash
# Fetch data first
python fetch_data.py

# Check data directory
ls -la data/structured/financials/
```

**Problem: CORS errors in browser**
```bash
# Make sure ALLOWED_ORIGINS includes your frontend URL
# In .env:
ALLOWED_ORIGINS=http://localhost:8000,http://localhost:3000
```

### Production Issues

**Problem: "Permission denied" errors**
```bash
# Check service account has correct permissions
# Re-run the "Grant Permissions" commands above
```

**Problem: "Cloud Storage bucket not found"**
```bash
# Create the bucket
gsutil mb -l us-central1 gs://deep-alpha-copilot-data
```

**Problem: Data not updating**
```bash
# Check scheduler status
gcloud scheduler jobs describe daily-fetch-job --location=us-central1

# Trigger manually
gcloud scheduler jobs run daily-fetch-job --location=us-central1

# Check logs
gcloud run logs read deep-alpha-copilot --region=us-central1 --limit=100
```

## 📊 Monitoring

### Cloud Run Metrics

```bash
# View metrics in Cloud Console
open "https://console.cloud.google.com/run/detail/us-central1/deep-alpha-copilot/metrics"

# Check costs
open "https://console.cloud.google.com/billing"
```

### Check Data Freshness

```bash
# Check latest files in Cloud Storage
gsutil ls -lh gs://deep-alpha-copilot-data/data/structured/financials/ | head -10

# Check BigQuery data
bq query --use_legacy_sql=false \
    'SELECT MAX(fetch_timestamp) as latest_update
     FROM `financial-agent-474022.deep_alpha_copilot.stock_prices`'
```

## 🔐 Security Best Practices

1. **Never commit `.env` file** - It's in `.gitignore` ✅
2. **Use Secret Manager in production** - Run `setup_secrets.sh`
3. **Set ALLOWED_ORIGINS** - Restrict CORS to your domain
4. **Rotate API keys periodically**
5. **Monitor costs** - Set up budget alerts in GCP
6. **Use strong SESSION_SECRET_KEY** - Generate with `secrets.token_urlsafe(32)`

## 📝 Cost Estimates

Monthly production costs (approximate):
- **Cloud Run**: $5-10 (2GB RAM, minimal traffic)
- **Cloud Storage**: $0.06 (184 MB)
- **BigQuery**: $0.60 (storage + queries)
- **Cloud Scheduler**: $0.10
- **Total**: ~$6-11/month

## 🤝 Support

For issues:
1. Check logs: `gcloud run logs read deep-alpha-copilot --limit=100`
2. See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed deployment guide
3. See [ARCHITECTURE.md](ARCHITECTURE.md) for system architecture

## 📚 Additional Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Google Cloud Run Documentation](https://cloud.google.com/run/docs)
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
