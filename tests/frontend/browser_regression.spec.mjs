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
      await expect(panel.getByRole('heading', { name: 'Fixture Bridge', exact: true })).toBeVisible();
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
  await search.fill(''); await panel.locator('.filters > summary').click();
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

test('an open filter dropdown survives a backend refresh', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('.filters > summary').click();
  const select = panel.locator('[data-filter=domain]');
  await select.focus();
  const original = await select.elementHandle();
  await panel.evaluate(element => element.refresh(false));
  expect(await original.evaluate(node => node.isConnected)).toBe(true);
  await expect(select).toBeFocused();
  const beforeBlur = await panel.evaluate(element => element.renderCount);
  await panel.getByRole('heading', { name: 'Geräte verwalten' }).click();
  await expect.poll(() => panel.evaluate(element => element.renderCount)).toBeGreaterThan(beforeBlur);
});

test('filter dropdown supports waiting, selection, keyboard, outside click and another filter', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('.filters > summary').click();
  const domain = panel.locator('[data-filter=domain]');
  await domain.focus();
  const original = await domain.elementHandle();
  await page.waitForTimeout(3500);
  await panel.evaluate(async element => {
    element.onInventoryUpdated({ data: { revision: 1 } });
    while (element.loading) await new Promise(resolve => setTimeout(resolve, 5));
  });
  expect(await original.evaluate(node => node.isConnected)).toBe(true);
  await domain.selectOption('light');
  await expect(domain).toHaveValue('light');
  await expect(domain).toBeFocused();
  await domain.press('Tab');
  const area = panel.locator('[data-filter=area]');
  await area.focus();
  await area.press('Escape');
  await area.press('Tab');
  await expect(panel.locator('[data-filter=device]')).toBeFocused();
  await area.focus();
  await area.selectOption('Kitchen');
  await expect(area).toHaveValue('Kitchen');
  await expect(panel.locator('.result-count')).toContainText('1 von 2');
  await area.click();
  await expect(area).toBeFocused();
  await panel.getByRole('heading', { name: 'Geräte verwalten' }).click();
  await expect(area).not.toBeFocused();
});

test('diagnostic dropdown also survives a backend refresh', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Einstellungen', exact: true }).click();
  await panel.getByRole('button', { name: 'Diagnose', exact: true }).click();
  const select = panel.locator('[data-diagnostic-filter]');
  await select.focus();
  const original = await select.elementHandle();
  await panel.evaluate(element => element.refresh(false));
  expect(await original.evaluate(node => node.isConnected)).toBe(true);
  await expect(select).toBeFocused();
});

test('technical details stay open during passive refresh and no-operation status is clear', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Änderungen', exact: true }).click();
  await expect(panel.locator('.empty-changes')).toContainText('Keine Änderungen vorgemerkt');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('[data-group=entities]').click();
  const details = panel.locator('details[data-detail-key="entity:light.kitchen"]');
  await details.locator('summary').click();
  await expect(details).toHaveAttribute('open', '');
  await panel.evaluate(element => element.refresh(false));
  await expect(details).toHaveAttribute('open', '');
});

