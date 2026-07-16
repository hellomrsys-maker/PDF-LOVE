const CACHE_NAME = 'dockbench-v3';
const APP_SHELL = [
  './', './index.html', './manifest.json',
  // Self-hosted libraries: precached so every tool (including the WASM
  // encryption engine) works fully offline after the first visit.
  './vendor/pdf-lib.min.js',
  './vendor/pdf.min.js',
  './vendor/pdf.worker.min.js',
  './vendor/jszip.min.js',
  './vendor/mammoth.browser.min.js',
  './vendor/jspdf.umd.min.js',
  './vendor/html2canvas.min.js',
  './vendor/qrcode.min.js',
  './vendor/jsqr.js',
  './vendor/jsbarcode.all.min.js',
  './vendor/qpdf.js',
  './vendor/qpdf.wasm',
  './vendor/qpdf.wasm.b64.js',
  './vendor/gifenc.min.js',
  './vendor/fonts/fonts.css',
  './vendor/fonts/fraunces-latin-400-normal.woff2',
  './vendor/fonts/fraunces-latin-600-normal.woff2',
  './vendor/fonts/fraunces-latin-700-normal.woff2',
  './vendor/fonts/ibm-plex-sans-latin-400-normal.woff2',
  './vendor/fonts/ibm-plex-sans-latin-500-normal.woff2',
  './vendor/fonts/ibm-plex-sans-latin-600-normal.woff2',
  './vendor/fonts/ibm-plex-mono-latin-400-normal.woff2',
  './vendor/fonts/ibm-plex-mono-latin-500-normal.woff2',
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(APP_SHELL))
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// Cache-first with background refresh for GET requests. Everything else —
// POSTs to the backend, uploads — must never touch the cache (the Cache API
// rejects non-GET entries, and stale API responses would be wrong anyway).
self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;               // let the network handle it
  const url = new URL(req.url);
  if (url.pathname.startsWith('/api/')) return;   // backend is always live
  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req)
        .then((res) => {
          if (res && res.status === 200) {
            const resClone = res.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone)).catch(() => {});
          }
          return res;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
