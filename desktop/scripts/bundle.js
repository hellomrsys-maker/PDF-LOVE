#!/usr/bin/env node
/**
 * Copies ../frontend into desktop/app and adapts it for a packaged
 * application. Run automatically by `npm start` and `npm run dist`.
 *
 * The desktop build is genuinely different from the website:
 *   * no service worker — there is no origin to cache, files load from disk;
 *   * no install button — it is already installed;
 *   * no ad slots — a paid/offline build should not carry them;
 *   * no CDN fallbacks — an unreachable CDN must never be attempted.
 */
const fs = require('fs');
const path = require('path');

const SRC = path.resolve(__dirname, '..', '..', 'frontend');
const OUT = path.resolve(__dirname, '..', 'app');

// Web-only files that must not ship inside the desktop package.
const SKIP = new Set(['sw.js', 'manifest.json']);

function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true });
  let files = 0;
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    if (SKIP.has(entry.name)) continue;
    const s = path.join(src, entry.name);
    const d = path.join(dst, entry.name);
    if (entry.isDirectory()) files += copyDir(s, d);
    else { fs.copyFileSync(s, d); files++; }
  }
  return files;
}

function adaptIndex(file) {
  let html = fs.readFileSync(file, 'utf8');
  const before = html.length;

  // 1. Never register a service worker — file:// has no origin for one.
  html = html.replace(
    /if\('serviceWorker' in navigator[\s\S]*?\n\}/,
    '/* desktop build: no service worker — the app is on disk */'
  );

  // 2. Drop the manifest link (no PWA install path in a packaged app).
  html = html.replace(/<link rel="manifest"[^>]*>\s*/g, '');

  // 3. Remove the Install button — it is already installed.
  html = html.replace(
    /<button class="install-btn"[\s\S]*?<\/button>\s*/,
    ''
  );

  // 4. Mark the build so the page can adapt (used by the CSS below and by
  //    any runtime check that wants to know it is the desktop app).
  html = html.replace('<body>', '<body data-build="desktop">');

  // 5. Hide the web-only footer controls and the ad slots.
  html = html.replace('</head>', `<style>
  /* desktop build: nothing here is applicable to a packaged app */
  [data-build="desktop"] #check-update-btn,
  [data-build="desktop"] #check-update-status,
  [data-build="desktop"] .install-btn,
  [data-build="desktop"] .ad-slot { display: none !important; }
</style>
</head>`);

  fs.writeFileSync(file, html);
  return before - html.length;
}

console.log('PDFLove desktop bundler');
console.log('  source :', SRC);
console.log('  output :', OUT);

if (!fs.existsSync(SRC)) {
  console.error('  ERROR: frontend directory not found at ' + SRC);
  process.exit(1);
}

fs.rmSync(OUT, { recursive: true, force: true });
const n = copyDir(SRC, OUT);
console.log('  copied :', n, 'files');

const idx = path.join(OUT, 'index.html');
if (!fs.existsSync(idx)) {
  console.error('  ERROR: index.html missing after copy');
  process.exit(1);
}
const trimmed = adaptIndex(idx);
console.log('  adapted: index.html (-' + trimmed + ' bytes of web-only markup)');

// Fail loudly if the packaged app would still try to reach a service worker.
const check = fs.readFileSync(idx, 'utf8');
for (const [what, re] of [
  ['serviceWorker.register', /serviceWorker\.register/],
  ['manifest link', /rel="manifest"/],
]) {
  if (re.test(check)) {
    console.error('  ERROR: ' + what + ' still present in the desktop build');
    process.exit(1);
  }
}
console.log('  verified: no service worker, no manifest link');
console.log('Done.');
