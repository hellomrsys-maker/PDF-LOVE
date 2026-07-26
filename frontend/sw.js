const CACHE_NAME = 'dockbench-v6';

// The app shell is served network-first (see the fetch handler): these are
// the files that change when the app is updated, so a cached copy must
// never win over a newer one on the server.
const SHELL_PATHS = ['/', '/index.html', '/manifest.json'];

const APP_SHELL = [
  './', './index.html', './manifest.json',
  // Installable-app icons referenced by manifest.json.
  './icons/icon-48.png',
  './icons/icon-72.png',
  './icons/icon-96.png',
  './icons/icon-128.png',
  './icons/icon-144.png',
  './icons/icon-152.png',
  './icons/icon-192.png',
  './icons/icon-384.png',
  './icons/icon-512.png',
  './icons/icon-maskable-192.png',
  './icons/icon-maskable-512.png',
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
  './vendor/xlsx.full.min.js',
  // On-device OCR engine + English model — offline after first visit.
  './vendor/tesseract/tesseract.min.js',
  './vendor/tesseract/worker.min.js',
  './vendor/tesseract/tesseract-core-lstm.wasm.js',
  './vendor/tesseract/tesseract-core-simd-lstm.wasm.js',
  './vendor/tesseract/tesseract-core-relaxedsimd-lstm.wasm.js',
  './vendor/tesseract/lang/eng.traineddata.gz',
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

// Without these the app cannot function at all; everything else is a
// best-effort offline extra.
const REQUIRED = ['./index.html'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);

    // Deliberately NOT cache.addAll(): that is atomic, so one 404 or one
    // flaky response aborts the whole install and the app silently ends up
    // with no offline cache at all. Fetch each asset independently, fail
    // only on the ones the app genuinely cannot run without, and report
    // the rest so a broken deploy is visible instead of silent.
    const failed = [];
    await Promise.all(APP_SHELL.map(async (url) => {
      try {
        const res = await fetch(url, { cache: 'reload' });
        if (!res.ok) throw new Error('HTTP ' + res.status);
        await cache.put(url, res);
      } catch (err) {
        failed.push(url + ' (' + err.message + ')');
      }
    }));

    if (failed.length) {
      console.warn('[dockbench sw] %d asset(s) not precached:', failed.length, failed);
    }
    const missingRequired = REQUIRED.filter(u => failed.some(f => f.startsWith(u)));
    if (missingRequired.length) {
      throw new Error('Cannot install: ' + missingRequired.join(', '));
    }
  })());
  // Note: no skipWaiting() here. The new worker waits until the page tells
  // it to activate, so a running tab is never swapped underneath the user
  // mid-operation. index.html prompts, then posts SKIP_WAITING.
});

self.addEventListener('message', (event) => {
  if (event.data === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((names) =>
      Promise.all(names.filter(n => n !== CACHE_NAME).map(n => caches.delete(n)))
    )
  );
  self.clients.claim();
});

// Two strategies, because the two kinds of asset have opposite requirements:
//
//   app shell (index.html, manifest.json)  -> NETWORK-FIRST
//     These change on every deploy. Serving them cache-first meant an
//     installed PWA could keep showing an old build indefinitely: the
//     background refresh only ever helped the *next* load, so a user who
//     had loaded a broken version stayed on it. Network wins when reachable;
//     the cache is the offline fallback.
//
//   vendor/, icons/, fonts  -> CACHE-FIRST
//     Version-pinned, immutable files, several of them megabytes (the
//     Tesseract WASM core, the qpdf engine). Re-validating these on every
//     navigation would make the app slow for no benefit.
//
// Everything non-GET (uploads, backend POSTs) bypasses the cache entirely —
// the Cache API rejects non-GET entries and a stale API response is wrong
// by definition.
function isShell(url) {
  return SHELL_PATHS.includes(url.pathname) || url.pathname.endsWith('/index.html');
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  if (req.method !== 'GET') return;               // let the network handle it
  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return; // third-party: not ours
  if (url.pathname.startsWith('/api/')) return;   // backend is always live

  // Navigations and the shell: network-first.
  if (req.mode === 'navigate' || isShell(url)) {
    event.respondWith((async () => {
      try {
        const res = await fetch(req);
        if (res && res.ok) {
          const clone = res.clone();
          caches.open(CACHE_NAME).then(c => c.put(req, clone)).catch(() => {});
        }
        return res;
      } catch (err) {
        // Offline: fall back to the cached shell, then to index.html so a
        // deep link still resolves to the app rather than a browser error.
        return (await caches.match(req))
            || (await caches.match('./index.html'))
            || Response.error();
      }
    })());
    return;
  }

  // Everything else: cache-first with a background refresh.
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
