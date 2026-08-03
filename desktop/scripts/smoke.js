/**
 * Headless smoke test for the packaged desktop app.
 *
 * Launches the real Electron main process with Playwright's _electron
 * driver and asserts the things that actually matter:
 *   * it opens from file:// (no host, so it cannot fail to "reach a site")
 *   * the tools are present and a real PDF merge works
 *   * no service worker and no manifest are involved
 *   * outbound network requests are blocked
 */
const { _electron: electron } = require('/opt/node22/lib/node_modules/playwright');
const path = require('path');

(async () => {
  const app = await electron.launch({
    args: [path.resolve(__dirname, '..')],
    executablePath: require(path.resolve(__dirname, '..', 'node_modules', 'electron')),
    env: { ...process.env, ELECTRON_DISABLE_SANDBOX: '1' },
  });

  const win = await app.firstWindow();
  await win.waitForLoadState('load');
  await win.waitForTimeout(2500);

  const out = {};
  out.url = await win.url();
  out.isFileProtocol = out.url.startsWith('file://');
  out.title = await win.title();

  out.page = await win.evaluate(() => ({
    h1: document.querySelector('h1') && document.querySelector('h1').textContent.trim(),
    toolCards: document.querySelectorAll('.tool-card').length,
    buildFlag: document.body.dataset.build || null,
    hasManifestLink: !!document.querySelector('link[rel="manifest"]'),
    hasInstallBtn: !!document.querySelector('.install-btn'),
    swControlled: !!(navigator.serviceWorker && navigator.serviceWorker.controller),
    // pdf-lib etc. now load on demand (see index.html's ensure*() helpers),
    // not eagerly, so this must be false until a tool that needs it runs.
    pdfLibLoadedEagerly: typeof PDFLib !== 'undefined',
  }));

  // Fixture PDFs for the merge test below, built via pdf-lib injected
  // directly into the page. This is a test-only helper independent of the
  // app's own lazy loader — it does not touch the network (Playwright's
  // addScriptTag with a local `path` reads the file and injects it via
  // CDP, not a browser request), so it works under the app's network block.
  await win.addScriptTag({ path: path.resolve(__dirname, '..', 'app', 'vendor', 'pdf-lib.min.js') });
  const mkPdf = async (n) => win.evaluate(async (pages) => {
    const d = await PDFLib.PDFDocument.create();
    for (let i = 0; i < pages; i++) d.addPage([200, 200]);
    return Array.from(await d.save());
  }, n);
  const pdf2 = await mkPdf(2);
  const pdf3 = await mkPdf(3);

  // open the tool page inside the app
  await win.click('.tool-card[data-tool="Merge PDF"]');
  await win.waitForTimeout(900);
  out.toolPage = await win.evaluate(() => ({
    h1: document.querySelector('#tool-page h1') && document.querySelector('#tool-page h1').textContent,
    url: location.href.split('/').pop(),
  }));

  // real merge, driven through the actual tool UI (not the pdf-lib API
  // directly) so this exercises the app's own ensurePdfLib() lazy loader.
  //
  // The result is captured by intercepting URL.createObjectURL rather than
  // Playwright's page.waitForEvent('download'): in this Electron + xvfb
  // combination, native downloads never fire a 'will-download' session
  // event at all (confirmed independently of the app's own code — even a
  // trivial blob-anchor click outside any tool never reaches it), so
  // waiting on that event just times out. Reading the blob the app itself
  // built is a more direct check anyway — it confirms the merge tool
  // produced the right bytes, without depending on Electron's native
  // download plumbing working under Xvfb.
  await win.evaluate(() => {
    window.__lastBlob = null;
    const orig = URL.createObjectURL.bind(URL);
    URL.createObjectURL = (blob) => { window.__lastBlob = blob; return orig(blob); };
  });
  const dt = await win.evaluateHandle((files) => {
    const dt = new DataTransfer();
    for (const [bytes, name] of files) dt.items.add(new File([new Uint8Array(bytes)], name, { type: 'application/pdf' }));
    return dt;
  }, [[pdf2, 'a.pdf'], [pdf3, 'b.pdf']]);
  await win.evaluate((dt) => {
    const input = document.querySelector('#panel-body input[type=file]');
    input.files = dt.files;
    input.dispatchEvent(new Event('change', { bubbles: true }));
  }, dt);
  await win.waitForTimeout(400);
  await win.click('#panel-body button.primary-btn');
  await win.waitForTimeout(1500);
  out.merge = await win.evaluate(async () => {
    if (!window.__lastBlob) return null;
    const bytes = new Uint8Array(await window.__lastBlob.arrayBuffer());
    const pageCount = (await PDFLib.PDFDocument.load(bytes)).getPageCount();
    return { type: window.__lastBlob.type, bytes: bytes.length, pageCount };
  });
  out.runlog = await win.evaluate(() => {
    const el = document.querySelector('.runlog');
    return el ? el.textContent : null;
  });

  // the network really is blocked for the renderer
  out.networkBlocked = await win.evaluate(async () => {
    try {
      await fetch('https://example.com/', { mode: 'no-cors' });
      return false;            // got through — bad
    } catch (e) {
      return true;             // blocked — expected
    }
  });

  console.log(JSON.stringify(out, null, 2));
  await app.close();

  const failures = [];
  if (!out.isFileProtocol) failures.push('not loaded from file://');
  if (!out.page.toolCards) failures.push('no tool cards rendered');
  if (out.page.hasManifestLink) failures.push('manifest link present (should be stripped)');
  if (out.page.swControlled) failures.push('service worker controlling the page (should be stripped)');
  if (out.page.pdfLibLoadedEagerly) failures.push('pdf-lib loaded eagerly on page load (should be lazy)');
  if (!out.merge || out.merge.pageCount !== 5) failures.push('merge did not produce a 5-page PDF: ' + JSON.stringify(out.merge));
  if (!out.networkBlocked) failures.push('outbound network was not blocked');
  if (failures.length) {
    console.error('SMOKE FAILED:', failures.join('; '));
    process.exit(1);
  }
  console.log('SMOKE OK');
})().catch((e) => { console.error('SMOKE FAILED:', e.message); process.exit(1); });
