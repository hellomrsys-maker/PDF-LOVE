/*
 * Keyboard and screen-reader access to the parts of the app that matter.
 *
 *   node scripts/check-a11y.js [--url http://localhost:5599]
 *
 * This is a narrow check, not a full audit. It asserts the three things that
 * were actually broken, so they cannot quietly break again:
 *
 *   1. Every tool card can be reached and activated from the keyboard.
 *      The cards were <button>s, which was fine — until you needed to reach
 *      the favourite star inside one.
 *
 *   2. The favourite star can be reached and toggled from the keyboard.
 *      It was a <span role="button"> with no tabindex, so it was announced
 *      as a button and was not in the tab order: a keyboard user could open
 *      any tool but could not pin one. A control you can see and cannot
 *      operate is worse than one that is not there.
 *
 *   3. Every form control inside a tool panel has an accessible name.
 *      All 138 of them relied on an adjacent <label> with no `for`, or on a
 *      placeholder. A placeholder is not a name — it vanishes on focus and
 *      screen readers announce the control as "edit, blank".
 *
 * A sample of tools is opened rather than all 104: the panels are built by
 * the same handful of helpers, so a representative spread catches a
 * regression in any of them without a five-minute run.
 */
const path = require('path');
const { chromium } = require(process.env.PLAYWRIGHT_PATH || 'playwright');

const args = process.argv.slice(2);
const BASE = args.includes('--url') ? args[args.indexOf('--url') + 1] : 'http://localhost:5599';

// One tool from each panel-building style: file pickers, numeric ranges,
// checkboxes, textareas, selects, and the generators.
const SAMPLE = [
  'Merge PDF', 'Split PDF', 'Make PDF Smaller', 'Rotate PDF', 'Protect PDF',
  'Resize Image', 'Make Image Smaller', 'Images to PDF', 'Add Watermark',
  'Page Numbering & Document ID', 'Remove Duplicate Lines', 'JSON Formatter & Checker',
  'Word & Character Counter', 'QR Code Generator', 'Screen Recorder',
  'Search & Redact', 'Trim Video', 'Invoice Generator',
];

const problems = [];

