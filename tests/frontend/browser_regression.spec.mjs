import { test, expect } from '@playwright/test';
import path from 'node:path';
import fs from 'node:fs';

const sizes = [['phone-320', 320, 740], ['phone-430', 430, 932], ['tablet', 768, 1024], ['desktop', 1440, 900]];
const views = [['home', 'HomeKit'], ['devices', 'Geräte'], ['changes', 'Änderungen'], ['settings', 'Einstellungen']];
const artifacts = process.env.HKM_SCREENSHOTS || 'test-results/screenshots';

for (const [name, width, height] of sizes) {
  for (const colorScheme of ['light', 'dark']) {
    test(`${name} ${colorScheme}: all four views fit and navigate`, async ({ page }, info) => {
      await page.setViewportSize({ width, height }); await page.emulateMedia({ colorScheme });
      const errors = []; page.on('pageerror', error => errors.push(error.message));
      await page.goto('/tests/frontend/browser_fixture.html');
      const panel = page.locator('homekit-manager-panel');
      await expect(panel.getByText('Fixture Bridge', { exact: true })).toBeVisible();
      for (const [id, label] of views) {
        await panel.getByRole('tab', { name: label, exact: true }).click();
        await expect(panel.getByRole('tab', { name: label, exact: true })).toHaveAttribute('aria-selected', 'true');
        await expect(panel.locator('h2').first()).toBeVisible();
        const geometry = await panel.evaluate(element => {
          const root = element.shadowRoot;
          return { pageOverflow: document.documentElement.scrollWidth - innerWidth, navOverflow: root.querySelector('.main-nav').scrollWidth - root.querySelector('.main-nav').clientWidth, cardOverflow: [...root.querySelectorAll('.surface,.area-card')].some(card => card.getBoundingClientRect().right > innerWidth + 1) };
        });
        expect(geometry.pageOverflow).toBeLessThanOrEqual(1); expect(geometry.navOverflow).toBeLessThanOrEqual(1); expect(geometry.cardOverflow).toBe(false);
        await page.screenshot({ path: path.join(artifacts, info.project.name, `${name}-${colorScheme}-${id}.png`), fullPage: true });
      }
      expect(errors).toEqual([]);
    });
  }
}

test('search keeps focus, supports areas, all filters work, and pagination reaches later entries', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html'); const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  const search = panel.getByRole('searchbox', { name: 'Entitäten suchen' });
  await search.pressSequentially('Kitchen'); await expect(search).toBeFocused(); await expect(search).toHaveValue('Kitchen');
  await search.fill('Hall'); await expect(panel.locator('.result-count')).toContainText('1 von 2');
  await search.fill(''); await panel.locator('.filters summary').click();
  for (const [key, value] of [['domain', 'light'], ['area', 'Kitchen'], ['device', 'Kitchen device'], ['status', 'included'], ['compatibility', 'supported'], ['availability', 'available'], ['integration', 'sensor_demo']]) {
    await panel.locator(`[data-filter=${key}]`).selectOption(value);
    await expect(panel.locator('.result-count')).toContainText('1 von 2');
    await panel.locator('[data-reset-filters]').click();
  }
  await panel.locator('[data-group=entities]').click();
  await panel.evaluate(element => { element.entities = Array.from({length: 101}, (_, index) => ({ entity_id: `light.test_${index}`, name: `Lamp ${index}`, domain: 'light', available: true, compatibility: {status: 'supported'}, homekit: {configured_by_filter: true} })); element.render(); });
  await expect(panel.locator('.entity-row')).toHaveCount(80);
  await panel.getByRole('button', {name: 'Nächste Seite'}).click(); await expect(panel.locator('.entity-row')).toHaveCount(21);
});

