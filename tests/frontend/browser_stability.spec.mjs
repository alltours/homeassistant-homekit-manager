import { test, expect } from "@playwright/test";

test.setTimeout(310000);

test("panel remains stable during a five minute observation", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/tests/frontend/browser_fixture.html");
  const panel = page.locator("homekit-manager-panel");
  await expect(panel).toBeVisible();
  const initial = await panel.evaluate((element) => element.renderCount);
  await page.evaluate(async () => {
    const element = document.querySelector("homekit-manager-panel");
    for (let index = 0; index < 300; index += 1) {
      element.hass = { states: {}, callWS: element.hass.callWS };
      await new Promise((resolve) => setTimeout(resolve, 1000));
    }
  });
  const final = await panel.evaluate((element) => element.renderCount);
  expect(final).toBe(initial);
});
