// Screenshot the animation rig alone: PWC=<playwright-core dir> PAGE=<abs html> OUT=<dir> W=<width> FRAMES=120,274 node rig_shots.js
const { chromium } = require(process.env.PWC);
const EXE = process.env.HOME + '/Library/Caches/ms-playwright/chromium-1223/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing';
const FILE = 'file://' + process.env.PAGE, OUT = process.env.OUT, W = +(process.env.W || 1280);
const FRAMES = (process.env.FRAMES || '120').split(',').map(Number);
(async () => {
  const browser = await chromium.launch({ executablePath: EXE, args: ['--disable-gpu', '--no-sandbox'] });
  for (const theme of ['light', 'dark']) {
    const ctx = await browser.newContext({ viewport: { width: W, height: 900 }, deviceScaleFactor: 2, colorScheme: theme });
    const page = await ctx.newPage();
    const errors = [];
    page.on('pageerror', e => errors.push(String(e)));
    page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
    await page.goto(FILE); await page.waitForTimeout(2500);
    for (const f of FRAMES) {
      await page.evaluate(f => { const s = document.querySelector('#scrub'); s.value = f; s.dispatchEvent(new Event('input')); }, f);
      await page.waitForTimeout(400);
      await page.locator('.rig').screenshot({ path: `${OUT}/rig-${theme}-${W}-f${f}.png` });
    }
    console.log(theme, W, 'errors', errors.length ? errors : 'none');
    await ctx.close();
  }
  await browser.close();
})().catch(e => { console.error('FAILED', e); process.exit(1); });
