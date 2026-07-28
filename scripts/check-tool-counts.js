/*
 * Keep the advertised tool counts honest.
 *
 * The README, the download page and every company page state how many tools
 * run on-device. That number was wrong — the docs said 97 of 104 while the
 * app actually ships 94, because three server-assisted converters sit in the
 * always-visible Convert row rather than the opt-in server section. Nothing
 * checked it, so the claim drifted from the code and stayed wrong.
 *
 * This asks the running app how many tools there are and where each one
 * runs, then fails if any published figure disagrees.
 *
 *   node scripts/check-tool-counts.js [--url http://localhost:5599]
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const ROOT = path.join(__dirname, '..');
const args = process.argv.slice(2);
const BASE = args.includes('--url') ? args[args.indexOf('--url') + 1] : 'http://localhost:5599';

// Files that state the split, and the pattern that carries the number.
//
// This list was incomplete, and the omission cost something real: index.html,
// about.html and terms.html all claimed "97 of 104" on-device for weeks —
// including inside the FAQPage JSON-LD that feeds Google's rich results, and
// inside the privacy policy, the one document whose whole job is to be exact
// about which tools touch a server. Anything that states the split belongs
// here.
const CLAIMS = [
  'README.md',
  'desktop/README.md',
  'deploy/API.md',
  'deploy/CLOUDFLARE.md',
  'frontend/index.html',
  'frontend/download.html',
  'frontend/company/about.html',
  'frontend/company/pricing.html',
  'frontend/company/security.html',
  'frontend/company/privacy.html',
  'frontend/company/terms.html',
  'frontend/company/legal.html',
  'frontend/company/cookies.html',
  'frontend/company/grievance.html',
  // The generators, so a wrong number is caught at the source rather than
  // only in the output it produces.
  'scripts/build-legal.py',
];

// "Ninety-seven of them never send your file anywhere" slipped through for
// the same reason: the scan only understood digits. Prose counts are still
// counts.
const WORD_NUM = (() => {
  const ones = ['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven',
                'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen',
                'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen',
                'nineteen'];
  const tens = ['', '', 'twenty', 'thirty', 'forty', 'fifty', 'sixty',
                'seventy', 'eighty', 'ninety'];
  const map = new Map();
  ones.forEach((w, i) => map.set(w, i));
  tens.forEach((w, t) => {
    if (!w) return;
    map.set(w, t * 10);
    for (let u = 1; u <= 9; u++) map.set(`${w}-${ones[u]}`, t * 10 + u);
  });
  return map;
})();

(async () => {
  const browser = await chromium.launch();
  const page = await (await browser.newContext()).newPage();
  await page.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(2000);

  const counts = await page.evaluate(() => {
    const seen = new Map();
    document.querySelectorAll('.tool-card[data-tool]').forEach(c => {
      const n = c.getAttribute('data-tool');
      if (!seen.has(n)) seen.set(n, c.dataset.where);
    });
    const all = [...seen.values()];
    return {
      total: all.length,
      device: all.filter(w => w === 'device').length,
      server: all.filter(w => w === 'server').length,
    };
  });
  await browser.close();

  if (!counts.total) {
    console.error('No tool cards rendered — the app did not initialise.');
    process.exit(1);
  }
  console.log(`  app reports ${counts.device} on-device + ${counts.server} ` +
              `server-assisted = ${counts.total} tools\n`);

  if (counts.device + counts.server !== counts.total) {
    console.error(`Every card must declare where it runs; ` +
                  `${counts.total - counts.device - counts.server} did not.`);
    process.exit(1);
  }

  // Any "N of 104"-shaped claim must use the real on-device number, and any
  // total must be the real total.
  const problems = [];
  for (const rel of CLAIMS) {
    const file = path.join(ROOT, rel);
    if (!fs.existsSync(file)) continue;
    const text = fs.readFileSync(file, 'utf8');
    text.split('\n').forEach((line, i) => {
      // "97 of the 104 tools" must match as readily as "97 of 104" — the
      // optional "the" is why the wrong figure in index.html's JSON-LD
      // survived this check for as long as it did.
      const OF_TOTAL = /(\d+)\s+of\s+(?:the\s+)?(\d+)/;
      const ofTotal = line.match(new RegExp(OF_TOTAL, 'g')) || [];
      for (const m of ofTotal) {
        const [, n, t] = m.match(OF_TOTAL);
        if (Number(t) !== counts.total) {
          problems.push(`${rel}:${i + 1} says "${m}" but the app has ${counts.total} tools`);
        } else if (![counts.device, counts.server, counts.total].includes(Number(n))) {
          // total-of-total is legitimate: the desktop build bundles the
          // local engine, so all 104 run on the user's machine there.
          problems.push(`${rel}:${i + 1} says "${m}" but the split is ` +
                        `${counts.device} on-device / ${counts.server} server-assisted`);
        }
      }
      const onDevice = line.match(/(\d+)\s+on-device tools/);
      if (onDevice && Number(onDevice[1]) !== counts.device) {
        problems.push(`${rel}:${i + 1} says "${onDevice[0]}" but the app has ${counts.device}`);
      }

      // Spelled-out counts, in the shapes that actually occur:
      //   "Ninety-seven of them"      "Seven of the 104 tools"
      //   "those seven"               "including the seven that ..."
      //
      // "one" is excluded: "every one of the 104 tools" is idiomatic English,
      // not a claim about how many. Every other number word in these
      // positions is a count.
      const words = [...WORD_NUM.keys()].filter(w => w !== 'one').join('|');
      const spelled = new RegExp(
        `\\b(${words})\\b\\s+(?:of\\s+them|of\\s+the\\s+\\d+\\s+tools)|` +
        `\\bthose\\s+(${words})\\b|` +
        `\\bthe\\s+(${words})\\s+that\\b`, 'gi');
      for (const m of line.matchAll(spelled)) {
        const word = (m[1] || m[2] || m[3]).toLowerCase();
        const n = WORD_NUM.get(word);
        if (n === undefined) continue;
        if (![counts.device, counts.server, counts.total].includes(n)) {
          problems.push(`${rel}:${i + 1} says "${m[0].trim()}" but the split is ` +
                        `${counts.device} on-device / ${counts.server} server-assisted`);
        }
      }
    });
  }

  if (problems.length) {
    console.error('Published tool counts disagree with the app:\n');
    problems.forEach(p => console.error('  ' + p));
    console.error(`\nThe app is the source of truth: ${counts.device} on-device, ` +
                  `${counts.server} server-assisted, ${counts.total} total.`);
    process.exit(1);
  }
  console.log('  PASS: every published count matches the app.');
})();
