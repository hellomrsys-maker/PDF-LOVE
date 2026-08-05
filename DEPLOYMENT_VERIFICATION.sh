#!/bin/bash

# PDFLove Deployment Verification Script
# Verifies that performance optimizations are live on Cloudflare

DOMAIN="pdflove.co.in"
RESULTS_FILE="/tmp/pdflove-deployment-verification.txt"

echo "🔍 PDFLove Performance Deployment Verification" | tee "$RESULTS_FILE"
echo "=============================================" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"
echo "Time: $(date)" >> "$RESULTS_FILE"
echo "Domain: $DOMAIN" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"

# Test 1: Service Worker Cache Version
echo "📋 Test 1: Service Worker Cache Control Headers" | tee -a "$RESULTS_FILE"
RESPONSE=$(curl -s -I "https://$DOMAIN/sw.js" 2>&1)
if echo "$RESPONSE" | grep -q "Cache-Control: no-cache"; then
    echo "✅ PASS: Service worker has no-cache header (will auto-update)" | tee -a "$RESULTS_FILE"
else
    echo "❌ FAIL: Service worker cache header not optimized" | tee -a "$RESULTS_FILE"
    echo "Response: $RESPONSE" >> "$RESULTS_FILE"
fi
echo "" >> "$RESULTS_FILE"

# Test 2: Vendor Files Caching
echo "📋 Test 2: Vendor Files Long-Term Caching" | tee -a "$RESULTS_FILE"
RESPONSE=$(curl -s -I "https://$DOMAIN/vendor/pdf-lib.min.js" 2>&1)
if echo "$RESPONSE" | grep -q "max-age=31536000"; then
    echo "✅ PASS: Vendor files cached for 1 year" | tee -a "$RESULTS_FILE"
else
    echo "❌ FAIL: Vendor caching not optimized" | tee -a "$RESULTS_FILE"
fi
echo "" >> "$RESULTS_FILE"

# Test 3: Compression
echo "📋 Test 3: Gzip Compression for WASM/JS/CSS" | tee -a "$RESULTS_FILE"
RESPONSE=$(curl -s -I "https://$DOMAIN/vendor/tesseract/tesseract.min.js" 2>&1)
if echo "$RESPONSE" | grep -q "Content-Encoding: gzip\|Content-Encoding: br"; then
    ENCODING=$(echo "$RESPONSE" | grep -i "Content-Encoding:" | awk '{print $2}')
    echo "✅ PASS: Content compressed with $ENCODING" | tee -a "$RESULTS_FILE"
else
    echo "⚠️  WARNING: Compression not detected (may be cached uncompressed)" | tee -a "$RESULTS_FILE"
fi
echo "" >> "$RESULTS_FILE"

# Test 4: HTML File Caching
echo "📋 Test 4: Dynamic HTML (no-cache)" | tee -a "$RESULTS_FILE"
RESPONSE=$(curl -s -I "https://$DOMAIN/index.html" 2>&1)
if echo "$RESPONSE" | grep -q "Cache-Control: no-cache"; then
    echo "✅ PASS: index.html won't be cached (updates reach users promptly)" | tee -a "$RESULTS_FILE"
else
    echo "❌ FAIL: index.html may be cached too long" | tee -a "$RESULTS_FILE"
fi
echo "" >> "$RESULTS_FILE"

# Test 5: Icons Caching
echo "📋 Test 5: App Icons Long-Term Caching" | tee -a "$RESULTS_FILE"
RESPONSE=$(curl -s -I "https://$DOMAIN/icons/icon-192.png" 2>&1)
if echo "$RESPONSE" | grep -q "max-age=31536000"; then
    echo "✅ PASS: Icons cached for 1 year (immutable)" | tee -a "$RESULTS_FILE"
else
    echo "⚠️  WARNING: Icon caching may need optimization" | tee -a "$RESULTS_FILE"
fi
echo "" >> "$RESULTS_FILE"

