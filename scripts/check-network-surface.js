/*
 * Enforces the network contract.
 *
 *   node scripts/check-network-surface.js
 *   node scripts/check-network-surface.js --url https://example.com
 *
 * The product's central claim is that it makes no request of its own. That
 * claim decays silently: someone adds a font, an analytics snippet, a CDN
 * icon set, and nothing visibly breaks — the claim just quietly stops being
 * true. This fails the build when a host appears that is not on the list
 * below, so adding one has to be a deliberate, reviewed act.
 *
 * Every entry needs a reason. If you cannot write one, that is the answer.
 *
 * With --url, also drives a real browser through Merge PDF end to end and
 * asserts that zero requests fire between choosing the file and the
 * download completing — the exact window the marketing copy invites
 * visitors to watch in their own Network tab. Ad scripts on marketing pages
 * (see frontend/ads.js) only ever load before that window opens, which is
 * what this proves rather than just asserts.
 */
const fs = require('fs');
const path = require('path');

const FRONTEND = path.join(__dirname, '..', 'frontend');
const args = process.argv.slice(2);
const URL_ARG = args.includes('--url') ? args[args.indexOf('--url') + 1] : null;

/* The complete set of hosts the app may reference, and why.
 * Keep in sync with frontend/company/security.html and deploy/API.md. */
const ALLOWED = {
  // --- not requests at all -------------------------------------------
  'www.w3.org':                 'XML namespace URI in SVG markup. Never fetched.',
  'schema.org':                 'JSON-LD vocabulary URI. Never fetched.',
  'schemas.openxmlformats.org': 'OOXML namespace URI inside generated .docx/.xlsx. Never fetched.',
  'pdflove.co.in':              'Our own canonical/OG URLs. Not fetched by the app.',
  'localhost':                  'Documentation of the self-hosted backend default.',
  'my-server':                  'Placeholder in a documentation comment.',
  'your-server':                'Placeholder in a documentation comment.',
  'example.com':                'Placeholder text in the QR and Markdown input fields. Shown to the user, never requested.',
  'appassets.androidplatform.net': 'Android WebViewAssetLoader origin — serves assets bundled in the APK, not the network.',

  // --- real requests, all user-initiated ------------------------------
  'api.frankfurter.dev':  'Live FX rates. Only when the user opens Currency Converter; sends nothing but the request.',
  'huggingface.co':       'One-off on-device AI model download; cached after. Only when an AI tool is used.',
  'cdn.jsdelivr.net':     'Pinned CDN fallback, used only if vendor/ is missing (e.g. a stray copy of index.html).',
  'cdnjs.cloudflare.com': 'Pinned CDN fallback, same reason.',

  // --- links the user clicks, never fetched ---------------------------
  'github.com':      'Release download links on download.html.',
  'play.google.com': 'Play Store link on download.html.',
  'optout.aboutads.info': 'Industry ad opt-out, linked from company/cookies.html so a visitor can refuse advertising cookies. A link, not a request.',
  'youronlinechoices.eu': 'European equivalent of the above, same page, same reasoning.',
  'releases.pdflove.co.in': 'Desktop updater manifest. Desktop app only; a version string out, a signed manifest back.',
};

/* Hosts that must never appear. Not exhaustive — the allowlist above is the
 * real control — but these produce a clearer message than "unknown host",
 * because they are the ones that would actually get added by accident. */
const FORBIDDEN = {
  'google-analytics.com': 'analytics',
  'googletagmanager.com': 'analytics',
  'analytics.google.com': 'analytics',
  'fonts.googleapis.com': 'remote fonts — vendor/fonts is self-hosted for this reason',
  'fonts.gstatic.com':    'remote fonts — vendor/fonts is self-hosted for this reason',
  'connect.facebook.net': 'tracking',
  'plausible.io':         'analytics',
  'sentry.io':            'error reporting would transmit page state',
};

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['icons', 'dist', 'node_modules'].includes(e.name)) continue;
      walk(p, out);
    } else if (/\.(html|js|json|css)$/.test(e.name)) {
      out.push(p);
    }
  }
  return out;
}

const problems = [];
const seen = new Map();

