import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
class FakeHTMLElement { attachShadow() { return this.shadowRoot = { innerHTML: '', querySelector: () => null, querySelectorAll: () => [] }; } }
const registry = new Map();
vm.runInNewContext(fs.readFileSync(new URL('../../custom_components/homekit_manager/www/homekit-manager.js', import.meta.url), 'utf8'), { HTMLElement: FakeHTMLElement, customElements: { define: (key, value) => registry.set(key, value), get: key => registry.get(key) }, console, navigator: {}, window: {} });
const Panel = registry.get('homekit-manager-panel');
const panel = new Panel();
assert.match(panel.shadowRoot.innerHTML, /HomeKit Manager/);
let calls = 0;
panel.hass = { callWS: async () => { calls++; throw new Error('Transport offline'); } };
await new Promise(resolve => setTimeout(resolve, 0));
assert.equal(calls, 1, 'dependent reads must stop after failed inventory transport');
assert.match(panel.shadowRoot.innerHTML, /Transport offline/);
panel.entities = [
  { entity_id: 'light.kitchen', name: 'Kitchen', device_id: 'ceiling', device_name: 'Ceiling light', area_id: 'kitchen', area_name: 'Kitchen area', domain: 'light', integration_domain: 'demo', available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true } },
  { entity_id: 'sensor.temperature', name: 'Temperature', device_id: 'meter', device_name: 'Meter', area_id: 'hall', area_name: 'Hall', domain: 'sensor', integration_domain: 'sensor_test', available: false, compatibility: { status: 'conditionally_supported' }, homekit: { configured_by_filter: false } },
];
panel.bridge = { entry_id: 'bridge-one', title: 'Test Bridge', source: 'user', state: 'loaded' };
panel.bridges = [panel.bridge];
panel.query = 'kitchen area'; assert.deepEqual(panel.filtered.map(item => item.entity_id), ['light.kitchen']);
panel.query = ''; panel.filters.integration = 'demo'; assert.equal(panel.filtered.length, 1); panel.filters.integration = '';
panel.filters.device = 'Meter'; assert.equal(panel.filtered[0].entity_id, 'sensor.temperature'); panel.filters.device = '';
panel.setDraft('light.kitchen', 'excluded');
assert.equal(panel.desiredDocument().bridges['bridge-one'].entities['light.kitchen'], 'exclude');
panel.setDraft('light.kitchen', 'included'); assert.equal(panel.draft.size, 0);
panel.setDraft('sensor.temperature', 'included'); assert.equal(panel.desiredDocument().bridges['bridge-one'].entities['sensor.temperature'], 'include');
panel.view = 'changes'; panel.activationStatus = { state: 'unknown', has_operation: true };
panel.render(); assert.match(panel.shadowRoot.innerHTML, /Ergebnis unbekannt/); assert.match(panel.shadowRoot.innerHTML, /data-apply disabled/);
let writes = 0; panel._hass = { callWS: async () => { writes++; } };
await panel.applyDraft(); assert.equal(writes, 0); assert.equal(panel.activationStatus.state, 'unknown');
for (const view of ['home', 'devices', 'changes', 'settings']) { panel.view = view; panel.render(); assert.match(panel.shadowRoot.innerHTML, /Hauptbereiche/); }
for (const section of ['general', 'configuration', 'diagnostics', 'rules', 'history', 'performance']) { panel.settingsView = section; panel.view = 'settings'; panel.render(); assert.match(panel.shadowRoot.innerHTML, /Einstellungsbereiche/); }
const before = panel.renderCount; panel.hass = { callWS: async () => ({}) }; assert.equal(panel.renderCount, before, 'unrelated hass setters do not rebuild the UI');
assert.equal(panel.escape('<script>'), '&lt;script&gt;');
console.log('frontend panel behavior: ok');
