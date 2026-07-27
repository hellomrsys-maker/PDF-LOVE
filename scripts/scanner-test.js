/*
 * Verifies frontend/vendor/docscan.js against synthetic skewed documents,
 * in a real browser.
 *
 *   node scripts/scanner-test.js
 *
 * Asserts two things:
 *   1. The detected corners land near the true corners of a document drawn
 *      at a known perspective.
 *   2. Detection is fast enough for a live camera preview. This is the
 *      claim that justified writing it in JS rather than compiling to WASM,
 *      so it is measured rather than assumed.
 */
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const DOCSCAN = path.join(__dirname, '..', 'frontend', 'vendor', 'docscan.js');

// Live preview targets ~10 fps for detection, so anything under 100 ms is
// usable. Fail well before that so a regression is caught early.
const BUDGET_MS = 60;
// Corners must land within this fraction of the frame's larger dimension.
const TOLERANCE_FRAC = 0.05;

(async () => {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('about:blank');
  await page.addScriptTag({ path: DOCSCAN });

  const results = await page.evaluate(async ({ budget, tolFrac }) => {
    const W = 960, H = 720;

    /** Draw a page at a known quad, on a contrasting background. */
    function render(quad, opts) {
      opts = opts || {};
      const c = document.createElement('canvas');
      c.width = W; c.height = H;
      const g = c.getContext('2d');

      // Desk: darker than the page, with some texture so it isn't a
      // degenerate flat-field case.
      g.fillStyle = '#3b3a36';
      g.fillRect(0, 0, W, H);
      if (opts.noise) {
        for (let i = 0; i < 4000; i++) {
          g.fillStyle = `rgba(255,255,255,${Math.random() * 0.06})`;
          g.fillRect(Math.random() * W, Math.random() * H, 2, 2);
        }
      }

      // The page.
      g.save();
      g.beginPath();
      g.moveTo(quad[0].x, quad[0].y);
      for (let i = 1; i < 4; i++) g.lineTo(quad[i].x, quad[i].y);
      g.closePath();
      g.fillStyle = opts.dim ? '#b9b6ad' : '#f3f1ea';
      g.fill();
      g.clip();

      // Text lines, so the page isn't a flat rectangle either.
      g.fillStyle = 'rgba(40,40,40,0.75)';
      const minX = Math.min(...quad.map(p => p.x)), maxX = Math.max(...quad.map(p => p.x));
      const minY = Math.min(...quad.map(p => p.y)), maxY = Math.max(...quad.map(p => p.y));
      for (let y = minY + 30; y < maxY - 20; y += 22) {
        const w = (maxX - minX) * (0.55 + Math.random() * 0.3);
        g.fillRect(minX + 25, y, w, 7);
      }
      g.restore();
      return c;
    }

    function maxCornerError(got, want) {
      // Match each expected corner to the nearest detected one; ordering is
      // already canonical but this makes the check independent of it.
      let worst = 0;
      for (const w of want) {
        let best = Infinity;
        for (const g of got) {
          best = Math.min(best, Math.hypot(g.x - w.x, g.y - w.y));
        }
        worst = Math.max(worst, best);
      }
      return worst;
    }

    const cases = [
      { name: 'straight',        quad: [{x:180,y:110},{x:780,y:110},{x:780,y:610},{x:180,y:610}] },
      { name: 'skewed',          quad: [{x:150,y:150},{x:800,y:95},{x:830,y:600},{x:190,y:660}] },
      { name: 'rotated',         quad: [{x:300,y:80},{x:840,y:250},{x:660,y:640},{x:120,y:470}] },
      { name: 'small in frame',  quad: [{x:340,y:250},{x:640,y:240},{x:650,y:490},{x:330,y:480}] },
      { name: 'dim + noisy',     quad: [{x:170,y:130},{x:790,y:120},{x:800,y:590},{x:180,y:600}],
                                 opts: { dim: true, noise: true } },
    ];

    const out = [];
    for (const c of cases) {
      const canvas = render(c.quad, c.opts);
      const ctx = canvas.getContext('2d', { willReadFrequently: true });
      const img = ctx.getImageData(0, 0, W, H);

      // Warm up once, then take the median of several runs.
      DocScan.detect(img);
      const times = [];
      let res = null;
      for (let i = 0; i < 7; i++) {
        const t = performance.now();
        res = DocScan.detect(img);
        times.push(performance.now() - t);
      }
      times.sort((a, b) => a - b);
      const median = times[3];

      if (!res) { out.push({ name: c.name, detected: false, ms: median }); continue; }

      const err = maxCornerError(res.corners, c.quad);
      out.push({
        name: c.name, detected: true, ms: median,
        error: err, tolerance: Math.max(W, H) * tolFrac,
        score: res.score, corners: res.corners.map(p => [Math.round(p.x), Math.round(p.y)]),
      });
    }

    // Negative case: an empty desk must not report a document.
    const blank = document.createElement('canvas');
    blank.width = W; blank.height = H;
    const bg = blank.getContext('2d');
    bg.fillStyle = '#3b3a36'; bg.fillRect(0, 0, W, H);
    const blankRes = DocScan.detect(bg.getImageData(0, 0, W, H));
    out.push({ name: 'blank frame (must NOT detect)', detected: !!blankRes, negative: true });

    // Warp check: a detected quad must flatten to the requested size.
    const c2 = render(cases[1].quad);
    const d2 = DocScan.detect(c2.getContext('2d', { willReadFrequently: true })
      .getImageData(0, 0, W, H));
    const warped = DocScan.warp(c2, d2.corners, 600, 800);
    out.push({ name: 'warp', warpedW: warped.width, warpedH: warped.height });

    return out;
  }, { budget: BUDGET_MS, tolFrac: TOLERANCE_FRAC });

  await browser.close();

  let failed = 0;
  console.log('\n  case                       detected   err(px)  tol   ms');
  console.log('  ' + '-'.repeat(60));
  for (const r of results) {
    if (r.negative) {
      const ok = r.detected === false;
      if (!ok) failed++;
      console.log(`  ${r.name.padEnd(28)} ${ok ? 'correctly ignored ✓' : 'FALSE POSITIVE ✗'}`);
      continue;
    }
    if (r.warpedW) {
      const ok = r.warpedW === 600 && r.warpedH === 800;
      if (!ok) failed++;
      console.log(`  ${'warp to 600x800'.padEnd(28)} ${r.warpedW}x${r.warpedH} ${ok ? '✓' : '✗'}`);
      continue;
    }
    const okDetect = r.detected;
    const okErr = okDetect && r.error <= r.tolerance;
    const okSpeed = r.ms <= BUDGET_MS;
    if (!okDetect || !okErr || !okSpeed) failed++;
    console.log(
      `  ${r.name.padEnd(26)} ${okDetect ? ' yes' : '  NO'}    ` +
      `${okDetect ? r.error.toFixed(1).padStart(6) : '     -'}  ` +
      `${okDetect ? r.tolerance.toFixed(0).padStart(4) : '   -'}  ` +
      `${r.ms.toFixed(1).padStart(5)}` +
      `${okErr ? '' : '   <- ERROR TOO LARGE'}${okSpeed ? '' : '   <- TOO SLOW'}`
    );
  }

  const times = results.filter(r => r.ms).map(r => r.ms);
  if (times.length) {
    console.log(`\n  median detection: ${(times.reduce((a, b) => a + b, 0) / times.length).toFixed(1)} ms ` +
                `(budget ${BUDGET_MS} ms for a ~10 fps live preview)`);
  }

  if (failed) {
    console.error(`\n  ${failed} check(s) failed.`);
    process.exit(1);
  }
  console.log('\n  All scanner checks passed.');
})();
