/*
 * Drive tools on their OWN /tools/*.html pages, not through the modal.
 *
 *   node scripts/page-native-test.js [--url http://localhost:5599]
 *
 * Why this is separate from functional-suite.js: that suite loads
 * index.html and scopes every selector to #panel-body. Page-native pages
 * render into #panel-body-mount instead (see panelShell in frontend/app.js),
 * so the suite could pass completely while all 149 tool pages were broken.
 *
 * That mattered. Those pages are where search traffic lands — a visitor
 * arriving from Google never touches the homepage — and they shipped with no
 * test of any kind. This closes that.
 *
 * Deliberately a smoke test over representative tools rather than all 97:
 * the per-tool logic is already covered through the modal path, and what is
 * unique here is the mount, not the tools. What this proves is that the
 * mount renders, accepts input, produces real output, and that the modal
 * still works afterwards on the same page.
 */
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const ROOT = path.join(__dirname, '..');
const FIXTURES = path.join(ROOT, 'fixtures');
const args = process.argv.slice(2);
const BASE = args.includes('--url') ? args[args.indexOf('--url') + 1] : 'http://localhost:5599';

// Chosen to cover every distinct input shape: multi-file, single file with a
// mode tab, images, an Office document, video, and two tools that take no
// file at all.
const CASES = [
  { slug: 'merge-pdf',          files: ['text.pdf', 'text.pdf'], download: true },
  { slug: 'split-pdf',          files: ['text.pdf'],             download: true },
  { slug: 'images-to-pdf',      files: ['photo.jpg'],            download: true },
  { slug: 'make-image-smaller', files: ['photo.jpg'],            download: true },
  { slug: 'word-to-pdf',        files: ['document.docx'],        download: true },
  { slug: 'video-to-gif',       files: ['clip.webm'],            download: true },
  { slug: 'qr-code-generator',  files: null,                     download: false },
  { slug: 'hash-generator',     files: null,                     download: false },
];

const results = [];
const pass = (slug, detail) => { results.push({ slug, ok: true, detail }); console.log(`  PASS  ${slug.padEnd(22)} ${detail}`); };
const fail = (slug, detail) => { results.push({ slug, ok: false, detail }); console.log(`  FAIL  ${slug.padEnd(22)} ${detail}`); };

(async () => {
  if (!fs.existsSync(path.join(FIXTURES, 'manifest.json'))) {
    console.error('No fixtures. Run: python scripts/make-fixtures.py');
    process.exit(1);
  }

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ acceptDownloads: true });
  console.log(`\n  driving ${CASES.length} tools on their own pages at ${BASE}\n`);

  for (const c of CASES) {
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(e.message));
    try {
      await page.goto(`${BASE}/tools/${c.slug}.html`, { waitUntil: 'networkidle' });
      await page.waitForTimeout(400);

      // The mount must be filled by panelShell, not left as the empty div
      // the generator emits.
      const mounted = await page.evaluate(() => {
        const m = document.getElementById('tool-mount');
        return m ? m.innerHTML.trim().length : -1;
      });
      if (mounted <= 0) { fail(c.slug, mounted < 0 ? 'no #tool-mount on the page' : 'mount rendered empty'); await page.close(); continue; }

      const body = page.locator('#panel-body-mount');
      if (!(await body.count())) { fail(c.slug, 'rendered, but not into #panel-body-mount'); await page.close(); continue; }

      if (c.files) {
        const input = page.locator('#panel-body-mount input[type=file]');
        if (!(await input.count())) { fail(c.slug, 'no file input inside the mount'); await page.close(); continue; }
        await input.setInputFiles(c.files.map(f => path.join(FIXTURES, f)));
        await page.waitForTimeout(500);
      }

      if (c.download) {
        const btn = page.locator('#panel-body-mount button.primary-btn:not([disabled])').last();
        const [dl] = await Promise.all([
          page.waitForEvent('download', { timeout: 45000 }),
          btn.click(),
        ]);
        const p = await dl.path();
        const size = p ? fs.statSync(p).size : 0;
        if (size <= 0) { fail(c.slug, 'download produced an empty file'); await page.close(); continue; }
        pass(c.slug, `${dl.suggestedFilename()}, ${size} bytes`);
      } else {
        // No-file tools: assert the mount has real interactive controls.
        const controls = await page.locator('#panel-body-mount input, #panel-body-mount button, #panel-body-mount textarea').count();
        if (controls < 1) { fail(c.slug, 'mount has no interactive controls'); await page.close(); continue; }
        pass(c.slug, `${mounted} chars, ${controls} control(s)`);
      }

      if (errors.length) fail(c.slug + ' (js)', errors[0].slice(0, 90));
    } catch (e) {
      fail(c.slug, (e.message || String(e)).split('\n')[0].slice(0, 90));
    }
    await page.close();
  }

  // The mount is a one-shot latch (toolMountUsed in frontend/app.js): the
  // page's own tool takes it, and anything opened afterwards must fall back
  // to the modal. Exercised the way a user reaches it — finish a tool, then
  // click the "Also want to ..." suggestion offerChain renders. If the latch
  // broke, that button would silently do nothing on all 149 pages.
  //
  // Uses Make PDF Smaller rather than Merge PDF because only 2 of the 11
  // tools listed in SUGGESTED_NEXT actually call offerChain — see the note
  // in the commit; the other 9 entries are dead config and render no
  // suggestion at all.
  const page = await ctx.newPage();
  try {
    await page.goto(`${BASE}/tools/make-pdf-smaller.html`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(400);
    // scanned.pdf, not text.pdf: this tool needs an image-heavy document to
    // have anything to compress (same fixture tool-expectations.json uses).
    await page.locator('#panel-body-mount input[type=file]')
      .setInputFiles([path.join(FIXTURES, 'scanned.pdf')]);
    await page.waitForTimeout(400);
    await Promise.all([
      page.waitForEvent('download', { timeout: 45000 }),
      page.locator('#panel-body-mount button.primary-btn:not([disabled])').last().click(),
    ]);
    await page.waitForTimeout(600);

    const chain = page.locator('#panel-body-mount button', { hasText: /Also want to/i }).first();
    if (!(await chain.count())) {
      fail('modal-fallback', 'no chained-tool suggestion appeared after the result');
    } else {
      await chain.click();
      await page.waitForTimeout(600);
      const state = await page.evaluate(() => {
        const overlay = document.getElementById('overlay');
        const body = document.getElementById('panel-body');
        return {
          open: !!overlay && overlay.classList.contains('open'),
          filled: !!body && body.innerHTML.trim().length > 0,
        };
      });
      if (state.open && state.filled) pass('modal-fallback', 'chained tool opened in the overlay, mount not reused');
      else fail('modal-fallback', `overlay open=${state.open} panel filled=${state.filled}`);
    }
  } catch (e) {
    fail('modal-fallback', (e.message || String(e)).split('\n')[0].slice(0, 90));
  }
  await page.close();

  await browser.close();

  const failed = results.filter(r => !r.ok).length;
  console.log(`\n  ${results.length - failed}/${results.length} passed\n`);
  if (failed) process.exit(1);
})();