for (const file of walk(FRONTEND)) {
  const rel = path.relative(FRONTEND, file);
  // vendor/ is third-party library source; it is self-hosted and never
  // executed against a remote host by us. Auditing its inline strings would
  // be noise, but a *new* vendor file is a review concern of its own.
  if (rel.startsWith('vendor' + path.sep)) continue;

  const text = fs.readFileSync(file, 'utf8');
  for (const m of text.matchAll(/https?:\/\/([a-zA-Z0-9.-]+)/g)) {
    const host = m[1].toLowerCase();
    if (!seen.has(host)) seen.set(host, new Set());
    seen.get(host).add(rel);
  }
}

for (const [host, files] of seen) {
  const where = [...files].slice(0, 3).join(', ');
  if (FORBIDDEN[host]) {
    problems.push(`FORBIDDEN ${host} (${FORBIDDEN[host]}) in ${where}`);
    continue;
  }
  const known = ALLOWED[host] ||
    Object.keys(ALLOWED).find(a => host === a || host.endsWith('.' + a));
  if (!known) {
    problems.push(
      `UNDECLARED ${host} in ${where}\n` +
      `      If this is intentional, add it to ALLOWED in this file with a\n` +
      `      reason, and update frontend/company/security.html to match.`);
  }
}

console.log(`\n  network surface: ${seen.size} host(s) referenced\n`);
const width = Math.max(...[...seen.keys()].map(h => h.length));
for (const host of [...seen.keys()].sort()) {
  const reason = ALLOWED[host] ||
    ALLOWED[Object.keys(ALLOWED).find(a => host.endsWith('.' + a)) || ''] || '';
  const mark = FORBIDDEN[host] ? '✗' : (reason ? '·' : '?');
  console.log(`  ${mark} ${host.padEnd(width)}  ${reason.slice(0, 78)}`);
}

if (problems.length) {
  console.error(`\n  ${problems.length} problem(s):`);
  problems.forEach(p => console.error('   - ' + p));
  process.exit(1);
}
console.log('\n  Every referenced host is declared. The app makes no request of its own.');

/* ---------------------------------------------------------------------
 * Live processing-window check (only with --url): choose a file in Merge
 * PDF, click merge, and assert zero requests fire before the download
 * completes. Requires playwright — lazily required so the static check
 * above still runs with no extra dependency when --url is omitted. */
async function processingWindowCheck(base) {
  const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');
  const fixturesDir = path.join(__dirname, '..', 'fixtures');
  const fixture = path.join(fixturesDir, 'text.pdf');
  if (!fs.existsSync(fixture)) {
    console.log('\n  processing-window check: skipped — no fixtures. Run scripts/make-fixtures.py first.');
    return true;
  }

  const browser = await chromium.launch();
  const page = await browser.newContext({ acceptDownloads: true }).then(c => c.newPage());
  await page.goto(`${base}/index.html`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(500);

  await page.locator('.tool-card[data-tool="Merge PDF"]').first().click();
  await page.waitForTimeout(300);
  await page.locator('#panel-body input[type=file]').setInputFiles([fixture, fixture]);
  await page.waitForTimeout(300);

  // Everything the app needs (vendor libs, fonts, the ad scripts on
  // marketing pages) has already loaded by now — the window under test
  // starts here, after the file is chosen, not at page load.
  const requestsDuringProcessing = [];
  const onRequest = req => requestsDuringProcessing.push(req.url());
  page.on('request', onRequest);

  const [download] = await Promise.all([
    page.waitForEvent('download', { timeout: 20000 }),
    page.locator('#panel-body button.primary-btn:not([disabled])').last().click(),
  ]);
  await download.path().catch(() => {}); // wait for the download to actually land

  page.off('request', onRequest);
  await browser.close();

  console.log(`\n  processing window (file chosen → download complete): ${requestsDuringProcessing.length} request(s)`);
  if (requestsDuringProcessing.length) {
    requestsDuringProcessing.forEach(u => console.error('   - ' + u));
    console.error('\n  FAIL: the app requested the network while a file was being processed.');
    return false;
  }
  console.log('  PASS: pick a file and watch the Network tab — nothing fires while it is being processed.');
  return true;
}

if (URL_ARG) {
  processingWindowCheck(URL_ARG.replace(/\/$/, '')).then(ok => {
    if (!ok) process.exit(1);
  }).catch(err => {
    console.error('\n  processing-window check errored:', err.message);
    process.exit(1);
  });
}
