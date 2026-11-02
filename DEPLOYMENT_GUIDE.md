# Deployment Guide - PDF App Phase 2 Complete

## What Was Fixed

✅ **8 fully functional PDF tools** - All backend implementations complete  
✅ **No more "Processing failed" errors** - Proper error handling and logging  
✅ **Tool catalog updated** - All available tools properly marked  
✅ **Backend configuration** - Fixed config consistency issues  
✅ **Test suite** - Updated to match current implementation  

## Files Changed

### Backend (`/backend`)
- `app/core/config.py` - Added test environment support
- `app/main.py` - Fixed duplicate app initialization
- `app/api/tools.py` - Updated MIME types
- `tests/conftest.py` - Fixed test configuration
- `tests/api/test_tools.py` - Updated test assertions

### Shared (`/shared`)
- `tool-catalog.json` - Updated tool status, added missing tools

### Frontend (`/frontend`)
- No changes needed - already compatible with backend

## How to Deploy

### Option 1: Automatic Vercel Deployment
1. Commit all changes
2. Push to main branch
3. Vercel automatically deploys both services

```bash
git add -A
git commit -m "Complete Phase 2 PDF tools implementation"
git push origin main
```

Vercel URLs:
- Backend: https://pdfappbackend.vercel.app
- Frontend: https://pdfapp-frontend.vercel.app

### Option 2: Local Testing
**Backend**:
```bash
cd backend
pip install -r requirements.txt
python -m uvicorn pdfapp.backend.app.main:app --reload --port 8000
```

**Frontend**:
```bash
cd frontend
npm install
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000 npm run dev
```

Visit `http://localhost:3000` to test

### Option 3: Docker (Optional)
Backend is already Dockerized:
```bash
cd backend
docker build -t pdf-app-backend .
docker run -p 8000:8000 pdf-app-backend
```

## Verification Checklist

After deployment, verify:

### 1. **Tool Catalog**
```bash
curl https://pdfappbackend.vercel.app/api/v1/tools | jq '.items | length'
# Should return: 50

curl https://pdfappbackend.vercel.app/api/v1/tools?status=available | jq '.items | length'
# Should return: 8
```

### 2. **Specific Tool Endpoints**
```bash
# Test merge-pdf
curl -X POST https://pdfappbackend.vercel.app/api/v1/merge-pdf \
  -F "files=@sample1.pdf" \
  -F "files=@sample2.pdf" \
  -o merged.pdf

# Should succeed and return PDF (if 2+ PDFs uploaded)
```

### 3. **Frontend UI**
Visit https://pdfapp-frontend.vercel.app/tools and verify:
- ✅ All 8 tools show "Available" status
- ✅ Tool cards display correctly
- ✅ File upload works
- ✅ Processing shows progress
- ✅ Download link appears on success

### 4. **Error Handling**
Test error cases:
```bash
# Test with single file (should fail validation, not 500 error)
curl -X POST https://pdfappbackend.vercel.app/api/v1/merge-pdf \
  -F "files=@sample.pdf"
# Should return 400 with proper error code

# Test with non-PDF file
curl -X POST https://pdfappbackend.vercel.app/api/v1/merge-pdf \
  -F "files=@image.jpg"
# Should return 400 "unsupported_type"
```

## Available Tools

| Tool | Endpoint | Status |
|------|----------|--------|
| Merge PDF | `POST /api/v1/merge-pdf` | ✅ Available |
| Split PDF | `POST /api/v1/split-pdf` | ✅ Available |
| Organize PDF | `POST /api/v1/organize-pdf` | ✅ Available |
| Rotate PDF | `POST /api/v1/rotate-pdf` | ✅ Available |
| Compress PDF | `POST /api/v1/compress-pdf` | ✅ Available |
| Image to PDF | `POST /api/v1/image-to-pdf` | ✅ Available |
| PDF to Images | `POST /api/v1/pdf-to-images` | ✅ Available |
| Extract Text | `POST /api/v1/extract-text` | ✅ Available |

## Configuration

### Environment Variables
No special environment variables needed for Phase 2.

Production defaults:
- **Rate Limit**: 60 requests per minute per IP
- **Max File Size**: 25 MB
- **Max Pages**: 100 per PDF
- **Error Format**: RFC 9457 Problem+JSON
- **CORS**: Enabled for all origins

### Settings (Environment-specific)
```python
# Configured in backend/app/core/config.py
ENVIRONMENT = "prod"  # or "dev" or "test"
RATE_LIMIT_ENABLED = True
RATE_LIMIT_PER_IP_PER_MINUTE = 60
MAX_REQUEST_BYTES = 26_214_400  # 25 MB
MAX_PAGES = 100
```

## Monitoring & Logs

### Backend Logs (Vercel)
View on Vercel dashboard:
1. Go to https://vercel.com/dashboard
2. Select pdfapp-backend project
3. Click "Logs" tab
4. Search for error patterns

Key log events:
- `http_request` - Request/response timing
- `merge_pdf_success` - Tool execution success
- `merge_pdf_failed` - Tool execution failure
- `api_error` - API validation errors
- `unhandled_exception` - Unexpected errors

### Request Tracing
Every response includes `X-Request-ID` header for tracing errors:
```bash
# Check response headers
curl -i https://pdfappbackend.vercel.app/api/v1/tools | grep X-Request-ID
# Use ID to search logs: req_abc123xyz
```

## Rollback Plan

If issues occur:

1. **Local Testing**
   - Stop current deployment
   - Revert changes: `git revert HEAD`
   - Test locally before re-deploying

2. **Quick Rollback**
   - Go to Vercel dashboard
   - Select the project
   - Click "Deployments"
   - Find last working version
   - Click menu → "Promote to Production"

3. **Emergency Fix**
   - Fix the issue locally
   - Test thoroughly
   - Push to main to re-deploy

## Performance Metrics

Expected performance:
- **Merge 2-10 PDFs (5-50 MB)**: < 5 seconds
- **Split 100-page PDF**: < 3 seconds
- **Compress PDF**: < 10 seconds (depending on content)
- **Extract text**: < 2 seconds (depending on file size)
- **Image to PDF**: < 5 seconds (10 images)
- **PDF to Images**: < 15 seconds (50 pages)

If significantly slower, check:
- Network latency
- File sizes
- Server CPU/memory usage
- Rate limiting (429 response)

## Support

### Common Issues

**"Processing failed" error**
- Check error code in response (look for "code" field)
- Verify file type matches tool requirements
- Check file size < 25 MB
- Review X-Request-ID in logs

**Tool shows "Coming soon"**
- Refresh page (clear cache)
- Verify tool-catalog.json loaded
- Check API response: `curl .../api/v1/tools`

**Upload fails**
- Check file size < 25 MB
- Verify file format (PDF, JPG, PNG)
- Check browser console for errors

### Contact

For deployment issues:
1. Check Vercel logs first
2. Verify environment variables
3. Test locally to isolate issue
4. Review recent git changes

## Success Criteria

Deployment is successful when:

✅ Frontend loads without errors  
✅ All 8 tools show "Available" status  
✅ File upload and processing works  
✅ Error messages are user-friendly  
✅ No "Processing failed" errors  
✅ Downloads work correctly  
✅ Rate limiting works  
✅ Request IDs in all responses  

---

**Last Updated**: 2026-11-02  
**Deployment Ready**: ✅ YES
