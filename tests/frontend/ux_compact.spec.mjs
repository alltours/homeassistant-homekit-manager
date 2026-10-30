import { test, expect } from '@playwright/test';

for (const width of [320, 375, 390, 393, 768, 1440]) {
  test(`compact hierarchy fits ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 844 });
    await page.emulateMedia({ colorScheme: 'dark' });
    await page.goto('/tests/frontend/browser_fixture.html');
    const panel = page.locator('homekit-manager-panel');
    await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
    const areas = panel.locator('.area-card');
    await expect(areas).toHaveCount(2);
    for (const area of await areas.all()) {
      await expect(area.locator('[data-scope-value="included"]')).toBeVisible();
      await expect(area.locator('[data-scope-value="excluded"]')).toBeVisible();
      await expect(area.locator('.area-heading')).toContainText('Entität');
    }
    const geometry = await panel.evaluate(element => {
      const cards = [...element.shadowRoot.querySelectorAll('.area-card')];
      return { overflow: document.documentElement.scrollWidth - innerWidth,
        firstHeight: cards[0].getBoundingClientRect().height,
        secondBottom: cards[1].getBoundingClientRect().bottom };
    });
    expect(geometry.overflow).toBeLessThanOrEqual(1);
    expect(geometry.firstHeight).toBeLessThanOrEqual(width < 390 ? 175 : 145);
    if (width === 390) expect(geometry.secondBottom).toBeLessThanOrEqual(844);
    await panel.locator('[data-group="devices"]').click();
    const device = panel.locator('.device-row').first();
    await expect(device.locator('[data-scope-value="included"]')).toBeVisible();
    await expect(device.locator('[data-scope-value="excluded"]')).toBeVisible();
    await device.locator('[data-expand]').click();
    await expect(device.locator('.entity-row')).toHaveCount(1);
  });
}

test('display options stay inside the filter panel and survive refresh', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await panel.getByRole('tab', { name: 'Geräte', exact: true }).click();
  await expect(panel.locator('.filters')).not.toHaveAttribute('open', '');
  await expect(panel.locator('.display-options input')).toHaveCount(4);
  await panel.locator('.filters > summary').click();
  await expect(panel.locator('.display-options')).not.toHaveAttribute('open', '');
  await panel.locator('.display-options > summary').click();
  await panel.locator('[data-display="disabled"]').check();
  await expect(panel.locator('.filters > summary')).toContainText('Anzeige 1 aktiv');
  await panel.evaluate(element => element.refresh(false));
  await expect(panel.locator('.filters')).toHaveAttribute('open', '');
  await expect(panel.locator('.display-options')).toHaveAttribute('open', '');
  await expect(panel.locator('[data-display="disabled"]')).toBeChecked();
  await panel.locator('.filters > summary').click();
  await expect(panel.locator('.filters > summary')).toContainText('Anzeige 1 aktiv');
});

test('compact overview and empty changes retain warnings and lead to devices', async ({ page }) => {
  await page.goto('/tests/frontend/browser_fixture.html');
  const panel = page.locator('homekit-manager-panel');
  await expect(panel.locator('.home-summary')).toContainText('Fixture Bridge');
  await expect(panel.locator('.home-numbers')).toContainText('1');
  await expect(panel.locator('.notice.warning')).toContainText('Bestehende Filterregeln prüfen');
  await expect(panel.locator('.home-details')).not.toHaveAttribute('open', '');
  await panel.getByRole('tab', { name: 'Änderungen', exact: true }).click();
  await expect(panel.locator('.empty-changes')).toContainText('Keine Änderungen vorgemerkt');
  await expect(panel.locator('[data-apply]')).toHaveCount(0);
  await panel.locator('.empty-changes [data-nav="devices"]').click();
  await expect(panel.getByRole('tab', { name: 'Geräte', exact: true })).toHaveAttribute('aria-selected', 'true');
  await panel.locator('[data-group="entities"]').click();
  await panel.locator('[data-entity-toggle]').first().click();
  await panel.getByRole('tab', { name: 'Änderungen', exact: true }).click();
  await expect(panel.locator('.change-row')).toHaveCount(1);
  await expect(panel.locator('[data-apply]')).toBeDisabled();
});
