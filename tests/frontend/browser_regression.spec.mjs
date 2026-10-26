import { test, expect } from "@playwright/test";

const viewports = [
  ["iphone-390", 390, 844],
  ["iphone-430", 430, 932],
  ["tablet-768", 768, 1024],
  ["desktop-1440", 1440, 900],
];

for (const [name, width, height] of viewports) {
  for (const colorScheme of ["light", "dark"]) {
    test(`${name} ${colorScheme} renders and preserves draft interactions`, async ({ page }) => {
      await page.setViewportSize({ width, height });
      await page.emulateMedia({ colorScheme });
      const errors = [];
      page.on("pageerror", (error) => errors.push(error.message));
      await page.goto("/tests/frontend/browser_fixture.html");
      const panel = page.locator("homekit-manager-panel");
      await expect(panel).toBeVisible();
      await expect(panel.locator("text=Eine klare Übersicht deiner Konfiguration")).toBeVisible();
      await panel.locator("text=Geräte verwalten").click();
      await expect(panel.locator("text=Was soll in HomeKit erscheinen?")).toBeVisible();
      await panel.locator("[data-expand]").first().click();
      await expect(panel.locator("text=Kitchen light")).toBeVisible();
      const input = panel.locator("[data-query]");
      await input.fill("Kitchen");
      await expect(input).toHaveValue("Kitchen");
      await panel.locator("[data-entity-toggle]").first().click();
      await panel.locator("[data-nav=settings]").click();
      await expect(panel.getByRole("heading", { name: "Regeln" })).toBeVisible();
      await panel.locator("[data-nav=changes]").click();
      await expect(panel.getByRole("heading", { name: "Nur deine geplanten Änderungen" })).toBeVisible();
      const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth);
      expect(overflow).toBe(false);
      expect(errors).toEqual([]);
      await page.screenshot({ path: `test-results/${name}-${colorScheme}.png`, fullPage: true });
    });
  }
}

test("large inventories render within the browser budget", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/tests/frontend/browser_fixture.html");
  await expect(page.locator("homekit-manager-panel")).toBeVisible();
  const results = await page.evaluate(() => {
    const panel = document.querySelector("homekit-manager-panel");
    panel.view = "devices";
    panel.groupMode = "entities";
    return [1000, 2500, 5000].map((count) => {
      panel.entities = Array.from({ length: count }, (_, index) => ({
        entity_id: `light.synthetic_${index}`,
        name: `Light ${index}`,
        area_name: `Area ${index % 20}`,
        device_name: `Device ${index % 100}`,
        domain: "light",
        compatibility: { status: "supported" },
        homekit: { current_status: index % 2 ? "excluded" : "included" },
      }));
      const start = performance.now();
      panel.render();
      return { count, render_ms: Number((performance.now() - start).toFixed(2)), html_length: panel.shadowRoot.innerHTML.length };
    });
  });
  for (const result of results) expect(result.render_ms).toBeLessThan(1000);
  expect(results.map((result) => result.count)).toEqual([1000, 2500, 5000]);
  console.log("browser performance", JSON.stringify(results));
});