# Test 6: Check if optimized files are present
echo "📋 Test 6: Verify Optimized Assets Deployed" | tee -a "$RESULTS_FILE"

# Check that QPDF binary is present (should be cached)
QPDF_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/vendor/qpdf.wasm")
if [ "$QPDF_STATUS" = "200" ]; then
    echo "✅ PASS: qpdf.wasm deployed (1.3 MB)" | tee -a "$RESULTS_FILE"
else
    echo "❌ FAIL: qpdf.wasm not accessible (HTTP $QPDF_STATUS)" | tee -a "$RESULTS_FILE"
fi

# Check that Tesseract SIMD-LSTM is present
TESSERACT_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/vendor/tesseract/tesseract-core-simd-lstm.wasm.js")
if [ "$TESSERACT_STATUS" = "200" ]; then
    echo "✅ PASS: tesseract-core-simd-lstm.wasm.js deployed (3.8 MB)" | tee -a "$RESULTS_FILE"
else
    echo "❌ FAIL: Tesseract SIMD variant not accessible (HTTP $TESSERACT_STATUS)" | tee -a "$RESULTS_FILE"
fi

# Check that redundant files are NOT present (or still serve but not cached)
QPDF_B64_STATUS=$(curl -s -o /dev/null -w "%{http_code}" "https://$DOMAIN/vendor/qpdf.wasm.b64.js")
if [ "$QPDF_B64_STATUS" = "404" ] || [ "$QPDF_B64_STATUS" = "200" ]; then
    if [ "$QPDF_B64_STATUS" = "200" ]; then
        echo "ℹ️  INFO: qpdf.wasm.b64.js still available (fallback for file:// access)" | tee -a "$RESULTS_FILE"
    else
        echo "✅ PASS: qpdf.wasm.b64.js removed (no longer needed)" | tee -a "$RESULTS_FILE"
    fi
else
    echo "⚠️  WARNING: Unexpected response for qpdf.wasm.b64.js (HTTP $QPDF_B64_STATUS)" | tee -a "$RESULTS_FILE"
fi

echo "" >> "$RESULTS_FILE"

# Test 7: Page Load Performance
echo "📋 Test 7: Basic Connectivity Test" | tee -a "$RESULTS_FILE"
RESPONSE_TIME=$(curl -s -o /dev/null -w "%{time_total}" "https://$DOMAIN/")
if (( $(echo "$RESPONSE_TIME < 3" | bc -l) )); then
    echo "✅ PASS: Main page responds in ${RESPONSE_TIME}s (fast)" | tee -a "$RESULTS_FILE"
elif (( $(echo "$RESPONSE_TIME < 5" | bc -l) )); then
    echo "⚠️  WARNING: Main page responds in ${RESPONSE_TIME}s (acceptable)" | tee -a "$RESULTS_FILE"
else
    echo "❌ FAIL: Main page responds in ${RESPONSE_TIME}s (slow)" | tee -a "$RESULTS_FILE"
fi
echo "" >> "$RESULTS_FILE"

echo "=============================================" >> "$RESULTS_FILE"
echo "Verification Complete!" >> "$RESULTS_FILE"
echo "Results saved to: $RESULTS_FILE" >> "$RESULTS_FILE"
echo "" >> "$RESULTS_FILE"
echo "Next Steps:" | tee -a "$RESULTS_FILE"
echo "1. Review results above" | tee -a "$RESULTS_FILE"
echo "2. If all tests PASS: Deployment successful!" | tee -a "$RESULTS_FILE"
echo "3. If failures: Check Cloudflare dashboard settings" | tee -a "$RESULTS_FILE"
echo "4. Monitor Core Web Vitals: https://pagespeed.web.dev/?url=https://pdflove.co.in/" | tee -a "$RESULTS_FILE"

# Print file location
echo ""
echo "📄 Full verification results saved to:"
echo "   cat $RESULTS_FILE"
