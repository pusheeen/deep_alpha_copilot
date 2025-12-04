#!/bin/bash
# Setup Cloud Scheduler jobs for automated data updates

PROJECT_ID="${GCP_PROJECT_ID:-synthetic-time-469701-t7}"
REGION="us-central1"
SERVICE_URL="https://deep-alpha-copilot-420930943775.us-central1.run.app"

echo "Setting up Cloud Scheduler jobs for project: $PROJECT_ID"
echo "Service URL: $SERVICE_URL"
echo ""

# Create scheduler jobs
echo "Creating scheduler jobs..."

# 1. Scoring data (quarterly - 1st day of quarter at 2am PST)
gcloud scheduler jobs create http update-scoring-data \
    --location=$REGION \
    --schedule="0 2 1 */3 *" \
    --uri="$SERVICE_URL/api/scheduler/update/scoring_data" \
    --http-method=POST \
    --description="Update financial statements, earnings, prices (quarterly)" \
    --time-zone="America/Los_Angeles" \
    --attempt-deadline=3600s \
    --project=$PROJECT_ID 2>&1 | grep -v "already exists" || echo "Job already exists"

# 2. Sentiment data (weekly - Monday at 2am PST)
gcloud scheduler jobs create http update-sentiment-data \
    --location=$REGION \
    --schedule="0 2 * * 1" \
    --uri="$SERVICE_URL/api/scheduler/update/sentiment_data" \
    --http-method=POST \
    --description="Update Reddit and X/Twitter sentiment (weekly)" \
    --time-zone="America/Los_Angeles" \
    --attempt-deadline=3600s \
    --project=$PROJECT_ID 2>&1 | grep -v "already exists" || echo "Job already exists"

# 3. News data (daily at 2am PST)
gcloud scheduler jobs create http update-news-data \
    --location=$REGION \
    --schedule="0 2 * * *" \
    --uri="$SERVICE_URL/api/scheduler/update/news_data" \
    --http-method=POST \
    --description="Fetch latest news (past 72 hours, refreshed daily)" \
    --time-zone="America/Los_Angeles" \
    --attempt-deadline=3600s \
    --project=$PROJECT_ID 2>&1 | grep -v "already exists" || echo "Job already exists"

# 4. Institutional flow (quarterly - 1st day of quarter at 2am PST)
gcloud scheduler jobs create http update-institutional-flow \
    --location=$REGION \
    --schedule="0 2 1 */3 *" \
    --uri="$SERVICE_URL/api/scheduler/update/institutional_flow" \
    --http-method=POST \
    --description="Update institutional ownership and flow data (quarterly)" \
    --time-zone="America/Los_Angeles" \
    --attempt-deadline=3600s \
    --project=$PROJECT_ID 2>&1 | grep -v "already exists" || echo "Job already exists"

# 5. Momentum data (daily at 2am PST)
gcloud scheduler jobs create http update-momentum-data \
    --location=$REGION \
    --schedule="0 2 * * *" \
    --uri="$SERVICE_URL/api/scheduler/update/momentum_data" \
    --http-method=POST \
    --description="Update price data and technical indicators for momentum strategy (daily)" \
    --time-zone="America/Los_Angeles" \
    --attempt-deadline=3600s \
    --project=$PROJECT_ID 2>&1 | grep -v "already exists" || echo "Job already exists"

echo ""
echo "✅ Cloud Scheduler jobs setup complete!"
echo ""
echo "To list all jobs:"
echo "  gcloud scheduler jobs list --location=$REGION --project=$PROJECT_ID"
echo ""
echo "To manually trigger a job:"
echo "  gcloud scheduler jobs run update-news-data --location=$REGION --project=$PROJECT_ID"

