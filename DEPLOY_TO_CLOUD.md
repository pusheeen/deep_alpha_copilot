# How to Switch to Cloud Mode

Cloud mode is automatically enabled when your application runs on Google Cloud Run. The `K_SERVICE` environment variable (set by Cloud Run) triggers cloud mode.

## Quick Deploy to Cloud Run

### Step 1: Set Your Project ID
```bash
export GCP_PROJECT_ID=financial-agent-474022  # or your project ID
export GCP_REGION=us-central1
```

### Step 2: Deploy Using the Script
```bash
# Make sure deploy.sh is executable
chmod +x deploy.sh

# Deploy to Cloud Run
./deploy.sh
```

This will:
- ✅ Enable required Google Cloud APIs
- ✅ Deploy your app to Cloud Run (automatically enables cloud mode)
- ✅ Set up Cloud Scheduler for daily runs
- ✅ Return your service URL

### Step 3: Verify Cloud Mode is Active

After deployment, check the logs:
```bash
gcloud run logs read deep-alpha-copilot --region=us-central1 --limit=20
```

You should see messages like:
- `✅ Cloud Storage initialized: deep-alpha-copilot-data`
- `Starting background data download from Cloud Storage...`

## Manual Deploy (Alternative)

If you prefer to deploy manually:

```bash
# Set project
gcloud config set project $GCP_PROJECT_ID

# Deploy to Cloud Run
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
    --set-env-vars=GCP_PROJECT_ID=$GCP_PROJECT_ID
```

## What Happens in Cloud Mode?

When deployed to Cloud Run, your app automatically:

1. **Detects Cloud Environment**: `K_SERVICE` env var is set by Cloud Run
2. **Uses Cloud Storage**: Data syncs with `gs://deep-alpha-copilot-data/`
3. **Uses Ephemeral Storage**: `/tmp/data/` for runtime cache
4. **Downloads Data on Startup**: Pulls latest data from Cloud Storage
5. **Uploads New Data**: Saves fetched data back to Cloud Storage

## Testing Cloud Mode Locally (Optional)

To test cloud mode behavior locally without deploying:

```bash
# Set K_SERVICE to simulate Cloud Run
export K_SERVICE=test-service
export GCP_PROJECT_ID=your-project-id
export DATA_ROOT=/tmp/data

# Run the app
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Note: This will try to use Cloud Storage, so make sure you have credentials configured.

## Verify Your Deployment

After deployment, your app will be available at:
- **Cloud Run URL**: `https://deep-alpha-copilot-420930943775.us-central1.run.app`
- **Custom Domain**: `https://www.deepalphacopilot.com`

Check status:
```bash
gcloud run services describe deep-alpha-copilot \
    --region=us-central1 \
    --format='value(status.url)'
```

## Troubleshooting

### Cloud Storage Not Working?
Make sure your Cloud Run service account has permissions:
```bash
# Get service account
SA=$(gcloud run services describe deep-alpha-copilot \
    --region=us-central1 \
    --format='value(spec.template.spec.serviceAccountName)')

# Grant storage permissions
gcloud projects add-iam-policy-binding $GCP_PROJECT_ID \
    --member="serviceAccount:$SA" \
    --role="roles/storage.objectAdmin"
```

### Check Current Mode
The app logs will show:
- **Local mode**: `ℹ️ Cloud Storage disabled (local development mode)`
- **Cloud mode**: `✅ Cloud Storage initialized: deep-alpha-copilot-data`

