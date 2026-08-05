# Cloudflare Optimization Guide for PDFLove

This document outlines the performance optimizations made for PDFLove on Cloudflare and the settings that need to be configured in the Cloudflare dashboard.

## Performance Improvements Made

### 1. Service Worker Cache Optimization (v16)
**Saves: 9.3 MB on first install (43% reduction)**

- Removed `qpdf.wasm.b64.js` (1.7 MB) from pre-cache
  - Binary format (`qpdf.wasm`) handles HTTP/HTTPS deployments
  - Base64 format still available on-demand for file:// access
  - Service worker fetches on-demand for offline users

- Optimized Tesseract WASM variants
  - Pre-cache only `tesseract-core-simd-lstm.wasm.js` (3.8 MB)
  - Removed `tesseract-core-lstm.wasm.js` (-3.8 MB, rarely needed)
  - Removed `tesseract-core-relaxedsimd-lstm.wasm.js` (-3.8 MB, rarely needed)
  - Tesseract.js auto-detects and loads the best variant from cache
  - Modern browsers have SIMD support; older fallback via lazy-load

- Deferred non-critical tool libraries to lazy-load
  - `mammoth.browser.min.js` (628 KB) — loads on first use of Word/Office tools
  - `xlsx.full.min.js` (862 KB) — loads on first use of spreadsheet tools
  - `jsbarcode`, `qrcode`, `jsqr` (311 KB total) — loads on first barcode/QR tool use

**Result: First install cache reduced from 21.4 MB → ~12 MB**

### 2. HTTP Caching Headers (`frontend/_headers`)

All static assets are now configured with appropriate cache TTLs:

| Asset | TTL | Reason |
|-------|-----|--------|
| `/index.html` | no-cache | Updates reach users promptly |
| `/sw.js` | no-cache | Service worker versioning |
| `/manifest.json` | no-cache | PWA metadata updates |
| `/vendor/*` | 1 year | Content-addressed, never changes |
| `/icons/*` | 1 year | App icons, stable |
| `/vendor/fonts/*` | 1 year | Font files, immutable |
| `*.html` (pages) | 7 days | About, FAQ, Terms, etc. |
| `/pages.css` | 30 days | May update with redesigns |
| `/favicon.ico` | 30 days | Browser cache |
| `*.wasm` | 1 year + gzip | WASM modules, compress on wire |
| `*.js` | 1 year + gzip | JavaScript libraries, compress |
| `*.css` | 1 year + gzip | Stylesheets, compress |

## Cloudflare Dashboard Configuration

### Step 1: Enable Auto-Minify
1. Go to **Speed** > **Optimization**
2. Enable:
   - ✅ Auto Minify (JavaScript, CSS, HTML)
   - This reduces JS/CSS file size by 15-20% with zero performance cost

### Step 2: Enable Brotli Compression
1. Go to **Speed** > **Optimization**
2. Under **HTTP/2 and HTTP/3 Defaults**, ensure:
   - ✅ Brotli is enabled (default: yes)
3. This compresses text assets to 30-40% of original size

### Step 3: Configure Caching Rules (if needed)
If `_headers` is not being respected:
1. Go to **Caching** > **Cache Rules**
2. Add rules for:
   - `/vendor/*` — Max age: 1 year
   - `/icons/*` — Max age: 1 year
   - `/index.html` — No cache
   - `/sw.js` — No cache

### Step 4: Security Headers (Already Set)
The CSP and security headers in `_headers` are complete:
- ✅ X-Content-Type-Options: nosniff
- ✅ X-Frame-Options: DENY
- ✅ CSP with strict inline-script policy (needed for tool definitions)
- ✅ Referrer-Policy: strict-origin-when-cross-origin

### Step 5: Page Rules (Optional, for advanced control)
Create Page Rules for special paths:
- **Pattern**: `pdflove.co.in/api/*`
  - **Disable Caching** (API responses must always be fresh)
  - **Cache Level**: Bypass

### Step 6: Workers Configuration (if using Cloudflare Workers)
If serving via Cloudflare Workers (vs. Workers Pages):
```javascript
// Add to your worker script:
response.headers.set('Cache-Control', 'public, max-age=3600, s-maxage=86400');
response.headers.set('X-Cache', 'HIT'); // for debugging
```

## Performance Metrics to Monitor

### Core Web Vitals (Essential)
1. **Largest Contentful Paint (LCP)** — target: < 2.5s
   - Service worker cache helps reduce LCP for repeat visits
   
2. **First Input Delay (FID)** — target: < 100ms
   - Should be unaffected by our changes
   
3. **Cumulative Layout Shift (CLS)** — target: < 0.1
   - UI redesign completed; monitor for regressions

### Other Metrics
- **Time to First Byte (TTFB)** — should be < 200ms (Cloudflare edge)
- **Cache Hit Ratio** — target: > 90% for `/vendor/*`
- **Bandwidth Saved** — monitor Cloudflare Analytics

### Tools to Check Metrics
1. **PageSpeed Insights**: https://pagespeed.web.dev/
2. **Cloudflare Analytics**: Dashboard > Analytics > Traffic
3. **WebPageTest**: https://www.webpagetest.org/
4. **GTmetrix**: https://gtmetrix.com/

## Deployment Checklist

- [x] Update service worker cache (sw.js v16)
- [x] Optimize `_headers` file
- [ ] Deploy to Cloudflare
- [ ] Purge Cloudflare cache for old version
- [ ] Test on slow network (DevTools throttling)
- [ ] Verify all tools work (especially OCR, encryption)
- [ ] Check Core Web Vitals in PageSpeed Insights
- [ ] Monitor Cloudflare Analytics for cache hits

## Future Optimizations

### Phase 2: Advanced Lazy Loading
- Split index.html into smaller chunks
- Load tools by category on demand
- Further reduce initial bundle

### Phase 3: Edge Caching Strategy
- Use Cloudflare Cache Reserve for WASM files
- Implement stale-while-revalidate for updates
- Cache API responses at edge with smart invalidation

### Phase 4: Image Optimization
- Convert static images to WebP
- Use Cloudflare Image Optimization API
- Responsive image sizing

## Troubleshooting

### Issue: Service worker not updating
**Solution**: Ensure `/sw.js` has `Cache-Control: no-cache` in `_headers`
```bash
curl -I https://pdflove.co.in/sw.js | grep Cache-Control
# Should show: Cache-Control: no-cache
```

### Issue: WASM files returning 404
**Solution**: Verify `/vendor/` directory is present and readable:
```bash
curl -I https://pdflove.co.in/vendor/qpdf.wasm
# Should return 200 OK
```

### Issue: Old assets not updating
**Solution**: Purge Cloudflare cache:
1. Go to **Caching** > **Cache Purge**
2. Select **Purge Everything** (if major update)
3. Or: Purge by URL for specific files

### Issue: Cache hit ratio too low
**Solution**: Check `_headers` is being read:
1. Verify file exists at `frontend/_headers`
2. Redeploy to Cloudflare
3. Wait 5 minutes for propagation
4. Check header: `curl -I <url>`

## References
- Cloudflare Cache: https://developers.cloudflare.com/cache/
- Cloudflare Headers: https://developers.cloudflare.com/workers/platform/static-assets/
- Web Vitals: https://web.dev/vitals/
