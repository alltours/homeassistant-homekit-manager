import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";

class FakeHTMLElement {
  attachShadow() {
    const root = {
      innerHTML: "",
      querySelector: () => null,
      querySelectorAll: () => [],
    };
    this.shadowRoot = root;
    return root;
  }
}

const registry = new Map();
const source = fs.readFileSync(
  new URL("../../custom_components/homekit_manager/www/homekit-manager.js", import.meta.url),
  "utf8",
);
vm.runInNewContext(source, {
  HTMLElement: FakeHTMLElement,
  customElements: { define: (name, value) => registry.set(name, value), get: (name) => registry.get(name) },
  navigator: {},
  window: {},
  console,
});

const Panel = registry.get("homekit-manager-panel");
assert.ok(Panel, "custom panel must register its web component");
const panel = new Panel();
assert.equal(typeof panel.scheduleRefresh, "function");
assert.match(panel.shadowRoot.innerHTML, /HomeKit Manager/);
assert.match(panel.shadowRoot.innerHTML, /Keine Änderungen/);

let inventoryCalls = 0;
panel.hass = {
  states: {},
  callWS: async ({ type }) => {
    inventoryCalls += 1;
    if (type === "homekit_manager/inventory") throw new Error("WebSocket nicht erreichbar");
    throw new Error(`unexpected command: ${type}`);
  },
};
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(inventoryCalls, 1);
assert.match(panel.shadowRoot.innerHTML, /Initialisierung fehlgeschlagen/);
assert.match(panel.shadowRoot.innerHTML, /WebSocket nicht erreichbar/);

panel.entities = [
  {
    entity_id: "light.kitchen",
    name: "Kitchen",
    area_name: "Kitchen",
    domain: "light",
    compatibility: { status: "supported" },
    homekit: { configured_by_filter: true },
  },
  {
    entity_id: "sensor.hidden",
    name: "Hidden sensor",
    area_name: "Hall",
    domain: "sensor",
    compatibility: { status: "conditionally_supported" },
    homekit: { configured_by_filter: false },
  },
];
panel.filters = { area_name: "Kitchen", device_name: "", integration_domain: "", domain: "", device_class: "", entity_category: "", compatibility: "", status: "" };
panel.query = "kitchen";
assert.deepEqual(panel.filtered.map((entity) => entity.entity_id), ["light.kitchen"]);
panel.query = "";
panel.filters.area_name = "";
panel.sort = { key: "name", direction: 1 };
assert.deepEqual(panel.filtered.map((entity) => entity.entity_id), ["sensor.hidden", "light.kitchen"]);

panel.bridge = { entry_id: "bridge-1" };
panel.draft = new Map([["light.kitchen", "exclude"]]);
assert.equal(panel.status(panel.entities[0]), "exclude");
panel.setDraft("sensor.hidden", "include");
assert.equal(panel.status(panel.entities[1]), "include");
assert.deepEqual(JSON.parse(JSON.stringify(panel.desiredDocument())), {
  schema_version: 1,
  bridges: { "bridge-1": { policy: "explicit_overrides", entities: { "light.kitchen": "exclude", "sensor.hidden": "include" } } },
});
panel._hass = {
  callWS: async (message) => {
    if (message.type === "homekit_manager/validate_draft") {
      return { warnings: [], document: panel.desiredDocument() };
    }
    return { summary: { blocked: false }, changes: [], fingerprint: panel.fingerprint };
  },
};
panel.fingerprint = "fingerprint";
await panel.previewServer();
assert.equal(panel.conflict, false);
assert.equal(panel.escape("<script>&\""), "&lt;script&gt;&amp;&quot;");

const successful = new Panel();
let successCalls = 0;
successful.hass = {
  states: { "light.kitchen": {} },
  callWS: async ({ type }) => {
    successCalls += 1;
    if (type === "homekit_manager/inventory") return { entities: [], overview: { fingerprint: "ok" } };
    if (type === "homekit_manager/bridges") return { bridges: [] };
    if (type === "homekit_manager/yaml_status") return { valid: true, exists: false };
    if (type === "homekit_manager/devices") return { devices: [] };
    if (type === "homekit_manager/areas") return { areas: [] };
    if (type === "homekit_manager/diagnostics") return { findings: [], summary: {} };
    if (type === "homekit_manager/device_preview") return { simulation: true, title: "Kitchen", service_type: "Lightbulb", applied: false };
    if (type === "homekit_manager/mode_status") return { active_mode: "homekit_bridge", desired_mode: "homekit_bridge", transition: "stable", matrix: {} };
    throw new Error(`unexpected command: ${type}`);
  },
};
successful.panel = { config: {} };
successful.narrow = true;
await new Promise((resolve) => setTimeout(resolve, 0));
assert.equal(successCalls, 7);
assert.doesNotMatch(successful.shadowRoot.innerHTML, /Initialisierung fehlgeschlagen/);
assert.match(successful.shadowRoot.innerHTML, /HomeKit Manager/);

console.log("frontend panel behavior: ok");
