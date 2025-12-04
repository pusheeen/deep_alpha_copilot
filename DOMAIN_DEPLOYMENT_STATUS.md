# Domain Deployment Status

## ✅ Latest Deployment

**Revision**: `deep-alpha-copilot-00058-2r2`  
**Deployed**: December 4, 2025  
**Status**: ✅ Active and serving 100% of traffic

## 🌐 Domain URLs

### Cloud Run Default URL
```
https://deep-alpha-copilot-420930943775.us-central1.run.app
```
**Status**: ✅ Active - Latest version deployed

### Custom Domain
```
https://www.deepalphacopilot.com
```
**Status**: ✅ Active - Responding to requests

## 🔍 Verification

**Latest Revision**: `deep-alpha-copilot-00058-2r2`

This revision includes:
- ✅ Ticker-first UI with background loading
- ✅ Progress bar for background ticker loading
- ✅ 3-tier news interpretation fallback system
- ✅ OpenRouter API support (Gwen, Llama, Mistral, etc.)
- ✅ Updated README with accurate information

## 📝 Notes

Cloud Run automatically routes **all traffic** (including custom domains) to the **latest ready revision** by default. This means:

- ✅ `www.deepalphacopilot.com` → Points to latest revision
- ✅ `deep-alpha-copilot-420930943775.us-central1.run.app` → Points to latest revision
- ✅ Both URLs serve the same latest version

**If the custom domain is configured** (via DNS or Cloud Run domain mapping), it will automatically serve the latest deployed version.

## 🔧 To Verify Custom Domain Mapping

If you want to explicitly configure the custom domain in Cloud Run:

```bash
gcloud run domain-mappings create \
  --service deep-alpha-copilot \
  --domain www.deepalphacopilot.com \
  --region us-central1
```

However, if the domain is already working (which it appears to be), it's likely configured through:
- DNS records pointing to Cloud Run
- External load balancer
- Or already mapped (may not show in domain-mappings list if configured differently)

---

**Conclusion**: Both URLs should be serving the latest version (`deep-alpha-copilot-00058-2r2`) with all new features! 🎉