test('mobile touch keeps the filter control mounted during refresh', async ({ browser }) => {
  const context = await browser.newContext({ hasTouch: true, isMobile: true, viewport: { width: 390, height: 844 } });
  const page = await context.newPage();
  try {
    await page.goto('/tests/frontend/browser_fixture.html');
    const panel = page.locator('homekit-manager-panel');
    await panel.getByRole('tab', { name: 'Geräte', exact: true }).tap();
    await panel.locator('.filters > summary').tap();
    const select = panel.locator('[data-filter=domain]');
    await select.tap();
    const original = await select.elementHandle();
    await panel.evaluate(element => element.refresh(false));
    expect(await original.evaluate(node => node.isConnected)).toBe(true);
    await select.selectOption('light');
    await expect(panel.locator('.result-count')).toContainText('1 von 2');
  } finally { await context.close(); }
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
    Object.assign(element.entities[1].homekit, {
      configured_by_filter: true, registry_eligible: false,
      runtime_candidate: false, registry_reason: 'category_or_hidden_exclude',
    });
    element.render();
  });
  await expect(panel.locator('.result-count')).toContainText('2 von 2');
  await panel.locator('.filters > summary').click();
  await panel.locator('.inventory-summary > summary').click();
  await expect(panel.locator('.inventory-summary').filter({ hasText: 'Ohne aktuellen State 1' })).toBeVisible();
  await panel.getByRole('searchbox', { name: 'Entitäten suchen' }).fill('Kitchen');
  await expect(panel.locator('.result-count')).toContainText('1 von 2');
  await expect(panel.locator('.inventory-summary').filter({ hasText: 'Ohne aktuellen State 0' })).toBeVisible();
  await panel.getByRole('searchbox', { name: 'Entitäten suchen' }).fill('Temperature');
  await panel.locator('.entity-row details.technical summary').click();
  await expect(panel.locator('.entity-row details.technical')).toContainText('Gerätereferenz');
  await expect(panel.locator('.entity-row details.technical')).toContainText('missing');
  await expect(panel.locator('.entity-row details.technical')).toContainText('Core-Registry-Gate');
  await expect(panel.locator('.entity-row details.technical')).toContainText('Gesperrt');
  await expect(panel.locator('.entity-row')).toContainText('Core-Registry-Sperre');
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
  await expect(panel.locator('[data-apply]')).toHaveCount(0);
  const calls = await page.evaluate(() => window.fixtureCommands.filter(name => name === 'homekit_manager/operation_apply'));
  expect(calls).toHaveLength(1);
});

test('source migration is absent from the 0.10.14 interface', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Einstellungen', exact: true }).click();
  await expect(panel.locator('[data-migration-target]')).toHaveCount(0);
  await expect(panel.locator('[data-migration-start]')).toHaveCount(0);
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/migration_start'))).toBe(false);
});

test('dual-mode assistant separates administration mode from native source', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Einstellungen', exact: true }).click();
  await panel.getByRole('button', { name: 'Konfiguration', exact: true }).click();
  await expect(panel.locator('.dual-mode-card')).toContainText('Verwaltungsmodus');
  await expect(panel.locator('.dual-mode-card')).toContainText('Home Assistant UI / Config Entry');
  await panel.locator('[data-admin-mode="yaml"]').click();
  await expect(panel.locator('.dual-mode-card')).toContainText('YAML nur als sicherer Entwurf verfügbar');
  await expect(panel.locator('.dual-mode-card')).toContainText('QuellenmigrationGesperrt');
  await expect(panel.locator('.dual-mode-card')).toContainText('Diese Quelle bleibt autoritativ und wird durch die Auswahl nicht geändert.');
});

test('bridge details expose source-bound configuration values without YAML structure claims', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.locator('.home-details > summary').click();
  await panel.locator('[data-bridge-expand]').click();
  await panel.getByText('Konfigurationswerte anzeigen').click();
  const values = panel.locator('.config-values');
  await expect(values).toContainText('"port": 21088');
  await expect(values).toContainText('"include_domains"');
  await expect(panel.getByText('YAML-Kommentare und Quelldatei gehören nicht zu diesen Werten.')).toBeVisible();
});

test('whole area and device selection use an explicit draft confirmation', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html'); const panel=page.locator('homekit-manager-panel');
  await panel.getByRole('tab',{name:'Geräte',exact:true}).click();
  const kitchen = panel.locator('.area-card').filter({has:page.locator('[data-area="Kitchen"]')});
  await kitchen.locator('[data-scope-value="excluded"]').click();
  await expect(panel.getByRole('dialog')).toContainText('Entitäten insgesamt1Werden neu ausgeschlossen1');
  await panel.getByRole('button',{name:'Im Entwurf vormerken'}).click();
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).click(); await expect(panel.locator('.change-row')).toHaveCount(1);
});