test('availability totals follow current hits and missing device is evidence, not orphan proof', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('[data-group=entities]').click();
  await panel.evaluate(element => {
    Object.assign(element.entities[1], {
      availability_status: 'no_state', state_present: false,
      registry_entry_present: true, device_registry_status: 'missing',
      area_source: 'device', disabled_by: null, hidden_by: null,
    });
    element.render();
  });
  await expect(panel.locator('.result-count')).toContainText('2 von 2');
  await expect(panel.locator('p.muted').filter({ hasText: 'Ohne aktuellen State 1' })).toBeVisible();
  await panel.getByRole('searchbox', { name: 'Entitäten suchen' }).fill('Kitchen');
  await expect(panel.locator('.result-count')).toContainText('1 von 2');
  await expect(panel.locator('p.muted').filter({ hasText: 'Ohne aktuellen State 0' })).toBeVisible();
  await panel.getByRole('searchbox', { name: 'Entitäten suchen' }).fill('Temperature');
  await panel.locator('.entity-row details.technical summary').click();
  await expect(panel.locator('.entity-row details.technical')).toContainText('Gerätereferenz');
  await expect(panel.locator('.entity-row details.technical')).toContainText('missing');
  await expect(panel.locator('.entity-row details.technical')).not.toContainText('Verwaist');
});

test('draft workflow validates, saves, downloads and keeps applying disabled', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html'); const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click(); await panel.locator('[data-group=entities]').click();
  await panel.locator('[data-entity-toggle]').first().click();
  await panel.getByRole('tab', { name: 'Änderungen', exact: true }).click();
  await expect(panel.locator('.change-row')).toHaveCount(1); await expect(panel.locator('.change-row code')).toHaveText('light.kitchen');
  await panel.locator('[data-preview]').click(); await expect(panel.locator('.status-line')).toContainText('Vorschau bestätigt');
  await panel.locator('[data-save]').click(); await expect(panel.locator('.status-line')).toContainText('Entwurf gespeichert');
  await expect(panel.locator('[data-apply]')).toBeDisabled();
  await panel.locator('[data-action-menu]').click();
  const downloadPromise = page.waitForEvent('download'); await panel.locator('[data-export]').click(); const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('homekit-manager-entwurf.yaml');
  expect(fs.readFileSync(await download.path(), 'utf8')).toContain('schema_version: 1');
  await panel.locator('[data-load]').click(); await panel.getByRole('button', {name:'Entwurf laden', exact:true}).last().click();
  await expect(panel.locator('.status-line')).toContainText('Entwurf geladen');
  await panel.locator('[data-discard]').click();
  await panel.getByRole('button', {name:'Verwerfen', exact:true}).last().click(); await expect(panel.locator('.change-row')).toHaveCount(0);
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/apply_options_diff'))).toBe(false);
});

test('isolated operation workflow binds plan, confirms exact request and verifies outcome', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html?isolated-write');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('[data-group=entities]').click();
  await panel.locator('[data-entity-toggle]').first().click();
  await panel.getByRole('tab', { name: 'Änderungen', exact: true }).click();
  await expect(panel.locator('[data-apply]')).toBeDisabled();
  await panel.locator('[data-operation-plan]').click();
  await expect(panel.locator('.operation-card')).toContainText('fixture-operation-1');
  await expect(panel.locator('[data-apply]')).toBeEnabled();
  await panel.locator('[data-apply]').click();
  await expect(panel.locator('dialog')).toContainText('fixture-operation-1');
  await panel.getByRole('button', { name: 'Genau diese Änderung anwenden' }).click();
  await expect(panel.locator('.status-line')).toContainText('Backend verifiziert');
  await expect(panel.locator('[data-apply]')).toBeDisabled();
  const calls = await page.evaluate(() => window.fixtureCommands.filter(name => name === 'homekit_manager/operation_apply'));
  expect(calls).toHaveLength(1);
});

test('source migration is absent from the 0.9.24 interface', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Einstellungen', exact: true }).click();
  await expect(panel.locator('[data-migration-target]')).toHaveCount(0);
  await expect(panel.locator('[data-migration-start]')).toHaveCount(0);
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/migration_start'))).toBe(false);
});

