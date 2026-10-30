// Isolated visual comparison: released v0.10.5 frontend vs the current source.
import { chromium } from 'playwright';
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';

const base = 'http://127.0.0.1:4173/tests/frontend/browser_fixture.html';
const output = path.resolve('docs/screenshots/0.10.6');
fs.mkdirSync(output, { recursive: true });
const baseline = execFileSync('git', ['show', 'v0.10.5:custom_components/homekit_manager/www/homekit-manager.js']);
const browser = await chromium.launch({ headless: true });
const measurements = {};

try {
  for (const version of ['before', 'after']) {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: 'dark' });
    if (version === 'before') {
      await context.route('**/custom_components/homekit_manager/www/homekit-manager.js', route =>
        route.fulfill({ status: 200, contentType: 'application/javascript', body: baseline }));
    }
    const page = await context.newPage();
    const panel = page.locator('homekit-manager-panel');
    const open = async (view) => {
      await page.goto(base);
      await panel.getByRole('tab', { name: view, exact: true }).click();
    };
    const capture = async (name) => page.screenshot({ path: path.join(output, `${version}-${name}.png`), fullPage: true });

    await open('HomeKit'); await capture('home');
    await open('Geräte'); await capture('devices');
    measurements[version] = await panel.evaluate(element => {
      const areas = [...element.shadowRoot.querySelectorAll('.area-card')];
      const options = element.shadowRoot.querySelector('.display-options');
      const filter = element.shadowRoot.querySelector('.filters');
      return { area_heights: areas.map(item => item.getBoundingClientRect().height),
        fully_visible_areas: areas.filter(item => item.getBoundingClientRect().bottom <= innerHeight).length,
        display_options_height: options?.getBoundingClientRect().height,
        filter_height: filter?.getBoundingClientRect().height };
    });
    await panel.locator('.area-card').first().screenshot({ path: path.join(output, `${version}-closed-area.png`) });
    await panel.locator('.area-heading').first().click(); await capture('open-area');
    await open('Geräte'); await panel.locator('[data-group="devices"]').click();
    await panel.locator('.device-row').first().screenshot({ path: path.join(output, `${version}-closed-device.png`) });
    await panel.locator('.device-row [data-expand]').first().click(); await capture('open-device');
    await open('Geräte'); await panel.locator('.filters > summary').click();
    if (version === 'after') await panel.locator('.display-options > summary').click();
    await capture('filter');
    await open('Änderungen'); await capture('changes-empty');
    await panel.evaluate(element => { element.draft.set('light.kitchen', 'excluded'); element.render(); });
    await capture('changes-draft');
    await open('Einstellungen'); await capture('settings');
    await context.close();
  }
} finally {
  await browser.close();
}
fs.writeFileSync(path.join(output, 'measurements.json'), `${JSON.stringify(measurements, null, 2)}\n`);
console.log(JSON.stringify(measurements));