test('hierarchy uses device area, shows every entity once and scopes bulk edits beyond search', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(element => {
    element.entities = [
      { entity_id: 'light.a1', name: 'Alpha one', domain: 'light', area_id: 'b', area_name: 'Beta', area_source: 'entity', device_area_id: 'a', device_area_name: 'Alpha', device_id: 'device-a', device_name: 'Main device', available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true } },
      { entity_id: 'light.a2', name: 'Alpha two', domain: 'light', area_id: 'a', area_name: 'Alpha', area_source: 'device', device_area_id: 'a', device_area_name: 'Alpha', device_id: 'device-a', device_name: 'Main device', available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true } },
      { entity_id: 'light.b', name: 'Beta orphan', domain: 'light', area_id: 'b', area_name: 'Beta', area_source: 'entity', device_id: null, available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true } },
      { entity_id: 'light.none', name: 'No area', domain: 'light', area_id: null, area_name: null, device_area_id: null, device_area_name: null, device_id: 'device-none', device_name: 'Unassigned device', available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true } },
    ].map(item => ({ registry_entry_present: true, state_present: true, device_registry_status: item.device_id ? 'main' : 'none', ...item }));
    element.render();
  });
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  const alpha = panel.locator('.area-card').filter({ has: page.locator('[data-area="Alpha"]') });
  await expect(alpha).toContainText('1 Gerät · 2 Entitäten');
  await alpha.locator('.area-heading').click();
  await alpha.locator('[data-expand]').click();
  await expect(alpha.locator('.entity-row')).toHaveCount(2);
  await expect(panel.locator('.area-card')).toHaveCount(3);
  await panel.getByRole('searchbox', { name: 'Entitäten suchen' }).fill('Alpha one');
  await expect(alpha.locator('.entity-row')).toHaveCount(1);
  await alpha.locator('[data-scope-kind="area"][data-scope-value="excluded"]').click();
  await expect(panel.getByRole('dialog')).toContainText('Entitäten insgesamt2Werden neu ausgeschlossen2Bereits ausgeschlossen0Werden übersprungen0');
  await panel.getByRole('button', { name: 'Im Entwurf vormerken' }).click();
  expect(await panel.evaluate(element => [...element.draft.keys()].sort())).toEqual(['light.a1', 'light.a2']);
  await expect(alpha).toContainText('Entwurf');
});

test('mixed aggregates and device action count existing drafts and unsupported entities', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(element => {
    element.entities = [
      { entity_id: 'light.on', name: 'On', domain: 'light', area_id: 'a', area_name: 'Alpha', device_id: 'device-a', device_name: 'Lamp', available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true } },
      { entity_id: 'light.off', name: 'Off', domain: 'light', area_id: 'a', area_name: 'Alpha', device_id: 'device-a', device_name: 'Lamp', available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: false } },
      { entity_id: 'light.unsupported', name: 'Unsupported', domain: 'light', area_id: 'a', area_name: 'Alpha', device_id: 'device-a', device_name: 'Lamp', available: true, compatibility: { status: 'unsupported' }, homekit: { configured_by_filter: false } },
    ].map(item => ({ registry_entry_present: true, state_present: true, device_registry_status: item.device_id ? 'main' : 'none', ...item }));
    element.draft.set('light.on', 'excluded'); element.render();
  });
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  const area = panel.locator('.area-card');
  await expect(area).toContainText('Gemischt');
  await area.locator('.area-heading').click();
  const device = area.locator('.device-row');
  await expect(device).toContainText('Gemischt');
  await device.locator('[data-scope-value="included"]').focus();
  await device.locator('[data-scope-value="included"]').press('Enter');
  await expect(panel.getByRole('dialog')).toContainText('Entitäten insgesamt3Werden neu eingeschlossen2Bereits eingeschlossen0Werden übersprungen1');
  await panel.getByRole('button', { name: 'Im Entwurf vormerken' }).click();
  expect(await panel.evaluate(element => [...element.draft])).toEqual([['light.off', 'included']]);
});

test('device bulk actions exclude hidden, disabled, categorized and incompatible entities', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(element => {
    const row = (id, extra = {}) => ({ entity_id: `light.${id}`, name: id, domain: 'light',
      device_id: 'device-a', device_name: 'Lamp', area_id: 'a', area_name: 'Alpha',
      available: true, compatibility: { status: 'supported' },
      homekit: { configured_by_filter: true }, ...extra });
    element.entities = [
      row('eligible'),
      row('unsupported', { compatibility: { status: 'unsupported' } }),
      row('unknown_compatibility', { compatibility: { status: 'unknown' } }),
      row('disabled', { disabled_by: 'user' }),
      row('hidden', { hidden_by: 'user' }),
      row('diagnostic', { entity_category: 'diagnostic' }),
      row('config', { entity_category: 'config' }),
    ].map(item => ({ registry_entry_present: true, state_present: true, device_registry_status: item.device_id ? 'main' : 'none', ...item }));
    element.render();
  });
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('[data-group="devices"]').click();
  const device = panel.locator('.device-row');
  await expect(device.getByRole('button', { name: 'Alle Entitäten in Lamp einschließen' })).toBeVisible();
  await expect(device.getByRole('button', { name: 'Alle Entitäten in Lamp ausschließen' })).toBeVisible();
  await device.locator('[data-scope-value="excluded"]').click();
  const dialog = panel.getByRole('dialog');
  await expect(dialog).toContainText('Entitäten insgesamt7Werden neu ausgeschlossen1Bereits ausgeschlossen0Werden übersprungen6');
  await dialog.getByText('Warum werden Entitäten übersprungen?').click();
  for (const reason of ['1 Nicht HomeKit-kompatibel', '1 Kompatibilität nicht verifiziert', '1 Deaktiviert', '1 Ausgeblendet', '1 Diagnoseentität', '1 Konfigurationsentität']) {
    await expect(dialog).toContainText(reason);
  }
  await panel.getByRole('button', { name: 'Im Entwurf vormerken' }).click();
  expect(await panel.evaluate(element => [...element.draft])).toEqual([['light.eligible', 'excluded']]);
});