(async () => {
  const browser = await chromium.launch();
  // Service workers off: this must test the build in the working tree, not
  // whatever a previous run left in the cache. Finding that out the hard
  // way is how the sw.js network-first gap turned up.
  const ctx = await browser.newContext({ serviceWorkers: 'block' });
  const page = await ctx.newPage();
  await page.goto(BASE, { waitUntil: 'networkidle' });

  console.log(`\n  checking keyboard and screen-reader access at ${BASE}\n`);

  // --- 1 & 2: cards and stars are in the tab order -------------------
  const reach = await page.evaluate(() => {
    const card = document.querySelector('.tool-card[data-tool]');
    if (!card) return { error: 'no tool cards rendered' };
    const star = card.querySelector('.fav-star');
    const focusable = el => el && el.tabIndex >= 0 && !el.disabled;
    return {
      cardName: card.dataset.tool,
      cardFocusable: focusable(card),
      cardRole: card.getAttribute('role') || card.tagName.toLowerCase(),
      starExists: !!star,
      starFocusable: focusable(star),
      starTag: star ? star.tagName.toLowerCase() : null,
      starName: star ? (star.getAttribute('aria-label') || star.textContent) : null,
      starPressed: star ? star.getAttribute('aria-pressed') : null,
      // A control nested inside a <button> is invalid and browsers may drop
      // it from the tab order regardless of tabindex.
      nestedInButton: !!(star && star.closest('button') !== star),
    };
  });
  if (reach.error) { problems.push(reach.error); }
  else {
    if (!reach.cardFocusable) problems.push('tool cards are not in the tab order');
    if (!['button', 'link'].includes(reach.cardRole))
      problems.push(`tool card announces as "${reach.cardRole}", not a button`);
    if (!reach.starExists) problems.push('no favourite star on the tool card');
    if (!reach.starFocusable) problems.push('the favourite star is not in the tab order');
    if (reach.nestedInButton)
      problems.push('the favourite star is nested inside a <button>, which is invalid and drops it from the tab order');
    if (!reach.starName || reach.starName === '☆' || reach.starName === '★')
      problems.push('the favourite star has no accessible name (a glyph is not a name)');
    if (reach.starPressed === null)
      problems.push('the favourite star does not expose aria-pressed, so its state is not announced');
    console.log(`  card       ${reach.cardName} — role=${reach.cardRole}, focusable`);
    console.log(`  star       <${reach.starTag}> "${reach.starName}" aria-pressed=${reach.starPressed}`);
  }

  // --- 2b: the star actually toggles from the keyboard ---------------
  const toggled = await page.evaluate(async () => {
    const star = document.querySelector('.tool-card[data-tool] .fav-star');
    if (!star) return null;
    const before = star.getAttribute('aria-pressed');
    star.focus();
    if (document.activeElement !== star) return { focused: false };
    star.click();                       // what Enter/Space does on a <button>
    const after = star.getAttribute('aria-pressed');
    star.click();                       // leave storage as we found it
    return { focused: true, before, after };
  });
  if (!toggled || !toggled.focused) problems.push('the favourite star cannot take keyboard focus');
  else if (toggled.before === toggled.after)
    problems.push('activating the favourite star did not change its pressed state');
  else console.log(`  toggle     aria-pressed ${toggled.before} -> ${toggled.after}, and back`);

  // --- 3: every control in a tool panel has an accessible name -------
  console.log();
  let checked = 0;
  for (const name of SAMPLE) {
    const card = page.locator(`.tool-card[data-tool="${name.replace(/"/g, '\\"')}"]`).first();
    if (!(await card.count())) { problems.push(`no card for "${name}"`); continue; }
    await card.click();
    await page.waitForTimeout(150);

    const unnamed = await page.evaluate(() => {
      const panel = document.querySelector('#panel, #tool-mount');
      if (!panel) return ['no panel opened'];
      const bad = [];
      for (const el of panel.querySelectorAll('input, select, textarea')) {
        if (el.type === 'hidden') continue;
        const named =
          (el.id && panel.querySelector(`label[for="${CSS.escape(el.id)}"]`)) ||
          el.getAttribute('aria-label') ||
          el.getAttribute('aria-labelledby') ||
          el.closest('label');
        // A placeholder is deliberately not accepted: it is a hint, it
        // disappears on focus, and it is not the accessible name.
        if (!named) bad.push(`${el.tagName.toLowerCase()}${el.id ? '#' + el.id : ''}[type=${el.type || '-'}]`);
      }
      return bad;
    });

    const total = await page.evaluate(() => {
      const p = document.querySelector('#panel, #tool-mount');
      return p ? p.querySelectorAll('input, select, textarea').length : 0;
    });
    checked += total;

    if (unnamed.length) {
      problems.push(`${name}: ${unnamed.length} unnamed control(s) — ${unnamed.join(', ')}`);
      console.log(`  FAIL  ${name.padEnd(32)} ${unnamed.length}/${total} unnamed`);
    } else {
      console.log(`  PASS  ${name.padEnd(32)} ${total} control(s), all named`);
    }

    await page.keyboard.press('Escape');
    await page.waitForTimeout(80);
  }

  await browser.close();

  console.log(`\n  ${checked} form control(s) inspected across ${SAMPLE.length} tools`);
  if (problems.length) {
    console.error(`\n  ${problems.length} problem(s):`);
    problems.forEach(p => console.error('   - ' + p));
    console.error('\n  A control that can be seen but not reached, or reached but');
    console.error('  not named, is unusable for anyone not using a mouse and eyes.');
    process.exit(1);
  }
  console.log('\n  Keyboard and screen-reader access is intact.');
})().catch(e => { console.error(e); process.exit(1); });
