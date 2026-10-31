import { test, expect } from '@playwright/test';

test('multi-bridge selection keeps the selected native source explicit', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html?multi-bridge');
  const panel = page.locator('homekit-manager-panel');
  await panel.locator('.home-details > summary').click();
  await expect(panel.locator('.bridge-card')).toHaveCount(3);

  const yamlCard = panel.locator('.bridge-card').filter({ hasText: 'YAML Fixture Bridge' });
  await yamlCard.getByRole('button', { name: 'Auswählen', exact: true }).click();
  await expect(yamlCard).toContainText('Ausgewählte Bridge');
  expect(await page.evaluate(() => window.fixtureCommands.includes('homekit_manager/select_bridge'))).toBe(true);

  await panel.getByRole('tab', { name: 'Einstellungen', exact: true }).click();
  await panel.getByRole('button', { name: 'Konfiguration', exact: true }).click();
  await expect(panel.locator('.dual-mode-card')).toContainText('YAML');
  await expect(panel.locator('.dual-mode-card')).toContainText('Home Assistant YAML (SOURCE_IMPORT)');
  await expect(panel.locator('.lock-note').filter({ hasText: 'Eine Auswahl des YAML-Modus' })).toContainText('ändert keine produktive HomeKit-Quelle');
});

test('unknown bridge selection is rejected without changing the browser selection', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html?multi-bridge');
  const panel = page.locator('homekit-manager-panel');
  await panel.evaluate(async element => {
    await element.selectBridge('unknown-bridge');
  });
  await expect(panel.locator('[role="alert"]').filter({ hasText: 'Unbekannte Bridge' })).toContainText('Unbekannte Bridge');
});
