/*
 * Drive every tool in the app with real files and check the real output.
 *
 *   node scripts/functional-suite.js [--only "Merge PDF"] [--url http://...]
 *
 * Before this existed, CI checked that a tool's panel opened without
 * throwing. That catches a crash and nothing else: a tool that produces an
 * empty file, the wrong page count, or a "redacted" PDF that still contains
 * the SSN all passed.
 *
 * Each tool is opened, given the fixture named in tool-expectations.json,
 * driven to its output, and the output handed to validate-output.py, which
 * opens it and looks. Results go to test-results/functional.json for the
 * report.
 */
const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const ROOT = path.join(__dirname, '..');
const FIXTURES = path.join(ROOT, 'fixtures');
const RESULTS = path.join(ROOT, 'test-results');
const DOWNLOADS = path.join(RESULTS, 'downloads');
const EXPECT = JSON.parse(fs.readFileSync(path.join(__dirname, 'tool-expectations.json'), 'utf8'));

const args = process.argv.slice(2);
const only = args.includes('--only') ? args[args.indexOf('--only') + 1] : null;
const BASE = args.includes('--url') ? args[args.indexOf('--url') + 1] : 'http://localhost:5599';
const DEFAULT_TIMEOUT = 45000;

/** Fixture chosen by what the tool's file input accepts. */
function defaultFixture(accept) {
  if (/pdf/.test(accept)) return 'text.pdf';
  if (/image/.test(accept)) return 'photo.jpg';
  if (/video|audio/.test(accept)) return 'clip.webm';
  if (/docx/.test(accept)) return 'document.docx';
  if (/pptx/.test(accept)) return 'presentation.pptx';
  if (/xlsx|csv|ods/.test(accept)) return 'spreadsheet.xlsx';
  return 'text.pdf';
}

// The validator needs pikepdf/Pillow. Use the interpreter the caller
// nominates, so a venv is honoured rather than silently falling back to a
// bare system python that reports every check as a missing module.
const PYTHON = process.env.PYTHON || 'python3';

function validate(checker, file, expected) {
  const r = spawnSync(PYTHON, [
    path.join(__dirname, 'validate-output.py'), checker, file,
    ...(expected !== undefined && expected !== null ? [String(expected)] : []),
  ], { encoding: 'utf8' });
  try {
    return JSON.parse((r.stdout || '').trim().split('\n').pop());
  } catch (e) {
    return { ok: false, detail: `validator failed: ${(r.stderr || r.stdout || '').slice(0, 160)}` };
  }
}

