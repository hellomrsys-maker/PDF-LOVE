/*
 * Enforces the network contract.
 *
 *   node scripts/check-network-surface.js
 *
 * The product's central claim is that it makes no request of its own. That
 * claim decays silently: someone adds a font, an analytics snippet, a CDN
 * icon set, and nothing visibly breaks — the claim just quietly stops being
 * true. This fails the build when a host appears that is not on the list
 * below, so adding one has to be a deliberate, reviewed act.
 *
 * Every entry needs a reason. If you cannot write one, that is the answer.
 */
const fs = require('fs');
const path = require('path');

const FRONTEND = path.join(__dirname, '..', 'frontend');

/* The complete set of hosts the app may reference, and why.
 * Keep in sync with frontend/company/security.html and deploy/API.md. */
const ALLOWED = {
  // --- not requests at all -------------------------------------------
  'www.w3.org':                 'XML namespace URI in SVG markup. Never fetched.',
  'schema.org':                 'JSON-LD vocabulary URI. Never fetched.',
  'schemas.openxmlformats.org': 'OOXML namespace URI inside generated .docx/.xlsx. Never fetched.',
  'dockbench.app':              'Our own canonical/OG URLs. Not fetched by the app.',
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
  'releases.dockbench.app': 'Desktop updater manifest. Desktop app only; a version string out, a signed manifest back.',
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
