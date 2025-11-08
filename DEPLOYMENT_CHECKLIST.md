# Deployment Readiness Checklist

## ✅ Critical Issues Fixed

- [x] Added `google-cloud-storage` to requirements.txt
- [x] Added `google-cloud-bigquery` to requirements.txt
- [x] Added `google-cloud-secret-manager` to requirements.txt
- [x] Added `flask` to requirements.txt
- [x] Fixed CORS configuration (environment-aware)
- [x] Clarified Flask vs FastAPI architecture in Dockerfile
- [x] Added SESSION_SECRET_KEY to .env
- [x] Created .env.example for documentation
- [x] Created comprehensive README_DEV_PROD.md

## 🔧 Configuration Files Ready

- [x] `.env` - Local development environment (gitignored)
- [x] `.env.example` - Template for new developers
- [x] `.gitignore` - Properly excludes secrets and data
- [x] `Dockerfile` - Updated to run Flask app (main.py)
- [x] `requirements.txt` - All dependencies included
- [x] `deploy.sh` - Deployment automation script
- [x] `setup_secrets.sh` - Secret Manager setup script

## 📋 Pre-Deployment Checklist

### Local Testing
- [ ] Run local FastAPI server: `uvicorn app.main:app --reload`
- [ ] Test API endpoints: `/api/scores/NVDA`, `/api/latest-news/NVDA`
- [ ] Run local Flask server: `python main.py`
- [ ] Test health check: `curl http://localhost:8080/`

### Google Cloud Setup
- [ ] Enable required GCP APIs
- [ ] Create Cloud Storage bucket: `gs://deep-alpha-copilot-data`
- [ ] Upload secrets to Secret Manager: `bash setup_secrets.sh`
- [ ] Create BigQuery dataset and tables

### Deployment Configuration
- [ ] Set environment variables in Cloud Run:
  - `GCP_PROJECT_ID=financial-agent-474022`
  - `DATA_ROOT=/tmp/data`
  - `ALLOWED_ORIGINS=https://your-production-domain.com`
- [ ] Configure service account permissions:
  - Storage Object Admin
  - BigQuery Data Editor
  - BigQuery Job User
  - Secret Manager Secret Accessor

### Post-Deployment
- [ ] Test health endpoint: `curl $SERVICE_URL/`
- [ ] Test manual fetch: `curl -X POST $SERVICE_URL/fetch`
- [ ] Setup Cloud Scheduler (daily at 6 AM UTC)
- [ ] Verify Cloud Storage has data
- [ ] Verify BigQuery tables populated
- [ ] Setup monitoring and alerts
- [ ] Setup budget alerts

## 🔒 Security Checklist

- [x] `.env` file is in `.gitignore`
- [x] CORS restricted to specific origins (configurable)
- [x] Strong SESSION_SECRET_KEY generated
- [ ] All API keys stored in Secret Manager (for production)
- [ ] Service account follows principle of least privilege
- [ ] Consider adding API rate limiting (recommended)
- [ ] Consider adding authentication for public endpoints (recommended)

## 🎯 Recommended Next Steps

### Before First Deployment

1. **Review and Update Environment Variables**
   ```bash
   # Edit .env with real credentials
   nano .env

   # Generate new session secret
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. **Test Local Environment**
   ```bash
   # Activate virtual environment
   source venv/bin/activate

   # Install dependencies
   pip install -r requirements.txt

   # Test FastAPI server
   uvicorn app.main:app --reload

   # In another terminal, test endpoints
   curl http://localhost:8000/api/scores/NVDA
   ```

3. **Setup Google Cloud**
   ```bash
   # Login and set project
   gcloud auth login
   gcloud config set project financial-agent-474022

   # Run deployment script
   export GCP_PROJECT_ID=financial-agent-474022
   bash deploy.sh
   ```

### After Deployment

1. **Monitor First Data Fetch**
   ```bash
   # Trigger manual fetch
   curl -X POST $SERVICE_URL/fetch

   # Watch logs
   gcloud run logs tail deep-alpha-copilot --region=us-central1
   ```

2. **Verify Data Pipeline**
   ```bash
   # Check Cloud Storage
   gsutil ls -r gs://deep-alpha-copilot-data/data/ | head -20

   # Check BigQuery
   bq query --use_legacy_sql=false \
       'SELECT COUNT(*) FROM `financial-agent-474022.deep_alpha_copilot.stock_prices`'
   ```

3. **Setup Monitoring**
   - Create uptime checks in Cloud Monitoring
   - Setup error rate alerts
   - Setup budget alerts
   - Configure log-based metrics

## ⚠️ Known Limitations

### Optional Features Not Configured
- **Stripe Payment**: Requires `STRIPE_SECRET_KEY` and `STRIPE_PRICE_ID`
- **Neo4j Database**: Disabled (commented in requirements.txt)
- **Redis**: Disabled (commented in requirements.txt)
- **API Authentication**: Not implemented (public endpoints)
- **Rate Limiting**: Not implemented

### Deployment Decisions Made
- **Application**: Flask app (main.py) for Cloud Run
- **FastAPI app**: For local development only
- **Data Storage**: Cloud Storage + local cache (/tmp/data)
- **CORS**: Environment-aware (restrictive in production)
- **Min Instances**: 0 (scales to zero when idle)

## 📊 Expected Costs

### Monthly (Approximate)
- Cloud Run: $5-10 (with scale-to-zero)
- Cloud Storage: $0.06 (184 MB)
- BigQuery: $0.60
- Cloud Scheduler: $0.10
- **Total**: ~$6-11/month

### Cost Optimization Tips
- Keep min-instances at 0
- Use Cloud Storage caching strategy
- Limit BigQuery queries
- Monitor with budget alerts

## 🆘 Troubleshooting Guide

### Common Issues

**Problem**: Import errors in Cloud Run
- **Solution**: Check all dependencies in requirements.txt
- **Verify**: `pip install -r requirements.txt` works locally

**Problem**: Permission denied errors
- **Solution**: Grant service account correct IAM roles
- **Command**: See "Grant Permissions" in README_DEV_PROD.md

**Problem**: CORS errors
- **Solution**: Set `ALLOWED_ORIGINS` environment variable
- **Example**: `ALLOWED_ORIGINS=https://your-domain.com,http://localhost:8000`

**Problem**: Session errors
- **Solution**: Set `SESSION_SECRET_KEY` environment variable
- **Generate**: `python -c "import secrets; print(secrets.token_urlsafe(32))"`

**Problem**: Data not found
- **Solution**:
  1. Check Cloud Storage has data: `gsutil ls gs://deep-alpha-copilot-data/data/`
  2. Check DATA_ROOT is set: `echo $DATA_ROOT`
  3. Trigger manual fetch: `curl -X POST $SERVICE_URL/fetch`

## 📚 Documentation

- [README_DEV_PROD.md](README_DEV_PROD.md) - Complete dev & prod guide
- [DEPLOYMENT.md](DEPLOYMENT.md) - Detailed deployment steps
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture
- [.env.example](.env.example) - Environment variables template

## ✅ Ready for Deployment

Once all checklist items are complete, you're ready to deploy to production!

```bash
# Quick deployment command
export GCP_PROJECT_ID=financial-agent-474022
bash deploy.sh
```

Good luck! 🚀
