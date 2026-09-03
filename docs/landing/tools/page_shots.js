const { chromium } = require(process.env.PWC);
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const FILE = 'file://' + process.env.PAGE, OUT = process.env.OUT, W = +(process.env.W || 1280);
(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--disable-gpu', '--no-sandbox'] });
  for (const theme of ['light', 'dark']) {
    const ctx = await browser.newContext({ viewport: { width: W, height: 900 }, deviceScaleFactor: 1, colorScheme: theme });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(FILE); await page.waitForTimeout(2500);
    // stop the animation at a telling frame and freeze
    await page.evaluate(() => { const s = document.querySelector('#scrub'); if (s) { s.value = 120; s.dispatchEvent(new Event('input')); } });
    await page.waitForTimeout(600);
    await page.screenshot({ path: `${OUT}/page-${theme}-${W}.png`, fullPage: true });
    const h = await page.evaluate(() => document.documentElement.scrollHeight);
    console.log(theme, 'height', h, 'errors', errors.length ? errors : 'none');
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.error('FAILED', e); process.exit(1); });