test('unknown-only device has a neutral and accurate aggregate label', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(element => {
    element.entities = [{ entity_id: 'light.unknown', name: 'Unknown', domain: 'light',
      device_id: 'device-a', device_name: 'Lamp', area_id: 'a', area_name: 'Alpha',
      available: true, compatibility: { status: 'supported' },
      homekit: { configured_by_filter: null } }].map(item => ({ registry_entry_present: true, state_present: true, device_registry_status: item.device_id ? 'main' : 'none', ...item }));
    element.render();
  });
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('[data-group="devices"]').click();
  await expect(panel.locator('.device-row')).toContainText('Nicht verifiziert');
});

test('broad filter migration stays a draft until server plan and exact apply confirmation', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html?isolated-write');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Einstellungen' }).click();
  await panel.getByRole('button', { name: 'Konfiguration', exact: true }).click();
  await panel.locator('[data-positive-migration]').click();
  await expect(panel.getByRole('dialog')).toContainText('1 aktuell durch den Filter ausgewählte Entitäten');
  await panel.getByRole('button', { name: 'Positivlistenentwurf vorbereiten' }).click();
  await expect(panel.locator('.operation-card')).toContainText('Noch nicht geplant');
  await expect(panel.locator('[data-operation-plan]')).toBeEnabled();
  const document = await panel.evaluate(element => element.desiredDocument());
  expect(document.bridges['fixture-bridge']).toEqual({ policy: 'positive_list', entities: { 'light.kitchen': 'include' }, migration_acknowledged: true });
  await panel.locator('[data-operation-plan]').click();
  await expect(panel.locator('.operation-card')).toContainText('validated');
  await expect(panel.locator('.notice.warning')).toContainText('HAP-Accessories nachgewiesen: 1');
  await panel.locator('[data-apply]').click();
  await expect(panel.getByRole('dialog')).toContainText('keine aktuelle Entity-Änderung; Filterregel wird umgestellt');
  await expect(panel.getByRole('dialog')).toContainText('Künftige neue Entitäten bleiben ausgeschlossen');
  await panel.getByRole('button', { name: 'Abbrechen' }).click();
  expect(await page.evaluate(() => window.fixtureCommands.filter(name => name === 'homekit_manager/operation_apply'))).toEqual([]);
});

test('area action spans 5000 entities while search displays one result', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html?paged');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.getByRole('searchbox', { name: 'Entitäten suchen' }).fill('Paged Lamp 4999');
  await expect(panel.locator('.result-count')).toContainText('1 von 5000');
  const started = Date.now();
  await panel.locator('.area-card [data-scope-value="excluded"]').click();
  await expect(panel.getByRole('dialog')).toContainText('Entitäten insgesamt5000Werden neu ausgeschlossen5000');
  await panel.getByRole('button', { name: 'Im Entwurf vormerken' }).click();
  expect(await panel.evaluate(element => element.draft.size)).toBe(5000);
  expect(Date.now() - started).toBeLessThan(10000);
});

