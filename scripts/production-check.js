/*
 * Check what the deployed site actually sends — headers, caching, and
 * whether every URL it advertises to search engines really exists.
 *
 * A config file saying a header should be set and a server sending it are
 * different things, and only one of them affects a visitor.
 *
 *   node scripts/production-check.js --url https://example.com
 *   node scripts/production-check.js --url https://example.com --sitemap
 */
const https = require('https');
const http = require('http');
const { URL } = require('url');

const args = process.argv.slice(2);
const BASE = (args.includes('--url') ? args[args.indexOf('--url') + 1] : '').replace(/\/$/, '');
const SITEMAP_MODE = args.includes('--sitemap');
if (!BASE) {
  console.error('--url is required');
  process.exit(1);
}

function fetchOnce(url, method = 'GET') {
  return new Promise(resolve => {
    const u = new URL(url);
    const lib = u.protocol === 'https:' ? https : http;
    const req = lib.request(u, { method, timeout: 25000,
      headers: { 'User-Agent': 'pdflove-production-check' } }, res => {
      const chunks = [];
      res.on('data', c => chunks.push(c));
      res.on('end', () => resolve({
        status: res.statusCode,
        headers: res.headers,
        body: Buffer.concat(chunks).toString('utf8'),
      }));
    });
    req.on('timeout', () => { req.destroy(); resolve({ status: 0, headers: {}, body: '', error: 'timeout' }); });
    req.on('error', e => resolve({ status: 0, headers: {}, body: '', error: e.message }));
    req.end();
  });
}

const failures = [];
const check = (ok, label, detail) => {
  console.log(`  ${ok ? 'OK  ' : 'FAIL'}  ${label}${detail ? ` — ${detail}` : ''}`);
  if (!ok) failures.push(`${label}${detail ? ` — ${detail}` : ''}`);
};

async function headers() {
  console.log(`\nHeaders and caching at ${BASE}\n`);
  const root = await fetchOnce(`${BASE}/index.html`);
  if (!root.status) {
    check(false, 'the site responds', root.error);
    return;
  }
  check(root.status === 200, 'index.html returns 200', `got ${root.status}`);

  const h = root.headers;
  // Security headers, as declared in frontend/_headers.
  const want = {
    'content-security-policy': null,
    'x-content-type-options': 'nosniff',
    'referrer-policy': null,
    'x-frame-options': null,
    'permissions-policy': null,
  };
  for (const [name, expect] of Object.entries(want)) {
    const got = h[name];
    if (!got) { check(false, `${name} is sent`, 'header absent'); continue; }
    check(!expect || got.toLowerCase().includes(expect),
      `${name} is sent`, expect ? `= ${got}` : `${String(got).slice(0, 48)}…`);
  }

  // The shell must not be cached hard, or a deploy never reaches anyone.
  const cc = String(h['cache-control'] || '');
  check(/no-cache|max-age=0|must-revalidate/.test(cc),
    'app shell is revalidated rather than cached forever', `cache-control: ${cc || 'absent'}`);

  // Immutable assets should be cached hard, or every visit re-downloads them.
  const vendor = await fetchOnce(`${BASE}/vendor/pdf-lib.min.js`);
  if (vendor.status === 200) {
    const vcc = String(vendor.headers['cache-control'] || '');
    check(/immutable|max-age=\d{5,}/.test(vcc),
      'vendor assets are cached long-term', `cache-control: ${vcc || 'absent'}`);
  } else {
    check(false, 'vendor asset is served', `got ${vendor.status}`);
  }

  for (const [path, type] of [['/sitemap.xml', 'xml'], ['/robots.txt', 'text/plain'],
                              ['/manifest.json', 'json']]) {
    const r = await fetchOnce(`${BASE}${path}`);
    check(r.status === 200 && String(r.headers['content-type'] || '').includes(type),
      `${path} is served as ${type}`,
      `status ${r.status}, type ${r.headers['content-type'] || 'none'}`);
  }
}

async function sitemap() {
  console.log(`\nEvery URL in the sitemap\n`);
  const sm = await fetchOnce(`${BASE}/sitemap.xml`);
  if (sm.status !== 200) {
    check(false, 'sitemap.xml is served', `got ${sm.status}`);
    return;
  }
  const urls = [...sm.body.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1]);
  console.log(`  ${urls.length} URLs listed\n`);
  if (!urls.length) { check(false, 'sitemap lists URLs', 'none found'); return; }

  // A 404 in a sitemap actively costs ranking, so check all of them, but
  // with a small concurrency so the origin is not hammered.
  const bad = [];
  let done = 0;
  const queue = [...urls];
  const worker = async () => {
    while (queue.length) {
      const u = queue.shift();
      // Sitemap entries are absolute and may name a different host than the
      // one under test; follow the path against the host we are testing.
      const path = new URL(u).pathname;
      const r = await fetchOnce(`${BASE}${path}`, 'HEAD');
      const status = r.status === 405 ? (await fetchOnce(`${BASE}${path}`)).status : r.status;
      if (status !== 200) bad.push(`${path} → ${status || r.error}`);
      if (++done % 25 === 0) console.log(`  checked ${done}/${urls.length}`);
    }
  };
  await Promise.all(Array.from({ length: 6 }, worker));

  check(bad.length === 0, `all ${urls.length} sitemap URLs return 200`,
    bad.length ? `${bad.length} broken: ${bad.slice(0, 8).join(', ')}` : '');
}

(async () => {
  if (SITEMAP_MODE) await sitemap();
  else await headers();

  if (failures.length) {
    console.error(`\n${failures.length} check(s) failed against production:`);
    failures.forEach(f => console.error(`  - ${f}`));
    process.exit(1);
  }
  console.log('\nAll production checks passed.');
})();
