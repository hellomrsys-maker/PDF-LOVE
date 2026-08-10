const CACHE_NAME = 'pdflove-v16';
const APP_SHELL = [
  './', './index.html', './manifest.json',
  // Static pages, precached so an installed offline copy can still show its
  // own terms, privacy policy and help.
  './pages.css',
  './robots.txt',
  './sitemap.xml',
  './about.html',
  './features.html',
  './pricing.html',
  './faq.html',
  './contact.html',
  './security.html',
  './privacy.html',
  './terms.html',
  './cookies.html',
  // Browser/OS favicons — declared in index.html, so precache them or an
  // installed, offline app requests them and gets nothing.
  './favicon.ico',
  './apple-touch-icon.png',
  './favicon-16x16.png',
  './favicon-32x32.png',
  './favicon-192x192.png',
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

// The shell that MUST be cached for the app to open offline at all. If one
// of these genuinely cannot be fetched, installing is pointless.
const CRITICAL = ['./', './index.html', './manifest.json'];

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE_NAME);

    // cache.addAll() is atomic: one 404 anywhere in a 60-entry list rejects
    // the whole thing, the worker never activates, and the installed app
    // then fails to open offline with ERR_FAILED — with no clue why. Cache
    // the critical shell atomically, then everything else individually so a
    // single missing asset degrades one tool instead of the entire app.
    await cache.addAll(CRITICAL);

    const rest = APP_SHELL.filter((u) => !CRITICAL.includes(u));
    const failed = [];
    await Promise.all(rest.map((u) =>
      cache.add(u).catch(() => { failed.push(u); })
    ));
    if (failed.length) {
      console.warn('[PDFLove] not precached (app still works offline):', failed);
    }
  })());
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

// OFFLINE-FIRST, and that is meant literally: if a request is in the cache
// it is served from the cache and NO network request is made at all.
//
// This used to be "cache-first with background refresh", which returned the
// cached copy but had already fired fetch() for every asset — so an
// installed app still put ~17 requests on the wire on every single load,
// even fully cached. An installed PDFLove must be able to sit on an
// air-gapped machine and phone nobody. The network is touched only when
// something genuinely is not cached, or when the user explicitly asks to
// check for an update (see the 'CHECK_UPDATE' message below).
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // The page probes for local vendor files with HEAD before falling back to
  // a CDN. HEAD is not GET, so without this it skipped the worker entirely
  // and put a request on the wire for a file we already hold. Answer from
  // the cache (headers only, as HEAD requires).
  if (req.method === 'HEAD') {
    if (url.origin !== location.origin) return;
    event.respondWith(
      caches.match(req, { ignoreMethod: true }).then((cached) =>
        cached ? new Response(null, { status: 200, headers: cached.headers })
               : fetch(req))
    );
    return;
  }

  if (req.method !== 'GET') return;               // let the network handle it
  // Only ever cache our own static assets. A cross-origin request is the
  // backend (pdflove.apiBase pointed at a separate host — the normal
  // setup when the frontend is on Cloudflare and the API is elsewhere).
  // Caching those would serve a stale GET /jobs/{id}, so the poll loop
  // would read "queued" forever and never see the job finish.
  if (url.origin !== location.origin) return;     // backend is always live
  if (url.pathname.startsWith('/api/')) return;   // same-origin backend too

  // Tool pages are routed by query string (index.html?tool=Merge+PDF), and
  // a Cache API lookup is exact by default, so ?tool=… would miss the
  // precached index.html and leave the app broken offline. Match
  // navigations ignoring the query — the document is identical either way.
  const isNavigation = req.mode === 'navigate';
  const matchOpts = isNavigation ? { ignoreSearch: true } : undefined;

  event.respondWith(
    caches.match(req, matchOpts).then((cached) => {
      // Cached: answer from disk and stop. No fetch is issued.
      if (cached) return cached;

      // Not cached: this is the only path that touches the network.
      return fetch(req).then((res) => {
        // Don't store one copy of the document per ?tool=… URL — that is
        // the same index.html 80-odd times over. The shell is precached.
        const skipStore = isNavigation && url.search;
        if (res && res.status === 200 && !skipStore) {
          const resClone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone)).catch(() => {});
        }
        return res;
      }).catch((err) => {
        // Offline and genuinely uncached — fall back to the app shell for a
        // navigation so the user lands in the app rather than a browser
        // error page.
        if (isNavigation) return caches.match('./index.html');
        throw err;
      });
    })
  );
});

// Explicit, user-initiated update check. Nothing here runs on its own: the
// page posts {type:'CHECK_UPDATE'} only when the user presses the button,
// which is the single moment an installed PDFLove is allowed to reach the
// network for its own sake.
self.addEventListener('message', (event) => {
  const data = event.data || {};
  if (data.type !== 'CHECK_UPDATE') return;
  event.waitUntil((async () => {
    const reply = (payload) => {
      if (event.source) event.source.postMessage({ type: 'UPDATE_RESULT', ...payload });
    };
    try {
      const cache = await caches.open(CACHE_NAME);
      // Compare the shell against the server, bypassing the HTTP cache.
      const res = await fetch('./index.html', { cache: 'reload' });
      if (!res || !res.ok) return reply({ ok: false, reason: 'unreachable' });
      const fresh = await res.clone().text();
      const cachedRes = await cache.match('./index.html');
      const current = cachedRes ? await cachedRes.text() : '';
      if (fresh === current) return reply({ ok: true, updated: false });
      // Something changed: refresh the whole shell in one go, so we never
      // end up with a half-updated app.
      await cache.addAll(APP_SHELL);
      reply({ ok: true, updated: true });
    } catch (e) {
      reply({ ok: false, reason: 'offline' });
    }
  })());
});
