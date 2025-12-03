# Guide: Uploading Data to Google Cloud Storage

This guide explains how to upload your local `data/` directory to Google Cloud Storage (GCS).

## Prerequisites

### 1. Google Cloud Account & Project
- You need a Google Cloud account
- A GCP project with billing enabled (if not already set up)

### 2. Install Google Cloud SDK
```bash
# macOS
brew install google-cloud-sdk

# Or download from: https://cloud.google.com/sdk/docs/install
```

### 3. Authenticate with Google Cloud
```bash
# Login to Google Cloud
gcloud auth login

# Set your project
export GCP_PROJECT_ID=your-project-id
gcloud config set project $GCP_PROJECT_ID

# Authenticate for application-default credentials (needed for Python SDK)
gcloud auth application-default login
```

### 4. Enable Required APIs
```bash
gcloud services enable storage.googleapis.com
gcloud services enable storage-component.googleapis.com
```

### 5. Install Python Dependencies
```bash
pip install google-cloud-storage
# Or install all requirements
pip install -r requirements.txt
```

## Method 1: Using the Upload Script (Recommended)

A helper script `upload_to_gcs.py` has been created to simplify the upload process.

### Basic Usage
```bash
# Set your project ID
export GCP_PROJECT_ID=your-project-id

# Upload all data
python upload_to_gcs.py

# Dry run (see what would be uploaded without actually uploading)
python upload_to_gcs.py --dry-run

# Custom bucket name
python upload_to_gcs.py --bucket-name my-custom-bucket

# Custom project ID
python upload_to_gcs.py --project-id your-project-id
```

### What the Script Does
1. Checks for authentication
2. Creates the bucket if it doesn't exist (default: `deep-alpha-copilot-data`)
3. Uploads all files from `./data/` to `gs://bucket-name/data/`
4. Preserves directory structure
5. Shows progress and summary

## Method 2: Using gsutil (Command Line)

### Create Bucket (if it doesn't exist)
```bash
gsutil mb -l us-central1 gs://deep-alpha-copilot-data
```

### Upload Data
```bash
# Upload entire data directory
gsutil -m cp -r data/* gs://deep-alpha-copilot-data/data/

# The -m flag enables parallel uploads for faster transfer
```

### Verify Upload
```bash
# List files in bucket
gsutil ls -r gs://deep-alpha-copilot-data/data/

# Check specific directory
gsutil ls gs://deep-alpha-copilot-data/data/structured/financials/
```

## Method 3: Using Python Directly

If you want to upload programmatically:

```python
from google.cloud import storage
from pathlib import Path

# Initialize client
client = storage.Client(project="your-project-id")
bucket = client.get_bucket("deep-alpha-copilot-data")

# Upload a file
local_file = Path("data/structured/financials/NVDA_financials.json")
blob = bucket.blob(f"data/structured/financials/NVDA_financials.json")
blob.upload_from_filename(str(local_file))
```

## Method 4: Modify storage_helper.py (For Development)

The `storage_helper.py` currently only works in production (`K_SERVICE` environment variable set). To enable uploads from local development:

### Option A: Set K_SERVICE temporarily
```bash
export K_SERVICE=local-dev
export GCP_PROJECT_ID=your-project-id
python -c "from storage_helper import get_storage_manager; sm = get_storage_manager(); sm.upload_data_folder()"
```

### Option B: Modify storage_helper.py
Change line 18 from:
```python
IS_PRODUCTION = bool(os.getenv("K_SERVICE"))
```
to:
```python
IS_PRODUCTION = bool(os.getenv("K_SERVICE")) or bool(os.getenv("FORCE_GCS_UPLOAD"))
```

Then run:
```bash
export FORCE_GCS_UPLOAD=1
export GCP_PROJECT_ID=your-project-id
python -c "from storage_helper import get_storage_manager; sm = get_storage_manager(); sm.upload_data_folder()"
```

## Required Permissions

Your Google Cloud account needs these IAM roles:
- **Storage Admin** (`roles/storage.admin`) - Full control of buckets and objects
- Or at minimum:
  - **Storage Object Creator** (`roles/storage.objectCreator`) - Can create objects
  - **Storage Object Admin** (`roles/storage.objectAdmin`) - Can manage objects

### Grant Permissions (if needed)
```bash
# For your user account
gcloud projects add-iam-policy-binding YOUR_PROJECT_ID \
    --member="user:your-email@gmail.com" \
    --role="roles/storage.admin"
```

## Bucket Configuration

### Default Bucket Name
- **Bucket**: `deep-alpha-copilot-data`
- **Location**: `us-central1` (US Central)
- **Storage Class**: Standard (default)

### Create Custom Bucket
```bash
# Create bucket in specific region
gsutil mb -l us-central1 gs://your-bucket-name

# Set lifecycle policy (optional - auto-delete old files)
gsutil lifecycle set lifecycle.json gs://your-bucket-name
```

## Cost Considerations

### Storage Costs
- **Standard Storage**: ~$0.020 per GB/month
- **Nearline Storage**: ~$0.010 per GB/month (for infrequent access)
- **Coldline Storage**: ~$0.004 per GB/month (for archival)

### Network Egress Costs
- **Free**: First 1 GB/month per project
- **After**: ~$0.12 per GB (varies by region)

### Estimate Your Costs
```bash
# Check current data size
du -sh data/

# Check bucket size after upload
gsutil du -sh gs://deep-alpha-copilot-data
```

## Troubleshooting

### Error: "Permission denied" or "403 Forbidden"
```bash
# Check authentication
gcloud auth list

# Re-authenticate
gcloud auth application-default login

# Check IAM permissions
gcloud projects get-iam-policy YOUR_PROJECT_ID
```

### Error: "Bucket not found"
```bash
# Create the bucket first
gsutil mb -l us-central1 gs://deep-alpha-copilot-data
```

### Error: "Project not found"
```bash
# Verify project ID
gcloud config get-value project

# Set correct project
gcloud config set project YOUR_PROJECT_ID
export GCP_PROJECT_ID=YOUR_PROJECT_ID
```

### Error: "Module not found: google.cloud.storage"
```bash
pip install google-cloud-storage
```

### Slow Upload Speed
```bash
# Use parallel uploads with gsutil
gsutil -m cp -r data/* gs://deep-alpha-copilot-data/data/

# Or increase parallelism in Python script
# (already enabled in upload_to_gcs.py)
```

## Verification

After uploading, verify the data:

```bash
# List all files
gsutil ls -r gs://deep-alpha-copilot-data/data/

# Count files
gsutil ls -r gs://deep-alpha-copilot-data/data/ | wc -l

# Check specific file
gsutil cat gs://deep-alpha-copilot-data/data/structured/financials/NVDA_financials.json | head -20

# View in browser
# https://console.cloud.google.com/storage/browser/deep-alpha-copilot-data/data
```

## Next Steps

After uploading to GCS:

1. **Deploy to Cloud Run**: The application will automatically download data on startup
2. **Set up Cloud Scheduler**: Automate daily data fetches and uploads
3. **Monitor Costs**: Set up billing alerts in GCP Console

## Related Files

- `upload_to_gcs.py` - Upload script
- `storage_helper.py` - Storage manager (production use)
- `DEPLOYMENT.md` - Full deployment guide
- `main.py` - Cloud Run entry point (includes upload logic)

## Quick Reference

```bash
# Complete upload workflow
export GCP_PROJECT_ID=your-project-id
gcloud auth application-default login
python upload_to_gcs.py

# Or using gsutil
gsutil -m cp -r data/* gs://deep-alpha-copilot-data/data/
```

