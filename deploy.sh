#!/bin/bash

# Deep Alpha Copilot - Deployment Script
# This script helps deploy the data pipeline to Google Cloud

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
PROJECT_ID="${GCP_PROJECT_ID:-}"
REGION="${GCP_REGION:-us-central1}"
SERVICE_NAME="deep-alpha-copilot"
DATASET_ID="deep_alpha_copilot"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deep Alpha Copilot Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo

# Check if PROJECT_ID is set
if [ -z "$PROJECT_ID" ]; then
    echo -e "${RED}Error: GCP_PROJECT_ID environment variable not set${NC}"
    echo "Please set it with: export GCP_PROJECT_ID=your-project-id"
    exit 1
fi

echo -e "${YELLOW}Project ID: $PROJECT_ID${NC}"
echo -e "${YELLOW}Region: $REGION${NC}"
echo

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check prerequisites
echo "Checking prerequisites..."
if ! command_exists gcloud; then
    echo -e "${RED}Error: gcloud CLI not found. Please install it first.${NC}"
    exit 1
fi

if ! command_exists python3; then
    echo -e "${RED}Error: python3 not found. Please install Python 3.${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Prerequisites OK${NC}"
echo

# Set active project
echo "Setting active GCP project..."
gcloud config set project $PROJECT_ID

# Enable required APIs
echo
echo "Enabling required Google Cloud APIs..."
gcloud services enable \
    cloudbuild.googleapis.com \
    run.googleapis.com \
    bigquery.googleapis.com \
    secretmanager.googleapis.com \
    cloudscheduler.googleapis.com

echo -e "${GREEN}✓ APIs enabled${NC}"
echo

# Create BigQuery dataset and tables
echo "Creating BigQuery dataset and tables..."
python3 bigquery_schemas.py

echo -e "${GREEN}✓ BigQuery setup complete${NC}"
echo

# Deploy to Cloud Run
echo "Deploying to Cloud Run..."
echo "This may take a few minutes..."
gcloud run deploy $SERVICE_NAME \
    --source . \
    --region=$REGION \
    --platform=managed \
    --allow-unauthenticated \
    --memory=2Gi \
    --timeout=900s \
    --max-instances=1 \
    --set-env-vars=GCP_PROJECT_ID=$PROJECT_ID

echo -e "${GREEN}✓ Cloud Run deployment complete${NC}"
echo

# Get service URL
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME \
    --region=$REGION --format='value(status.url)')

echo -e "${GREEN}Service URL: $SERVICE_URL${NC}"
echo

# Test the deployment
echo "Testing deployment..."
curl -s $SERVICE_URL/ | python3 -m json.tool

echo -e "${GREEN}✓ Health check passed${NC}"
echo

# Setup Cloud Scheduler (optional)
read -p "Do you want to setup Cloud Scheduler for daily runs? (y/n) " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "Setting up Cloud Scheduler..."

    # Delete existing job if it exists
    gcloud scheduler jobs delete daily-fetch-job --location=$REGION --quiet 2>/dev/null || true

    # Create new job
    gcloud scheduler jobs create http daily-fetch-job \
        --location=$REGION \
        --schedule="0 6 * * *" \
        --uri="$SERVICE_URL/fetch" \
        --http-method=POST \
        --headers="Content-Type=application/json" \
        --message-body='{}' \
        --time-zone="UTC"

    echo -e "${GREEN}✓ Cloud Scheduler configured (runs daily at 6 AM UTC)${NC}"
fi

echo
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo
echo "Service URL: $SERVICE_URL"
echo
echo "Next steps:"
echo "1. Setup secrets in Secret Manager (see README_DEPLOY.md)"
echo "2. Grant service account permissions (see README_DEPLOY.md)"
echo "3. Test data fetch: curl -X POST $SERVICE_URL/fetch"
echo
echo "For detailed instructions, see README_DEPLOY.md"
echo
