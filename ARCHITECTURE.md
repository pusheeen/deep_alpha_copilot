# Deep Alpha Copilot - Production Architecture

This document explains the production architecture with environment-aware data storage.

## Overview

The application uses a **multi-layer data storage strategy** that works seamlessly in both local development and production:

```
Local Development:     Agent → ./data/ (local files)
Production (Cloud Run): Agent → /tmp/data/ (cache) ← Cloud Storage (source of truth)
```

## Architecture Layers

### Layer 1: Cloud Storage (Primary - Source of Truth)
- **Bucket**: `gs://deep-alpha-copilot-data/`
- **Purpose**: Persistent storage, survives container restarts
- **Cost**: ~$0.06/month
- **Speed**: 10-20ms per file
- **Used in**: Production only

### Layer 2: Local Cache (/tmp/data/ or ./data/)
- **Production**: `/tmp/data/` (ephemeral, populated from Cloud Storage)
- **Local Dev**: `./data/` (persistent on your laptop)
- **Purpose**: Ultra-fast access for agent queries
- **Cost**: Free
- **Speed**: 2-6ms per file

### Layer 3: BigQuery (Analytics & Backup)
- **Dataset**: `deep_alpha_copilot`
- **Purpose**: Historical analytics, SQL queries, data warehouse
- **Cost**: ~$0.60/month
- **Speed**: 900-1700ms (not used for real-time queries)

## Data Flow

### Local Development

```
1. You run: python fetch_data.py
   └─> Fetches from APIs
   └─> Saves to ./data/

2. Agent reads from: ./data/ (2-6ms)
   └─> No cloud connection needed
   └─> Fast iteration
```

### Production (Cloud Run)

```
1. Container starts:
   └─> Downloads from Cloud Storage → /tmp/data/
   └─> Agent ready to serve queries

2. Cloud Scheduler triggers: POST /fetch (daily 6 AM UTC)
   └─> Downloads existing data from Cloud Storage
   └─> Fetches fresh data from APIs
   └─> Saves to /tmp/data/
   └─> Uploads to Cloud Storage (persistence)
   └─> Uploads to BigQuery (analytics)

3. User queries:
   └─> Agent reads from /tmp/data/ (2-6ms)
   └─> Same speed as local!
```

## Environment Detection

The application automatically detects the environment:

```python
# Priority order:
1. DATA_ROOT environment variable (if set)
2. K_SERVICE env var → Cloud Run → /tmp/data/
3. /app/data exists → Docker → /app/data/
4. Default → Local → ./data/
```

## File Structure

```
deep_alpha_copilot/
├── data/                           # Local development only (git ignored)
│   ├── structured/
│   │   ├── financials/*.json
│   │   ├── earnings/*.json
│   │   └── prices/*.csv
│   └── unstructured/
│       ├── reddit/*.json
│       └── news/*.json
│
├── app/
│   ├── main.py                     # FastAPI application
│   ├── scoring/
│   │   └── engine.py               # Auto-detects environment ✅
│   └── agents/
│       └── agents.py               # Uses scoring engine
│
├── storage_helper.py               # Cloud Storage manager
├── fetch_data.py                   # Environment-aware ✅
├── main.py                         # Cloud Run entry point
├── Dockerfile                      # No data/ copied ✅
└── .gitignore                      # Excludes data/ ✅
```

## Performance Comparison

| Metric | Local Dev | Production |
|--------|-----------|------------|
| **Agent read speed** | 2-6ms | 2-6ms (same!) |
| **Data location** | ./data/ | /tmp/data/ |
| **Persistence** | Laptop disk | Cloud Storage |
| **Cloud cost** | $0 | $6-11/month |

## Key Features

### ✅ Environment-Aware
- Automatically uses correct data directory
- No code changes between local and production
- No configuration files needed

### ✅ Fast in Both Environments
- Local: Reads from ./data/ (2-6ms)
- Production: Reads from /tmp/data/ cache (2-6ms)
- Same agent performance everywhere

### ✅ Production-Ready
- Persistent via Cloud Storage
- Scales horizontally (multiple containers share Cloud Storage)
- Stateless containers

### ✅ Developer-Friendly
- Keep local JSON files for development
- No cloud connection needed for local dev
- Easy debugging

## Cloud Storage Structure

```
gs://deep-alpha-copilot-data/
└── data/
    ├── structured/
    │   ├── financials/
    │   │   ├── NVDA_financials.json
    │   │   ├── AMD_financials.json
    │   │   └── ...
    │   ├── earnings/
    │   │   └── *_quarterly_earnings.json
    │   ├── prices/
    │   │   └── *_prices.csv
    │   └── sector_metrics/
    └── unstructured/
        ├── reddit/
        ├── news/
        └── x/
```

## Cost Breakdown

```
Monthly Production Costs:

Cloud Storage:
  - Storage (184 MB):              $0.004
  - Operations (daily sync):       $0.056
  Subtotal:                        $0.06/month

BigQuery:
  - Storage (184 MB):              $0.004
  - Queries (analytics only):      $0.50
  - Streaming inserts:             $0.10
  Subtotal:                        $0.60/month

Cloud Run:
  - Compute (2GB, minimal traffic): $5-10/month

Cloud Scheduler:
  - Daily job:                     $0.10/month

TOTAL:                             $6-11/month
```

Data storage costs are minimal (<$1/month). Main cost is Cloud Run compute.

## Troubleshooting

### Problem: Agent can't find data files

**Local development:**
```bash
# Make sure data/ folder exists
ls -la data/

# Set DATA_ROOT explicitly if needed
export DATA_ROOT=./data
python -m uvicorn app.main:app --reload
```

**Production:**
```bash
# Check Cloud Storage bucket
gsutil ls gs://deep-alpha-copilot-data/data/

# Check container logs
gcloud run logs read deep-alpha-copilot --region=us-central1
```

### Problem: Data not updating in production

**Check Cloud Scheduler:**
```bash
gcloud scheduler jobs describe daily-fetch-job --location=us-central1
gcloud scheduler jobs run daily-fetch-job --location=us-central1
```

**Check Cloud Run logs:**
```bash
gcloud run logs read deep-alpha-copilot --region=us-central1 --limit=100
```

### Problem: Slow queries

**If queries are slow (>100ms):**
- Check if data is cached in /tmp/ (production) or ./data/ (local)
- Verify agent is NOT querying BigQuery directly (should use files)
- Check logs for environment detection

## Next Steps

See [DEPLOYMENT.md](DEPLOYMENT.md) for step-by-step deployment instructions.