test('configuration source and write status are clear without a management switch', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html'); const panel=page.locator('homekit-manager-panel');
  await panel.locator('.home-details > summary').click();
  await expect(panel.locator('.home-details')).toContainText('Schreibstatus');
  await expect(panel.locator('[data-management-enable], [data-management-disable]')).toHaveCount(0);
  await panel.getByRole('tab',{name:'Einstellungen',exact:true}).click();
  await panel.getByRole('button',{name:'Konfiguration',exact:true}).click();
  await expect(panel.locator('.dual-mode-card')).toContainText('Home Assistant UI / Config Entry');
  await expect(panel.locator('.settings-content')).toContainText('native Konfigurationsquelle werden getrennt angezeigt');
  expect(await page.evaluate(() => window.fixtureCommands.some(type => type === 'homekit_manager/management_enable' || type === 'homekit_manager/management_disable'))).toBe(false);
});

test('unknown activation stays neutral, all settings remain reachable, keyboard tabs work', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html?activation-error'); const panel=page.locator('homekit-manager-panel');
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).click();
  await expect(panel.locator('.empty-changes')).toContainText('Keine Änderungen vorgemerkt');
  await expect(panel.locator('.notice.warning')).toContainText('nicht bestätigt');
  await expect(panel.locator('[data-apply]')).toHaveCount(0);
  await panel.locator('.activation-history > summary').click();
  await panel.locator('.activation-history [data-refresh]').click();
  await expect(panel.locator('.notice.warning')).toContainText('nicht bestätigt');
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).focus();
  await panel.getByRole('tab',{name:'Änderungen',exact:true}).press('ArrowRight');
  await expect(panel.getByRole('tab',{name:'Einstellungen',exact:true})).toBeFocused();
  for(const section of ['general','configuration','diagnostics','rules','history','performance']) {
    await panel.locator(`[data-settings-view=${section}]`).click(); await expect(panel.locator('.settings-nav')).toBeVisible(); await expect(panel.locator('.settings-content h3').first()).toBeVisible();
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

test('five thousand entities load through bounded WebSocket inventory pages', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html?paged'); const panel = page.locator('homekit-manager-panel');
  await expect.poll(() => panel.evaluate(element => element.entities.length)).toBe(5000);
  expect(await page.evaluate(() => window.fixtureCommands.filter(type => type === 'homekit_manager/inventory').length)).toBe(10);
  await panel.getByRole('tab', {name:'Geräte', exact:true}).click();
  await panel.locator('[data-group=entities]').click();
  await expect(panel.locator('.entity-row')).toHaveCount(80);
  await expect(panel.locator('.result-count')).toContainText('5000 von 5000');
});

test('snapshot drift during inventory paging blocks partial publication', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html?paged&stale-page'); const panel = page.locator('homekit-manager-panel');
  await expect(panel.getByRole('alert')).toContainText('während des Seitenabrufs');
  expect(await panel.evaluate(element => element.entities.length)).toBe(0);
});

test('search, sort, filters and bulk draft span every loaded inventory page', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html?paged'); const panel = page.locator('homekit-manager-panel');
  await expect.poll(() => panel.evaluate(element => element.entities.length)).toBe(5000);
  await panel.getByRole('tab', {name:'Geräte', exact:true}).click();
  await panel.locator('[data-group=entities]').click();
  const sorted = await panel.evaluate(element => [element.filtered[0].entity_id, element.filtered.at(-1).entity_id]);
  expect(sorted).toEqual(['light.paged_0', 'light.paged_4999']);
  const search = panel.getByRole('searchbox', {name:'Entitäten suchen'});
  await search.fill('Paged Lamp 4999');
  await expect(panel.locator('.result-count')).toContainText('1 von 5000');
  await expect(panel.locator('.entity-row code')).toHaveText('light.paged_4999');
  await search.fill('');
  await panel.locator('.filters > summary').click();
  for (const [key, value] of [['domain', 'light'], ['status', 'included'], ['compatibility', 'supported'], ['availability', 'available'], ['integration', 'demo']]) {
    await panel.locator(`[data-filter=${key}]`).selectOption(value);
    await expect(panel.locator('.result-count')).toContainText('5000 von 5000');
    await panel.locator('[data-reset-filters]').click();
  }
  await panel.locator('[data-selection]').click();
  await panel.locator('[data-select="light.paged_0"]').check();
  await panel.getByRole('button', {name:'Nächste Seite'}).click();
  await panel.locator('[data-select="light.paged_80"]').check();
  await search.fill('Paged Lamp 4999');
  await panel.locator('[data-select="light.paged_4999"]').check();
  await expect(panel.locator('.selection-bar')).toContainText('3 ausgewählt');
  await panel.locator('[data-exclude]').click();
  await expect(panel.locator('dialog')).toContainText('Die Bestätigung ändert nur den Entwurf');
  await panel.locator('[data-confirm-accept]').click();
  await panel.getByRole('tab', {name:'Änderungen', exact:true}).click();
  await expect(panel.locator('.change-row')).toHaveCount(3);
  expect(await panel.locator('.change-row code').allTextContents()).toEqual([
    'light.paged_0', 'light.paged_80', 'light.paged_4999',
  ]);
  await expect(panel.locator('[data-apply]')).toBeDisabled();
});

