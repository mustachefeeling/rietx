const { chromium } = require(process.env.PWC);
const URL = 'http://127.0.0.1:8799/';
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const OUT = process.env.OUT;
async function post(page, path, body) {
  const r = await page.request.post(URL + path, { data: body });
  if (!r.ok()) throw new Error(path + ' -> ' + r.status() + ' ' + (await r.text()).slice(0, 200));
  return r;
}
async function put(page, path, body) {
  const r = await page.request.put(URL + path, { data: body });
  if (!r.ok()) throw new Error(path + ' -> ' + r.status() + ' ' + (await r.text()).slice(0, 200));
}
async function runOnce(page) {
  await page.getByRole('button', { name: 'Run', exact: true }).click();
  await page.waitForSelector('header .pill[data-state="running"]', { timeout: 30000 });
  await page.waitForSelector('header .pill[data-state="idle"]', { timeout: 600000 });
  await page.waitForTimeout(2500);
}
async function setTheme(page, theme) {
  await page.click(`.theme button[aria-label="${theme}"]`);
  await page.waitForFunction(t => document.documentElement.dataset.theme === t, theme, { timeout: 10000 });
  await page.waitForTimeout(400);
}
(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--disable-gpu', '--no-sandbox'] });
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, deviceScaleFactor: 2, colorScheme: 'light' });
  const page = await ctx.newPage();
  await page.goto(URL); await page.waitForSelector('.tab', { timeout: 60000 }); await page.waitForTimeout(1200);
  await setTheme(page, 'light');
  const dismiss = page.locator('.checklist button', { hasText: 'Dismiss' });
  if (await dismiss.count()) { await dismiss.click(); await page.waitForTimeout(600); }
  // lineage 1: the example's own protocol
  await runOnce(page);
  // lineage 2: same plan, from the cell node
  await post(page, 'api/history/checkout', { node_id: 'n0003' });
  await page.reload(); await page.waitForSelector('.tab', { timeout: 60000 }); await page.waitForTimeout(1200);
  await runOnce(page);
  // lineage 3: a different strategy from the displacement node
  await post(page, 'api/history/checkout', { node_id: 'n0002' });
  await put(page, 'api/plan', { preset: 'mccusker_structural' });
  await page.reload(); await page.waitForSelector('.tab', { timeout: 60000 }); await page.waitForTimeout(1200);
  await runOnce(page);
  const h = await (await page.request.get(URL + 'api/history')).json();
  console.log('nodes', h.n_nodes, 'head', h.head);
  await page.click('.tab:text-is("History")'); await page.waitForTimeout(1200);
  for (const theme of ['light', 'dark']) {
    await setTheme(page, theme);
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}/gui-history-${theme}.png` });
    await page.locator('.side').first().screenshot({ path: `${OUT}/gui-history-panel-${theme}.png` });
  }
  await browser.close();
})().catch(e => { console.error('FAILED', e); process.exit(1); });