test('bridge details expose source-bound configuration values without YAML structure claims', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.locator('[data-bridge-expand]').click();
  await panel.getByText('Konfigurationswerte anzeigen').click();
  const values = panel.locator('.config-values');
  await expect(values).toContainText('"port": 21088');
  await expect(values).toContainText('"include_domains"');
  await expect(panel.getByText('YAML-Kommentare und Quelldatei gehören nicht zu diesen Werten.')).toBeVisible();
});

test('whole area and device selection use an explicit draft confirmation', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html'); const panel=page.locator('homekit-manager-panel');
  await panel.getByRole('tab',{name:'Geräte',exact:true}).click(); await panel.locator('[data-selection]').click();
  await panel.locator('[data-select-area="Kitchen"]').click(); await expect(panel.locator('.selection-bar')).toContainText('1 ausgewählt');
  await panel.locator('[data-exclude]').click(); await expect(panel.getByRole('dialog')).toBeVisible();
  await panel.getByRole('button',{name:'Vormerken',exact:true}).click(); await expect(panel.locator('.selection-bar')).toContainText('0 ausgewählt');
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).click(); await expect(panel.locator('.change-row')).toHaveCount(1);
});

test('management metadata can move in both directions with backend-confirmed dialogs', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html'); const panel=page.locator('homekit-manager-panel');
  await panel.locator('[data-management-enable]').click(); await expect(panel.getByRole('dialog')).toBeVisible();
  await panel.getByRole('button',{name:'Verwaltung übernehmen',exact:true}).last().click();
  await expect(panel.locator('[data-management-disable]')).toBeVisible();
  await panel.locator('[data-management-disable]').click(); await panel.getByRole('button',{name:'Zurückstellen',exact:true}).click();
  await expect(panel.locator('[data-management-enable]')).toBeVisible();
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/apply_options_diff'))).toBe(false);
});

test('unknown activation stays neutral, all settings remain reachable, keyboard tabs work', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html?activation-error'); const panel=page.locator('homekit-manager-panel');
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).click();
  await expect(panel.locator('[data-activation-state=unknown]')).toHaveClass(/tone-neutral/);
  await expect(panel.locator('[data-apply]')).toBeDisabled(); await panel.locator('[data-refresh]').last().click();
  await expect(panel.locator('[data-activation-state=unknown]')).toHaveClass(/tone-neutral/);
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).focus();
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).press('ArrowRight');
  await expect(panel.getByRole('tab',{name:'Einstellungen',exact:true})).toBeFocused();
  for(const section of ['general','configuration','diagnostics','rules','history','performance']) {
    await panel.locator(`[data-settings-view=${section}]`).click(); await expect(panel.locator('.settings-nav')).toBeVisible(); await expect(panel.locator('.settings-content h3')).toBeVisible();
  }
});

test('transport errors are visible and do not pretend empty success', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html?error'); const panel=page.locator('homekit-manager-panel');
  await expect(panel.getByRole('alert')).toContainText('Fixture-WebSocket nicht erreichbar');
  await expect(panel.locator('.tone-success')).toHaveCount(0);
});

test('large inventories render a bounded entity page', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html'); const panel=page.locator('homekit-manager-panel');
  const metrics = await panel.evaluate(element => { element.entities=Array.from({length:5000},(_,i)=>({entity_id:`light.large_${i}`,name:`Lamp ${i}`,domain:'light',available:true,compatibility:{status:'supported'},homekit:{configured_by_filter:true}})); element.view='devices';element.groupMode='entities';const start=performance.now();element.render();return {ms:performance.now()-start,rows:element.shadowRoot.querySelectorAll('.entity-row').length}; });
  expect(metrics.rows).toBe(80); expect(metrics.ms).toBeLessThan(1000); console.log('5000 entity page',metrics);
});
