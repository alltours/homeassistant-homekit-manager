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
      await expect(panel.locator("text=Konfigurationsmethode")).toBeVisible();
      await expect(panel.locator("text=Fixture Bridge")).toBeVisible();
      await panel.locator('[data-mode="yaml"]').click();
      await expect(panel.locator('[data-mode="yaml"] small')).toHaveText("Vorgemerkt");
      await panel.locator("[data-bridge-expand]").click();
      await expect(panel.getByText("Modus: bridge", { exact: true })).toBeVisible();
      await panel.locator("[data-bridge-expand]").click();
      await expect(panel.getByText("Modus: bridge", { exact: true })).not.toBeVisible();
      await panel.getByRole("tab", { name: "Geräte" }).click();
      await expect(panel.locator("text=Was soll in HomeKit erscheinen?")).toBeVisible();
      const input = panel.locator("[data-query]");
      await input.fill("Kitchen");
      await expect(input).toHaveValue("Kitchen");
      await panel.locator(".filters summary").click();
      await panel.locator("[data-filter=status]").selectOption("included");
      await panel.locator("[data-reset-filters]").click();
      await panel.locator("[data-group=entities]").click();
      await panel.locator("[data-entity-toggle]").first().click();
      await panel.getByRole("tab", { name: "Änderungen" }).click();
      await expect(panel.locator("text=Nur geplante Änderungen")).toBeVisible();
      await expect(panel.locator("text=Entwurf speichern")).toBeVisible();
      await panel.locator("[data-action-menu]").click();
      await panel.locator("[data-preview]").click();
      await panel.locator("[data-save]").click();
      await expect(panel.locator("text=Entwurf gespeichert")).toBeVisible();
      await panel.locator("[data-load]").click();
      await expect(panel.locator("text=Entwurf gespeichert")).toBeVisible();
      await panel.getByRole("tab", { name: "Einstellungen" }).click();
      await expect(panel.locator("[data-settings-view=rules]")).toBeVisible();
      await panel.locator("[data-settings-view=rules]").click();
      await expect(panel.getByRole("heading", { name: "Regeln" })).toBeVisible();
      await panel.locator("[data-rules-preview]").click();
      await panel.getByRole("tab", { name: "Einstellungen" }).click();
      await panel.locator("[data-settings-view=history]").click();
      await expect(panel.getByRole("heading", { name: "Historie" })).toBeVisible();
      await panel.getByRole("tab", { name: "Einstellungen" }).click();
      await panel.locator("[data-settings-view=performance]").click();
      await panel.locator("[data-performance]").click();
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

test("activation interruption remains explicitly unknown and is not retried", async ({ page }) => {
  await page.goto("/tests/frontend/browser_fixture.html?activation-error");
  const panel = page.locator("homekit-manager-panel");
  await expect(panel).toBeVisible();
  await panel.getByRole("tab", { name: "Geräte" }).click();
  await panel.locator("[data-group=entities]").click();
  await panel.locator("[data-entity-toggle]").first().click();
  await panel.getByRole("tab", { name: "Änderungen" }).click();
  await page.evaluate(() => { window.confirm = () => true; });
  await panel.locator("[data-apply]").click();
  await expect(panel.locator("text=Aktivierungsstatus: unknown")).toBeVisible();
  await expect(panel.locator("text=keine automatische Wiederholung")).toBeVisible();
  await expect(panel.locator("[role=alert]")).not.toBeVisible();
});

test("sticky change actions remain visible inside a Home Assistant-like scroll container", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/tests/frontend/browser_fixture.html");
  const panel = page.locator("homekit-manager-panel");
  await expect(panel).toBeVisible();
  await panel.getByRole("tab", { name: "Änderungen" }).click();
  await page.evaluate(() => {
    const element = document.querySelector("homekit-manager-panel");
    const wrapper = document.createElement("div");
    wrapper.id = "ha-scroll-container";
    wrapper.style.height = "320px";
    wrapper.style.overflow = "auto";
    element.replaceWith(wrapper);
    wrapper.append(element);
  });
  const footer = panel.locator(".sticky-actions");
  const wrapper = page.locator("#ha-scroll-container");
  await wrapper.evaluate((element) => { element.scrollTop = element.scrollHeight; });
  const geometry = await page.evaluate(() => {
    const footer = document.querySelector("homekit-manager-panel").shadowRoot.querySelector(".sticky-actions").getBoundingClientRect();
    const wrapper = document.querySelector("#ha-scroll-container").getBoundingClientRect();
    return { footerBottom: footer.bottom, wrapperBottom: wrapper.bottom, footerHeight: footer.height };
  });
  expect(geometry.footerHeight).toBeGreaterThan(0);
  expect(geometry.footerBottom).toBeLessThanOrEqual(geometry.wrapperBottom + 1);
});

test("storage cards distinguish verified source from blocked migration", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("/tests/frontend/browser_fixture.html");
  const panel = page.locator("homekit-manager-panel");
  await expect(panel.locator(".storage-card.active small")).toHaveText("Aktiv");
  await panel.locator('[data-mode="yaml"]').click();
  await expect(panel.locator('[data-mode="yaml"] small')).toHaveText("Vorgemerkt");
  await panel.locator('[data-migration-target]').selectOption("yaml");
  await expect(panel.locator(".migration-panel .warning")).toContainText("gesperrt");
  await expect(panel.locator('[data-migration-start]')).toBeDisabled();
});
