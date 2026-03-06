/**
 * QAForge UI Screenshot Helper
 *
 * Usage:
 *   node screenshot.js <page> [label]
 *
 * Pages:
 *   dashboard    — Project dashboard (default: Reltio MDM E2E Demo)
 *   test-plans   — Test Plans tab
 *   test-cases   — Test Cases tab
 *   executions   — Executions tab
 *   knowledge    — Knowledge Base tab
 *   guide        — In-app Guide page
 *   projects     — Projects list
 *
 * Output: saves PNG to /tmp/qaforge-<label>-<timestamp>.png and prints the path
 */

const { chromium } = require('playwright');

const BASE = 'https://qaforge.freshgravity.net';
const EMAIL = 'admin@freshgravity.com';
const PASSWORD = 'admin123';
const PROJECT_ID = 'a8cd771e-07fa-4585-886b-0ff69d655f64';

const pageArg = process.argv[2] || 'dashboard';
const label = process.argv[3] || pageArg;
const ts = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
const outFile = `/tmp/qaforge-${label}-${ts}.png`;

const PAGE_MAP = {
  'dashboard':   `/projects/${PROJECT_ID}`,
  'test-plans':  `/projects/${PROJECT_ID}?tab=test_plans`,
  'test-cases':  `/projects/${PROJECT_ID}?tab=test_cases`,
  'executions':  `/projects/${PROJECT_ID}?tab=test_plans`,
  'knowledge':   `/projects/${PROJECT_ID}?tab=knowledge`,
  'guide':       `/guide`,
  'projects':    `/projects`,
};

(async () => {
  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({
    viewport: { width: 1440, height: 900 },
    ignoreHTTPSErrors: true,
  });
  const pg = await context.newPage();

  try {
    // Login
    await pg.goto(`${BASE}/login`, { waitUntil: 'networkidle' });
    await pg.fill('input[type="email"]', EMAIL);
    await pg.fill('input[type="password"]', PASSWORD);
    await pg.click('button[type="submit"]');
    await pg.waitForTimeout(3000);

    // Navigate
    const targetPath = PAGE_MAP[pageArg] || PAGE_MAP['dashboard'];
    await pg.goto(`${BASE}${targetPath}`, { waitUntil: 'networkidle' });
    await pg.waitForTimeout(2000);

    // Screenshot
    await pg.screenshot({ path: outFile, fullPage: false });
    console.log(outFile);
  } catch (err) {
    console.error('Screenshot failed:', err.message);
    process.exit(1);
  } finally {
    await browser.close();
  }
})();
