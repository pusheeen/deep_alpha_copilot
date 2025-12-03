# GCP Monthly Cost Estimate

**Project**: `synthetic-time-469701-t7`  
**Date**: January 2025  
**Current Storage**: 456.22 MiB (~0.45 GB)

---

## 💰 Cost Breakdown by Service

### 1. Cloud Storage (Standard Storage)

**Current Usage**: 456.22 MiB (~0.45 GB)

| Component | Cost |
|-----------|------|
| **Storage** (0.45 GB × $0.020/GB/month) | **$0.01/month** |
| **Class A Operations** (PUT requests) | ~$0.00 (first 5,000 free) |
| **Class B Operations** (GET requests) | ~$0.00 (first 50,000 free) |
| **Network Egress** | First 1 GB/month free |

**Total Cloud Storage**: **~$0.01/month**

---

### 2. Cloud Run (Application Hosting)

**Configuration** (from `cloudbuild.yaml`):
- Memory: 2 GiB
- CPU: 2 vCPU (default)
- Max Instances: 1
- Min Instances: 0 (scales to zero)
- Region: us-central1

**Assumptions**:
- Low traffic: ~100 requests/day
- Average request duration: 2 seconds
- Idle most of the time (scales to zero)

| Component | Calculation | Cost |
|-----------|-------------|------|
| **CPU Time** | 100 req/day × 2s × 2 vCPU = 400s/day = 0.11 hours/month | $0.01/month |
| **Memory** | 0.11 hours × 2 GiB × $0.0000025/GiB-second | $0.00/month |
| **Request Count** | 100/day × 30 = 3,000 requests/month | $0.00 (first 2M free) |
| **Idle Time** | Scales to zero = $0 | $0.00/month |

**Total Cloud Run**: **~$0.01-0.05/month** (very low traffic)

**If Moderate Traffic** (1,000 requests/day):
- CPU Time: ~1.1 hours/month = **$0.10/month**
- Memory: **$0.01/month**
- **Total**: **~$0.11/month**

---

### 3. BigQuery (Data Warehouse)

**Current Usage**: Dataset `deep_alpha_copilot` with multiple tables

**Storage Costs**:
- Active storage: ~$0.020/GB/month
- Long-term storage (90+ days): ~$0.010/GB/month
- Estimated data: ~1-5 GB (structured data)

| Component | Cost |
|-----------|------|
| **Active Storage** (5 GB × $0.020/GB/month) | **$0.10/month** |
| **Query Processing** | First 1 TB/month free | **$0.00/month** |
| **Streaming Inserts** | First 500 MB/month free | **$0.00/month** |

**Total BigQuery**: **~$0.10/month** (assuming 5 GB storage)

---

### 4. Cloud Scheduler (Automated Jobs)

**Usage**: Daily data fetch job

| Component | Cost |
|-----------|------|
| **Job Executions** | 30 jobs/month × $0.10/job | **$3.00/month** |

**Total Cloud Scheduler**: **$3.00/month**

**Note**: First 3 jobs/month are free, so actual cost: **$2.70/month**

---

### 5. Secret Manager (API Keys Storage)

**Usage**: Storing API keys (Reddit, X/Twitter, Gemini, etc.)

| Component | Cost |
|-----------|------|
| **Secret Versions** | ~10 secrets × $0.06/version/month | **$0.60/month** |
| **Access Operations** | First 10,000 free | **$0.00/month** |

**Total Secret Manager**: **~$0.60/month**

---

### 6. Cloud Build (CI/CD)

**Usage**: Only when deploying (not running continuously)

| Component | Cost |
|-----------|------|
| **Build Minutes** | ~10 minutes/deploy × 4 deploys/month × $0.003/minute | **$0.12/month** |

**Total Cloud Build**: **~$0.12/month** (if deploying monthly)

---

### 7. Container Registry (Docker Images)

**Usage**: Storing Docker images

| Component | Cost |
|-----------|------|
| **Storage** (500 MB × $0.026/GB/month) | **$0.01/month** |
| **Network Egress** | First 1 GB/month free | **$0.00/month** |

**Total Container Registry**: **~$0.01/month**

---

## 📊 Total Monthly Cost Estimate

### Low Traffic Scenario (~100 requests/day)

| Service | Monthly Cost |
|---------|--------------|
| Cloud Storage | $0.01 |
| Cloud Run | $0.01 |
| BigQuery | $0.10 |
| Cloud Scheduler | $2.70 |
| Secret Manager | $0.60 |
| Cloud Build | $0.12 |
| Container Registry | $0.01 |
| **TOTAL** | **~$3.55/month** |

### Moderate Traffic Scenario (~1,000 requests/day)

| Service | Monthly Cost |
|---------|--------------|
| Cloud Storage | $0.01 |
| Cloud Run | $0.11 |
| BigQuery | $0.10 |
| Cloud Scheduler | $2.70 |
| Secret Manager | $0.60 |
| Cloud Build | $0.12 |
| Container Registry | $0.01 |
| **TOTAL** | **~$3.65/month** |

---

## 💡 Cost Optimization Tips

### 1. Reduce Cloud Scheduler Costs
- **Current**: Daily job = $2.70/month
- **Optimize**: Use Cloud Functions instead (free tier: 2M invocations/month)
- **Savings**: **~$2.70/month**

### 2. Optimize Cloud Run
- Already optimized: Scales to zero when idle ✅
- Consider reducing memory to 1 GiB if possible
- **Potential Savings**: ~$0.01/month

### 3. BigQuery Storage
- Use long-term storage for old data (90+ days)
- **Potential Savings**: 50% on old data

### 4. Cloud Storage Lifecycle Policies
- Move old 10-K filings to Nearline/Coldline storage
- **Potential Savings**: 50-80% on archival data

---

## 🎯 Optimized Monthly Cost

**With Optimizations**:
- Replace Cloud Scheduler with Cloud Functions: **~$0.85/month**
- Optimized BigQuery: **~$0.05/month**
- Optimized Storage: **~$0.01/month**
- Cloud Run: **~$0.11/month**
- Other services: **~$0.73/month**

**Optimized Total**: **~$1.75/month**

---

## 📈 Cost Scaling Projections

### Current (Low Traffic)
- **Monthly**: ~$3.55
- **Annual**: ~$42.60

### Moderate Growth (10K requests/day)
- Cloud Run: ~$1.00/month
- **Total**: ~$4.50/month

### High Growth (100K requests/day)
- Cloud Run: ~$10.00/month
- BigQuery queries: ~$5.00/month
- **Total**: ~$18.00/month

---

## ⚠️ Important Notes

1. **Free Tier**: GCP provides $300 free credit for new accounts (valid for 90 days)
2. **Billing Alerts**: Set up billing alerts at $5, $10, $25 thresholds
3. **Actual Costs**: May vary based on actual usage patterns
4. **Data Growth**: Costs will increase as data grows (especially BigQuery)

---

## 🔍 Monitoring Costs

```bash
# View current month's costs
gcloud billing accounts list
gcloud billing budgets list --billing-account=BILLING_ACCOUNT_ID

# Set up billing alerts in Console
# https://console.cloud.google.com/billing
```

---

## Summary

**Current Estimated Monthly Cost**: **~$3.55/month** (low traffic)  
**Optimized Cost**: **~$1.75/month** (with Cloud Functions)  
**Annual Cost**: **~$42.60** (current) or **~$21.00** (optimized)

**Most Expensive Component**: Cloud Scheduler ($2.70/month) - can be replaced with Cloud Functions for free!

