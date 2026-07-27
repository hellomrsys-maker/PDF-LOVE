/*
 * Audits every page for the things search engines actually check, and for
 * the duplication that gets a site penalised.
 *
 *   node scripts/seo-audit.js
 *
 * Fails on:
 *   - a missing or duplicated <title> or meta description
 *   - a missing or wrong <link rel="canonical">
 *   - a title or description outside the length search engines will render
 *   - more than one <h1>
 *   - malformed JSON-LD
 *   - a sitemap that lists a page that does not exist, or omits one that does
 *
 * The duplicate checks are the point. Generated pages are only safe when
 * each one is genuinely distinct; two pages sharing a description is the
 * signal that a template has been stamped out rather than a page written.
 */
const fs = require('fs');
const path = require('path');

const FRONTEND = path.join(__dirname, '..', 'frontend');
const SITE = 'https://dockbench.app';

// Google truncates around these; outside the range is a rendering problem,
// not a ranking one, but it costs click-through either way.
const TITLE_MIN = 20, TITLE_MAX = 70;
const DESC_MIN = 70, DESC_MAX = 165;

function walk(dir, out = []) {
  for (const e of fs.readdirSync(dir, { withFileTypes: true })) {
    const p = path.join(dir, e.name);
    if (e.isDirectory()) {
      if (['vendor', 'icons', 'dist', '.well-known'].includes(e.name)) continue;
      walk(p, out);
    } else if (e.name.endsWith('.html')) {
      out.push(p);
    }
  }
  return out;
}

const files = walk(FRONTEND);
const titles = new Map(), descs = new Map(), canons = new Map();
const problems = [];

for (const file of files) {
  const rel = path.relative(FRONTEND, file);
  const html = fs.readFileSync(file, 'utf8');
  const add = m => problems.push(`${rel}: ${m}`);

  const title = (html.match(/<title>([\s\S]*?)<\/title>/) || [])[1]?.trim();
  const desc = (html.match(/<meta\s+name="description"\s+content="([^"]*)"/i) || [])[1];
  const canon = (html.match(/<link\s+rel="canonical"\s+href="([^"]*)"/i) || [])[1];

  if (!title) add('no <title>');
  else {
    if (title.length < TITLE_MIN) add(`title too short (${title.length})`);
    if (title.length > TITLE_MAX) add(`title too long (${title.length}): ${title.slice(0, 50)}...`);
    if (titles.has(title)) add(`duplicate title, also in ${titles.get(title)}`);
    else titles.set(title, rel);
  }

  if (!desc) add('no meta description');
  else {
    if (desc.length < DESC_MIN) add(`description too short (${desc.length})`);
    if (desc.length > DESC_MAX) add(`description too long (${desc.length})`);
    if (descs.has(desc)) add(`duplicate description, also in ${descs.get(desc)}`);
    else descs.set(desc, rel);
  }

  if (!canon) add('no rel=canonical');
  else {
    if (!canon.startsWith(SITE)) add(`canonical is not absolute: ${canon}`);
    if (canons.has(canon)) add(`duplicate canonical, also in ${canons.get(canon)}`);
    else canons.set(canon, rel);
  }

  // Count real <h1> elements only. The app embeds HTML inside template
  // literals and placeholder attributes (the HTML-to-PDF tool shows
  // `<h1>Title</h1>` as example input), which a naive match counts as
  // markup on this page.
  const markup = html
    .replace(/<script[\s\S]*?<\/script>/gi, '')
    .replace(/`[^`]*`/g, '')
    .replace(/"(?:[^"\\]|\\.)*"/g, '""');
  const h1s = markup.match(/<h1[\s>]/g) || [];
  if (h1s.length === 0) add('no <h1>');
  if (h1s.length > 1) add(`${h1s.length} <h1> elements (should be 1)`);

  for (const m of html.matchAll(/<script type="application\/ld\+json">([\s\S]*?)<\/script>/g)) {
    try { JSON.parse(m[1]); }
    catch (e) { add(`invalid JSON-LD: ${e.message.slice(0, 60)}`); }
  }

  if (!/<meta\s+name="viewport"/i.test(html)) add('no viewport meta');
}

// --- sitemap coverage ---
const sitemapPath = path.join(FRONTEND, 'sitemap.xml');
if (!fs.existsSync(sitemapPath)) {
  problems.push('sitemap.xml does not exist');
} else {
  const sm = fs.readFileSync(sitemapPath, 'utf8');
  const locs = [...sm.matchAll(/<loc>([^<]+)<\/loc>/g)].map(m => m[1]);

  for (const loc of locs) {
    let p = loc.replace(SITE, '').replace(/^\//, '');
    if (p === '' || p.endsWith('/')) p += 'index.html';
    if (!fs.existsSync(path.join(FRONTEND, p))) {
      problems.push(`sitemap lists a file that does not exist: ${loc}`);
    }
  }
  const listed = new Set(locs.map(l => l.replace(SITE, '').replace(/^\//, '') || 'index.html'));
  for (const file of files) {
    const rel = path.relative(FRONTEND, file).split(path.sep).join('/');
    // Directory index pages appear in the sitemap as a trailing slash.
    const alt = rel.replace(/index\.html$/, '');
    if (!listed.has(rel) && !listed.has(alt) && !listed.has(alt + 'index.html')) {
      problems.push(`not in sitemap: ${rel}`);
    }
  }
}

if (!fs.existsSync(path.join(FRONTEND, 'robots.txt'))) {
  problems.push('robots.txt does not exist');
}

console.log(`\n  audited ${files.length} pages`);
console.log(`  unique titles:       ${titles.size}`);
console.log(`  unique descriptions: ${descs.size}`);
console.log(`  unique canonicals:   ${canons.size}`);

if (problems.length) {
  console.error(`\n  ${problems.length} problem(s):`);
  problems.slice(0, 40).forEach(p => console.error('   - ' + p));
  if (problems.length > 40) console.error(`   ... and ${problems.length - 40} more`);
  process.exit(1);
}
console.log('\n  No SEO problems found.');
