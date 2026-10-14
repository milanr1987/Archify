// Fallback browser check using the already installed Playwright Node driver.
const path = require('path');
const assert = require('assert/strict');
const { pathToFileURL } = require('url');
const root = path.resolve(__dirname, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH = process.env.PLAYWRIGHT_BROWSERS_PATH || path.join(root, '.playwright-browsers');
const { chromium } = require(path.join(root, '.venv/Lib/site-packages/playwright/driver/package'));

(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage();
    const external = [], dialogs = [];
    page.on('request', r => { if (!/^(file|data):/.test(r.url())) external.push(r.url()); });
    page.on('dialog', async d => { dialogs.push(d.message()); await d.dismiss(); });
    await page.goto(pathToFileURL(path.join(root, 'output/notes-verification.html')).href);
    await page.fill('#search', 'moja biljeska');
    assert.deepEqual(await page.locator('#list .row-name').allTextContents(), ['fixture-tool']);
    await page.locator('#list .row').click();
    assert.match(await page.locator('.item-id').textContent({ timeout: 2000 }), /^[a-f0-9]{64}$/);
    assert.equal(await page.locator('.detail-note').textContent(),
      '</script><img src=x onerror=alert(1)> moja bilješka');
    await page.fill('#search', 'djurdjevak');
    assert.deepEqual(await page.locator('#list .row-name').allTextContents(), ['fixture-tool']);
    assert.equal(await page.locator('img').count(), 0);
    assert.deepEqual(dialogs, []);
    assert.deepEqual(external, []);
    await page.setViewportSize({ width: 390, height: 844 });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    console.log('OK: notes display, search, diacritics, XSS, offline requests, mobile width');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode = 1; });