(async () => {
  fs.mkdirSync(DOWNLOADS, { recursive: true });
  if (!fs.existsSync(path.join(FIXTURES, 'manifest.json'))) {
    console.error('No fixtures. Run: python scripts/make-fixtures.py');
    process.exit(1);
  }

  const browser = await chromium.launch();
  const ctx = await browser.newContext({ acceptDownloads: true });
  const page = await ctx.newPage();

  const pageErrors = [];
  page.on('pageerror', e => pageErrors.push(String(e.message)));

  await page.goto(`${BASE}/index.html`, { waitUntil: 'networkidle' });
  await page.waitForTimeout(1200);

  // The rendered cards are the source of truth for what exists, so a new
  // tool cannot be silently untested. (toolIndex itself lives inside the
  // DOMContentLoaded closure and is not reachable from here.)
  const tools = await page.evaluate(() => {
    const seen = new Map();
    document.querySelectorAll('.tool-card[data-tool]').forEach(card => {
      const name = card.getAttribute('data-tool');
      if (seen.has(name)) return;
      // Cards are duplicated into the favourites/recent/popular rows; the
      // one inside a category grid carries the real section.
      const grid = card.closest('[id$="-tools"]');
      seen.set(name, { name, section: grid ? grid.id : 'unknown' });
    });
    return [...seen.values()];
  });
  if (!tools.length) {
    console.error('No tool cards rendered — the app did not initialise.');
    process.exit(1);
  }

  // Some tools have more than one behaviour worth testing — Split PDF's two
  // modes, Repair PDF on damage it can and cannot fix. Those are declared as
  // extra expectation entries carrying a "tool" field naming the card to
  // open, so one card can be exercised several ways.
  const byName = new Map(tools.map(t => [t.name, t]));
  const aliases = Object.entries(EXPECT)
    .filter(([k, v]) => !k.startsWith('_') && v && v.tool)
    .map(([k, v]) => {
      const base = byName.get(v.tool);
      if (!base) return null;
      return { name: k, card: v.tool, section: base.section };
    })
    .filter(Boolean);

  const results = [];
  const all = [...tools, ...aliases];
  const targets = only ? all.filter(t => t.name === only) : all;
  console.log(`\n  running ${targets.length} tools against ${BASE}\n`);

  for (const tool of targets) {
    const spec = EXPECT[tool.name] || {};
    const started = Date.now();
    const rec = { name: tool.name, section: tool.section, mode: spec.mode || 'download' };

    if (spec.mode === 'skip') {
      rec.status = 'skipped';
      rec.detail = spec.reason || 'no reason given';
      results.push(rec);
      console.log(`  SKIP  ${tool.name.padEnd(38)} ${rec.detail.slice(0, 60)}`);
      continue;
    }

    pageErrors.length = 0;
    try {
      await page.evaluate(() => window.closePanel && window.closePanel());
      await page.waitForTimeout(120);
      const cardName = tool.card || tool.name;
      await page.locator(`.tool-card[data-tool="${cardName.replace(/"/g, '\\"')}"]`)
        .first().click({ timeout: 8000 });
      await page.waitForTimeout(350);

      // Some tools need a tab or mode selected before their inputs appear
      // (Split PDF defaults to "extract a range"; the one-file-per-page mode
      // is behind a tab). Applied before anything is supplied.
      for (const sel of (spec.click_first || [])) {
        const el = page.locator(sel).first();
        if (await el.count()) { await el.click(); await page.waitForTimeout(250); }
      }

      // --- supply input -------------------------------------------------
      const fileInputs = page.locator('#panel-body input[type=file]');
      const inputCount = await fileInputs.count();

      if (inputCount > 0 && spec.mode !== 'text') {
        const accept = await fileInputs.first().getAttribute('accept') || '';
        let names = spec.input || defaultFixture(accept);
        if (!Array.isArray(names)) names = [names];
        const paths = names
          .map(n => path.join(FIXTURES, n))
          .filter(p => fs.existsSync(p));
        if (!paths.length) {
          rec.status = 'blocked';
          rec.detail = `fixture missing: ${names.join(', ')}`;
          results.push(rec);
          console.log(`  BLOCK ${tool.name.padEnd(38)} ${rec.detail}`);
          continue;
        }
        // Tools that compare or splice two documents render two separate
        // single-file inputs. Feeding both fixtures to the first one throws
        // "Non-multiple file input can only accept single file" — which
        // looked like a tool failure but was the driver's mistake.
        const multiple = await fileInputs.first().evaluate(el => el.multiple);
        if (!multiple && paths.length > 1 && inputCount > 1) {
          for (let i = 0; i < Math.min(paths.length, inputCount); i++) {
            await fileInputs.nth(i).setInputFiles(paths[i], { timeout: 20000 });
            await page.waitForTimeout(400);
          }
        } else if (!multiple) {
          await fileInputs.first().setInputFiles(paths[0], { timeout: 20000 });
        } else {
          await fileInputs.first().setInputFiles(paths, { timeout: 20000 });
        }
        await page.waitForTimeout(700);
      }

      // Named fields: passwords, target dimensions, form rows — anything a
      // tool legitimately refuses to run without.
      for (const [sel, value] of (spec.fill || [])) {
        const el = page.locator(sel).first();
        if (await el.count()) { await el.fill(String(value)); await el.dispatchEvent('input'); }
      }
      if (spec.fill) await page.waitForTimeout(400);

      // Tools that need something drawn or pointed at: a signature stroke,
      // a stamp placed on a page, a rectangle dragged over text to redact.
      // Without this they correctly refuse to run and look like failures.
      for (const g of (spec.gestures || [])) {
        const el = page.locator(g.target).first();
        if (!(await el.count())) continue;
        await el.scrollIntoViewIfNeeded();
        const box = await el.boundingBox();
        if (!box) continue;
        const at = (fx, fy) => ({ x: box.x + box.width * fx, y: box.y + box.height * fy });
        if (g.type === 'draw') {
          const p0 = at(0.2, 0.6);
          await page.mouse.move(p0.x, p0.y);
          await page.mouse.down();
          for (let s = 1; s <= 12; s++) {
            const p = at(0.2 + 0.5 * (s / 12), 0.6 - 0.25 * Math.sin(s / 2));
            await page.mouse.move(p.x, p.y);
          }
          await page.mouse.up();
        } else if (g.type === 'drag') {
          const a = at(g.from?.[0] ?? 0.15, g.from?.[1] ?? 0.15);
          const b = at(g.to?.[0] ?? 0.75, g.to?.[1] ?? 0.4);
          await page.mouse.move(a.x, a.y);
          await page.mouse.down();
          await page.mouse.move(b.x, b.y, { steps: 10 });
          await page.mouse.up();
        } else if (g.type === 'tap') {
          const p = at(g.at?.[0] ?? 0.5, g.at?.[1] ?? 0.5);
          await page.mouse.click(p.x, p.y);
        }
        await page.waitForTimeout(400);
      }

      // Text-driven tools: fill the first textarea/text input.
      if (spec.fill_text) {
        const field = page.locator(
          '#panel-body textarea, #panel-body input[type=text]').first();
        if (await field.count()) {
          await field.fill(spec.fill_text);
          await field.dispatchEvent('input');
          await page.waitForTimeout(400);
        }
      }

      // --- trigger --------------------------------------------------------
      const timeout = spec.timeout || DEFAULT_TIMEOUT;
      // Default to the last enabled primary button, which is the "do it"
      // button in almost every panel. Tools offering both directions
      // (Encode / Decode) name the one they mean, otherwise the driver
      // clicks Decode and reports that encoding is broken.
      const action = spec.action
        ? page.locator(spec.action).first()
        : page.locator('#panel-body button.primary-btn:not([disabled])').last();
      const hasAction = await action.count() > 0;

      if (spec.mode === 'live' || !hasAction) {
        // Output appears in the panel rather than as a download.
        if (hasAction) { await action.click(); await page.waitForTimeout(900); }
        else await page.waitForTimeout(600);

        const panel = await page.evaluate(() => {
          const b = document.getElementById('panel-body');
          if (!b) return { text: '', html: 0, canvases: 0 };
          // Many of these tools write their result into an <input> or
          // <textarea>. innerText does not include field values, so a
          // correct result would look like an empty panel without this.
          const values = [...b.querySelectorAll('input, textarea')]
            .map(el => el.value || '').filter(Boolean).join('\n');
          return {
            text: b.innerText + '\n' + values,
            html: b.innerHTML.length,
            canvases: b.querySelectorAll('canvas, img, svg').length,
          };
        });
        rec.mode = 'live';

        if (spec.assert === 'panel_contains') {
          const want = String(spec.expect);
          rec.status = panel.text.includes(want) ? 'pass' : 'fail';
          rec.detail = rec.status === 'pass'
            ? `panel contains "${want.slice(0, 24)}"`
            : `panel does not contain "${want.slice(0, 24)}" (got ${panel.text.slice(0, 80).replace(/\n/g, ' ')})`;
        } else if (spec.assert === 'canvas_or_img') {
          rec.status = panel.canvases > 0 ? 'pass' : 'fail';
          rec.detail = `${panel.canvases} rendered element(s)`;
        } else {
          rec.status = panel.html > 80 ? 'pass' : 'fail';
          rec.detail = `panel has ${panel.html} chars of content`;
        }
      } else {
        const dl = page.waitForEvent('download', { timeout }).catch(() => null);
        await action.click();
        const download = await dl;
        if (!download) {
          rec.status = 'fail';
          const log = await page.evaluate(() =>
            document.querySelector('#panel-body .runlog')?.innerText || '');
          rec.detail = log ? `no download; panel said: ${log.slice(0, 110)}`
                           : 'no download produced within the timeout';
        } else {
          const out = path.join(DOWNLOADS,
            `${tool.name.replace(/[^\w.-]+/g, '_')}__${download.suggestedFilename()}`);
          await download.saveAs(out);
          rec.output = path.relative(ROOT, out);
          rec.bytes = fs.statSync(out).size;
          const v = validate(spec.assert || 'any_output', out, spec.expect);
          rec.status = v.ok ? 'pass' : 'fail';
          rec.detail = v.detail;
        }
      }

      if (pageErrors.length) {
        rec.status = 'fail';
        rec.detail = `${rec.detail || ''} | page error: ${pageErrors[0].slice(0, 110)}`.trim();
      }
    } catch (e) {
      rec.status = 'error';
      rec.detail = String(e.message).split('\n')[0].slice(0, 150);
    }

    rec.ms = Date.now() - started;
    results.push(rec);
    const mark = { pass: 'PASS ', fail: 'FAIL ', error: 'ERROR', blocked: 'BLOCK' }[rec.status] || '?    ';
    console.log(`  ${mark} ${rec.name.padEnd(38)} ${(rec.detail || '').slice(0, 66)}`);
  }

  await browser.close();

  const summary = {
    generated: new Date().toISOString(),
    base: BASE,
    total: results.length,
    pass: results.filter(r => r.status === 'pass').length,
    fail: results.filter(r => r.status === 'fail').length,
    error: results.filter(r => r.status === 'error').length,
    blocked: results.filter(r => r.status === 'blocked').length,
    skipped: results.filter(r => r.status === 'skipped').length,
    results,
  };
  fs.mkdirSync(RESULTS, { recursive: true });
  fs.writeFileSync(path.join(RESULTS, 'functional.json'), JSON.stringify(summary, null, 2));

  const tested = summary.pass + summary.fail + summary.error + summary.blocked;
  console.log(`\n  ${summary.pass}/${tested} passed` +
              `  (${summary.fail} failed, ${summary.error} errored, ` +
              `${summary.blocked} blocked, ${summary.skipped} skipped)`);
  console.log(`  full results: test-results/functional.json\n`);

  // Exit non-zero only when something genuinely broke. Skips are declared
  // in the expectations file and reviewed there, not here.
  process.exit(summary.fail + summary.error + summary.blocked > 0 ? 1 : 0);
})();