test('native test mode is opt-in, bridge-bound in UI and revocable before apply', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', {name:'Einstellungen', exact:true}).click();
  await panel.getByRole('button', {name:'Konfiguration', exact:true}).click();
  await expect(panel.locator('[data-test-mode-enable]')).toBeVisible();
  await expect(panel.locator('[data-test-mode-disable]')).toHaveCount(0);
  await panel.locator('[data-test-mode-enable]').click();
  await expect(panel.locator('dialog')).toContainText('fixture-bridge');
  await expect(panel.locator('dialog')).toContainText('60 Minuten');
  await panel.locator('[data-confirm-cancel]').click();
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/test_write_mode_enable'))).toBe(false);
  await panel.locator('[data-test-mode-enable]').click();
  await panel.locator('[data-confirm-accept]').click();
  await expect(panel.locator('[data-test-mode-disable]')).toBeVisible();
  await panel.getByRole('tab', {name:'Geräte', exact:true}).click();
  await panel.locator('[data-group=entities]').click();
  await panel.locator('[data-entity-toggle]').first().click();
  await panel.getByRole('tab', {name:'Änderungen', exact:true}).click();
  await panel.locator('[data-operation-plan]').click();
  await expect(panel.locator('[data-apply]')).toBeEnabled();
  await panel.locator('[data-apply]').click();
  await expect(panel.locator('dialog')).toContainText('light.kitchen: Eingeschlossen → Ausgeschlossen');
  await panel.locator('[data-confirm-cancel]').click();
  await panel.getByRole('tab', {name:'Einstellungen', exact:true}).click();
  await panel.getByRole('button', {name:'Konfiguration', exact:true}).click();
  await panel.locator('[data-test-mode-disable]').click();
  await expect(panel.locator('[data-test-mode-enable]')).toBeVisible();
  await panel.getByRole('tab', {name:'Änderungen', exact:true}).click();
  await expect(panel.locator('[data-apply]')).toBeDisabled();
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/operation_apply'))).toBe(false);
});

test('isolated Core beta native Bridge exposes the explicit test-mode control', async ({page}) => {
  await page.goto('/tests/frontend/browser_fixture.html?core-beta');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', {name:'Einstellungen', exact:true}).click();
  await panel.getByRole('button', {name:'Konfiguration', exact:true}).click();
  await expect(panel.locator('[data-test-mode-enable]')).toBeEnabled();
  await expect(panel.locator('[data-test-mode-disable]')).toHaveCount(0);
});

test('unassigned entities are direct area members and display options only affect the view', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(element => {
    const item = (id, extra = {}) => ({ entity_id: `sensor.${id}`, name: id, domain: 'sensor', area_id: 'trash', area_name: 'Müllplatz',
      device_id: null, device_registry_status: 'none', registry_entry_present: true, state_present: true,
      compatibility: { status: 'supported' }, homekit: { configured_by_filter: false }, ...extra });
    element.entities = [item('blaue_tonne'), item('braune_tonne'), item('gelbe_tonne'), item('graue_tonne'),
      item('diagnose', { entity_category: 'diagnostic' }), item('deaktiviert', { disabled_by: 'integration' }),
      item('versteckt', { hidden_by: 'user' }), item('unbekannt', { compatibility: { status: 'unknown' } })];
    element.render();
  });
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await page.setViewportSize({ width: 390, height: 844 });
  const checkboxWidths = await panel.locator('.display-options input[type="checkbox"]')
    .evaluateAll(inputs => inputs.map(input => input.getBoundingClientRect().width));
  expect(checkboxWidths).toHaveLength(4);
  expect(checkboxWidths.every(width => width >= 16 && width <= 24)).toBe(true);
  const area = panel.locator('.area-card').filter({ has: page.locator('[data-area="Müllplatz"]') });
  await expect(area.locator('.area-heading')).toContainText('0 Geräte · 5 Entitäten');
  await area.locator('.area-heading').click();
  await expect(area.locator('.device-row')).toHaveCount(0);
  await expect(area.locator('.unassigned .entity-row')).toHaveCount(5);
  await expect(area.locator('.unassigned')).toContainText('blaue_tonne');
  await panel.locator('.filters > summary').click();
  await panel.locator('.display-options > summary').click();
  for (const key of ['disabled', 'hidden', 'technical']) await panel.locator(`[data-display="${key}"]`).check();
  await expect(area.locator('.unassigned .entity-row')).toHaveCount(8);
  expect(await panel.evaluate(element => element.draft.size)).toBe(0);
  await area.locator('[data-scope-value="included"]').click();
  await expect(panel.getByRole('dialog').locator('.dialog-counts')).toContainText('Werden übersprungen4');
  await panel.locator('[data-confirm-cancel]').click();
  expect(await panel.evaluate(element => element.draft.size)).toBe(0);
});

