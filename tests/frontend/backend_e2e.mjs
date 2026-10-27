import { chromium, webkit } from 'playwright';
import assert from 'node:assert/strict';
const [url, browserName] = process.argv.slice(2);
const browser = await ({chromium,webkit}[browserName]).launch({headless:true});
try {
  const page = await browser.newPage({viewport:{width:320,height:740}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  await page.goto(url);
  const panel=page.locator('homekit-manager-panel');
  await panel.getByText('Audit Bridge',{exact:true}).waitFor();
  for(const name of ['HomeKit','Geräte','Änderungen','Einstellungen']) {
    await panel.getByRole('tab',{name,exact:true}).click();
    assert.equal(await panel.locator('h2').first().isVisible(),true);
  }
  assert.equal(await panel.locator('.settings-content').innerText().then(s=>s.includes('0.9.24')),true);
  await panel.getByRole('tab',{name:'Geräte',exact:true}).click();
  await panel.locator('[data-group=entities]').click();
  await panel.getByRole('searchbox').pressSequentially('Audit');
  await panel.locator('[data-entity-toggle="light.audit_lamp"]').click();
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).click();
  await panel.locator('[data-preview]').click();
  await panel.locator('.status-line').filter({hasText:'Vorschau bestätigt'}).waitFor();
  await panel.locator('[data-save]').click();
  await panel.locator('.status-line').filter({hasText:'Entwurf gespeichert'}).waitFor();
  assert.equal(await panel.locator('[data-apply]').isDisabled(),true);
  assert.equal(await panel.locator('[data-activation-state]').getAttribute('data-activation-state'),'unknown');
  await page.setViewportSize({width:1440,height:900});
  await panel.getByRole('tab',{name:'Einstellungen',exact:true}).click();
  await panel.locator('[data-settings-view=history]').click();
  assert.equal(await panel.locator('.history-row').count(),1);
  assert.deepEqual(errors,[]);
  console.log(`real HA backend: ok (${browserName})`);
} finally { await browser.close(); }
