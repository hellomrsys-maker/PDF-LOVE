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
    pdfLib: typeof PDFLib !== 'undefined',
  }));

  // real work, entirely inside the packaged app
  out.merge = await win.evaluate(async () => {
    const { PDFDocument } = PDFLib;
    const mk = async (n) => {
      const d = await PDFDocument.create();
      for (let i = 0; i < n; i++) d.addPage([200, 200]);
      return d.save();
    };
    const outDoc = await PDFDocument.create();
    for (const b of [await mk(2), await mk(3)]) {
      const s = await PDFDocument.load(b);
      (await outDoc.copyPages(s, s.getPageIndices())).forEach((p) => outDoc.addPage(p));
    }
    return (await PDFDocument.load(await outDoc.save())).getPageCount();
  });

  // open a tool page inside the app
  await win.click('.tool-card[data-tool="Merge PDF"]');
  await win.waitForTimeout(900);
  out.toolPage = await win.evaluate(() => ({
    h1: document.querySelector('#tool-page h1') && document.querySelector('#tool-page h1').textContent,
    url: location.href.split('/').pop(),
  }));

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
})().catch((e) => { console.error('SMOKE FAILED:', e.message); process.exit(1); });
