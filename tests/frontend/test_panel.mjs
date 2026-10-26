import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

class FakeHTMLElement { attachShadow() { const root = { innerHTML: "", querySelector: () => null, querySelectorAll: () => [], addEventListener: () => {} }; this.shadowRoot = root; return root; } }
const registry = new Map();
const source = fs.readFileSync(new URL("../../custom_components/homekit_manager/www/homekit-manager.js", import.meta.url), "utf8");
vm.runInNewContext(source, { HTMLElement: FakeHTMLElement, customElements: { define: (name, value) => registry.set(name, value), get: (name) => registry.get(name) }, navigator: {}, window: {}, console });
const Panel = registry.get("homekit-manager-panel");
assert.ok(Panel);
const panel = new Panel();
assert.match(panel.shadowRoot.innerHTML, /HomeKit Manager/);
assert.match(panel.shadowRoot.innerHTML, /HomeKit/);
assert.match(panel.shadowRoot.innerHTML, /Konfigurationsmethode/);
assert.match(panel.shadowRoot.innerHTML, /HomeKit-Bridges/);
assert.match(panel.shadowRoot.innerHTML, /Änderungsübersicht/);
assert.match(panel.shadowRoot.innerHTML, /Änderungen speichern/);

let calls = 0;
panel.hass = { callWS: async ({ type }) => { calls += 1; if (type === "homekit_manager/inventory") throw new Error("WebSocket nicht erreichbar"); throw new Error(`unexpected command: ${type}`); } };
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(calls, 8);
assert.match(panel.shadowRoot.innerHTML, /WebSocket nicht erreichbar/);

panel.entities = [
  { entity_id: "light.kitchen", device_id: "device-kitchen", name: "Kitchen", area_name: "Kitchen", device_name: "Ceiling light", domain: "light", compatibility: { status: "supported" }, homekit: { configured_by_filter: true, current_status: "included" } },
  { entity_id: "sensor.hidden", device_id: "device-hidden", name: "Hidden sensor", area_name: "Hall", device_name: "Sensor", domain: "sensor", compatibility: { status: "conditionally_supported" }, homekit: { configured_by_filter: false, current_status: "excluded" } },
];
assert.equal(panel.currentStatus(panel.entities[0]), "included");
assert.equal(panel.status(panel.entities[1]), "excluded");
panel.query = "kitchen";
assert.deepEqual(panel.filtered.map((entity) => entity.entity_id), ["light.kitchen"]);
panel.query = "";
panel.bridge = { entry_id: "bridge-1" };
panel.draft = new Map([["light.kitchen", "excluded"]]);
assert.equal(panel.status(panel.entities[0]), "planned");
assert.equal(JSON.stringify(panel.desiredDocument().bridges["bridge-1"].entities), JSON.stringify({ "light.kitchen": "exclude" }));
panel.draft.clear();
panel.toggleDevice("device-kitchen");
assert.equal(panel.draft.get("light.kitchen"), "excluded");
panel.toggleDevice("device-kitchen");
assert.equal(panel.draft.size, 0, "returning a device to its baseline removes the draft");
panel.bridges = [{ entry_id: "bridge-1", title: "Test Bridge", state: "loaded" }];
panel.dashboardExpanded = new Set(["bridge-1"]);
panel.bridge = panel.bridges[0];
panel.render();
assert.match(panel.shadowRoot.innerHTML, /data-dashboard-entity/);
assert.match(panel.shadowRoot.innerHTML, /Geräte/);
assert.match(panel.shadowRoot.innerHTML, /Gerätetypen/);
assert.match(panel.shadowRoot.innerHTML, /Zonen/);
assert.match(panel.shadowRoot.innerHTML, /@media\(max-width:700px\)/);

const before = panel.renderCount;
panel.hass = { callWS: async () => ({}) };
assert.equal(panel.renderCount, before, "irrelevant Home Assistant state updates must not rebuild the DOM");

const successful = new Panel();
let successCalls = 0;
successful.hass = { callWS: async ({ type }) => { successCalls += 1; if (type === "homekit_manager/inventory") return { entities: [], overview: {} }; if (type === "homekit_manager/bridges") return { bridges: [] }; if (type === "homekit_manager/devices") return { devices: [] }; if (type === "homekit_manager/areas") return { areas: [] }; if (type === "homekit_manager/diagnostics") return { findings: [], summary: {} }; if (type === "homekit_manager/yaml_status") return { valid: true, exists: false }; if (type === "homekit_manager/mode_status") return { active_mode: "homekit_bridge" }; throw new Error(`unexpected command: ${type}`); } };
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(successCalls, 8);
assert.doesNotMatch(successful.shadowRoot.innerHTML, /Verbindung nicht möglich/);
console.log("frontend panel behavior: ok");
