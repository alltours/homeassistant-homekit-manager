import { test, expect } from '@playwright/test';

test('multi-bridge selection keeps the selected native source explicit', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html?multi-bridge');
  const panel = page.locator('homekit-manager-panel');
  const bridgeSelect = panel.locator('[data-bridge-select]');
  await expect(bridgeSelect).toBeVisible();
  await expect(bridgeSelect).toHaveValue('fixture-bridge');
  await bridgeSelect.selectOption('yaml-fixture-bridge');
  await expect(bridgeSelect).toHaveValue('yaml-fixture-bridge');
  await expect(panel.locator('.bridge-selector')).toContainText('Alle Entwürfe und Aktionen gelten ausschließlich für diese Bridge.');
  await bridgeSelect.selectOption('fixture-bridge');
  await expect(bridgeSelect).toHaveValue('fixture-bridge');
  await panel.locator('.home-details > summary').click();
  await expect(panel.locator('.bridge-card')).toHaveCount(3);

  const yamlCard = panel.locator('.bridge-card').filter({ hasText: 'YAML Fixture Bridge' });
  await yamlCard.getByRole('button', { name: 'Auswählen', exact: true }).click();
  await expect(yamlCard).toContainText('Ausgewählte Bridge');
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/select_bridge'))).toBe(true);

  await panel.getByRole('tab', { name: 'Einstellungen', exact: true }).click();
  await panel.getByRole('button', { name: 'Konfiguration', exact: true }).click();
  await expect(panel.locator('.source-card')).toContainText('YAML');
  await expect(panel.locator('.source-card')).toContainText('Home Assistant YAML (SOURCE_IMPORT)');
  await expect(panel.locator('.settings-content')).toContainText('Ein Wechsel zwischen UI und YAML wird nicht angeboten.');
});

test('unknown bridge selection is rejected without changing the browser selection', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html?multi-bridge');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(async element => {
    await element.selectBridge('unknown-bridge');
  });
  await expect(panel.locator('[role="alert"]').filter({ hasText: 'Unbekannte Bridge' })).toContainText('Unbekannte Bridge');
});
