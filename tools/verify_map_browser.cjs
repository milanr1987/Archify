const path = require('path');
const fs = require('fs');
const assert = require('assert/strict');
const { pathToFileURL } = require('url');
const root = path.resolve(__dirname, '..');
process.env.PLAYWRIGHT_BROWSERS_PATH = process.env.PLAYWRIGHT_BROWSERS_PATH || path.join(root, '.playwright-browsers');
const { chromium } = require(path.join(root, '.venv/Lib/site-packages/playwright/driver/package'));
(async () => {
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
    const network = [], errors = [];
    page.on('request', req => { if (!/^(file|data):/.test(req.url())) network.push(req.url()); });
    page.on('pageerror', error => errors.push(String(error)));
    await page.goto(pathToFileURL(path.join(root, 'output/index.html')).href);
    await page.locator('#list .row').filter({ hasText: 'workspace-atlas' }).click();
    assert.match(await page.locator('.map-status').textContent(), /Mapa:/);
    await page.locator('.map-link').click();
    await page.waitForLoadState('load');
    assert.match(page.url(), /maps\/atlas-demo\.html$/);
    assert.ok(await page.locator('svg').count() > 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({ path:path.join(root,'output/e2e/atlas-demo.png'), fullPage:true });
    assert.deepEqual(network, []);
    assert.deepEqual(errors, []);
    console.log('OK: catalog map link, status, native Archify SVG, no external resources, screenshot');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