test('same-name devices remain distinct and aggregate only regularly manageable entities', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(element => {
    const item = (id, device, area, extra = {}) => ({ entity_id: `light.${id}`, name: `Decke ${id}`, domain: 'light',
      device_id: device, device_name: 'Decke', device_area_id: area, device_area_name: area, area_id: area, area_name: area,
      device_registry_status: 'main', registry_entry_present: true, state_present: true,
      compatibility: { status: 'supported' }, homekit: { configured_by_filter: true }, ...extra });
    element.entities = [item('flur', 'one', 'Flur'), item('flur_hidden', 'one', 'Flur', { hidden_by: 'user', homekit: { configured_by_filter: false } }),
      item('katzen', 'two', 'Katzengefängnis')]; element.render();
  });
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await panel.locator('[data-group="devices"]').click();
  await expect(panel.locator('.device-row')).toHaveCount(2);
  await expect(panel.locator('.device-row').first()).toContainText('Decke · Flur');
  await expect(panel.locator('.device-row').last()).toContainText('Decke · Katzengefängnis');
  await expect(panel.locator('.device-row').first().locator('.device-head small')).toContainText('Eingeschlossen');
  await panel.locator('.device-row').first().locator('[data-expand]').click();
  await expect(panel.locator('.device-row').first().locator('.entity-row')).toHaveCount(1);
  await panel.locator('.filters > summary').click();
  await panel.locator('.display-options > summary').click();
  await panel.locator('[data-display="hidden"]').check();
  await expect(panel.locator('.device-row').first().locator('.entity-row')).toHaveCount(2);
  await expect(panel.locator('.device-row').first().locator('.device-head small')).toContainText('Eingeschlossen');
});

test('bulk action with no effective change does not create a draft or dialog', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  const kitchen = panel.locator('.area-card').filter({ has: page.locator('[data-area="Kitchen"]') });
  await kitchen.locator('[data-scope-value="included"]').click();
  await expect(panel.getByRole('dialog')).toHaveCount(0);
  expect(await panel.evaluate(element => element.draft.size)).toBe(0);
  await expect(panel.locator('.status-line')).toContainText('Keine Änderung erforderlich');
});

test('five thousand device references remain paged and searchable', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(element => {
    element.entities = Array.from({ length: 5000 }, (_, index) => ({
      entity_id: `light.device_${index}`, name: `Lamp ${index}`, domain: 'light',
      device_id: `device-${index}`, device_name: `Device ${index}`, device_registry_status: 'main',
      area_id: 'many', area_name: 'Viele Geräte', device_area_id: 'many', device_area_name: 'Viele Geräte',
      registry_entry_present: true, state_present: true, available: true,
      compatibility: { status: 'supported' }, homekit: { configured_by_filter: true },
    })); element.render();
  });
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  const area = panel.locator('.area-card');
  await expect(area).toHaveCount(1);
  await area.locator('.area-heading').click();
  await expect(area.locator('.device-row')).toHaveCount(40);
  await panel.locator('[data-group="devices"]').click();
  await expect(panel.locator('.device-row')).toHaveCount(80);
  await panel.getByRole('searchbox', { name: 'Entitäten suchen' }).fill('Device 4999');
  await expect(panel.locator('.device-row')).toHaveCount(1);
  await expect(panel.locator('.device-row')).toContainText('Device 4999');
});
