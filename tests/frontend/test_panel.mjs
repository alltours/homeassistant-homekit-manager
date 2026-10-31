import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
class FakeHTMLElement { attachShadow() { return this.shadowRoot = { innerHTML: '', querySelector: () => null, querySelectorAll: () => [] }; } }
const registry = new Map();
vm.runInNewContext(fs.readFileSync(new URL('../../custom_components/homekit_manager/www/homekit-manager.js', import.meta.url), 'utf8'), { HTMLElement: FakeHTMLElement, customElements: { define: (key, value) => registry.set(key, value), get: key => registry.get(key) }, console, navigator: {}, window: {}, queueMicrotask });
const Panel = registry.get('homekit-manager-panel');
const panel = new Panel();
assert.match(panel.shadowRoot.innerHTML, /HomeKit Manager/);
let calls = 0;
panel.hass = { callWS: async () => { calls++; throw new Error('Transport offline'); } };
await new Promise(resolve => setTimeout(resolve, 0));
assert.equal(calls, 1, 'dependent reads must stop after failed inventory transport');
assert.match(panel.shadowRoot.innerHTML, /Transport offline/);
panel.entities = [
  { entity_id: 'light.kitchen', name: 'Kitchen', device_id: 'ceiling', device_registry_status: 'main', registry_entry_present: true, state_present: true, device_name: 'Ceiling light', area_id: 'kitchen', area_name: 'Kitchen area', domain: 'light', integration_domain: 'demo', available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true } },
  { entity_id: 'sensor.temperature', name: 'Temperature', device_id: 'meter', device_registry_status: 'main', registry_entry_present: true, state_present: true, device_name: 'Meter', area_id: 'hall', area_name: 'Hall', domain: 'sensor', device_class: 'temperature', integration_domain: 'sensor_test', available: false, compatibility: { status: 'supported' }, homekit: { configured_by_filter: false } },
];
panel.bridge = { entry_id: 'bridge-one', title: 'Test Bridge', source: 'user', state: 'loaded' };
panel.bridges = [panel.bridge];
panel.query = 'kitchen area'; assert.deepEqual(panel.filtered.map(item => item.entity_id), ['light.kitchen']);
panel.query = ''; panel.filters.integration = 'demo'; assert.equal(panel.filtered.length, 1); panel.filters.integration = '';
panel.filters.device = 'Meter'; assert.equal(panel.filtered[0].entity_id, 'sensor.temperature'); panel.filters.device = '';
panel.entities[1].availability_status = 'unknown'; panel.filters.availability = 'unknown';
assert.equal(panel.filtered[0].entity_id, 'sensor.temperature'); panel.filters.availability = '';
assert.equal(panel.statusLabel('no_state'), 'Ohne aktuellen State');
panel.setDraft('light.kitchen', 'excluded');
assert.equal(panel.desiredDocument().bridges['bridge-one'].entities['light.kitchen'], 'exclude');
panel.setDraft('light.kitchen', 'included'); assert.equal(panel.draft.size, 0);
panel.setDraft('sensor.temperature', 'included'); assert.equal(panel.desiredDocument().bridges['bridge-one'].entities['sensor.temperature'], 'include');
const positivePanel = new Panel();
positivePanel.bridge = { entry_id: 'positive', filter: { include_entities: ['light.keep'] } };
assert.equal(positivePanel.activePositiveList(), true);
assert.equal(positivePanel.desiredDocument().bridges.positive.policy, 'positive_list');
assert.equal(positivePanel.desiredDocument().bridges.positive.entities['light.keep'], 'include');
positivePanel.draft.set('light.keep', 'excluded');
assert.deepEqual(Object.keys(positivePanel.desiredDocument().bridges.positive.entities), []);
positivePanel.bridge.filter = { include_domains: ['light'] };
assert.equal(positivePanel.activePositiveList(), false);
positivePanel.entities = [
  { entity_id: 'light.keep', homekit: { configured_by_filter: true, registry_eligible: true } },
  { entity_id: 'input_boolean.legacy_exclude', homekit: { configured_by_filter: true, registry_eligible: true } },
];
positivePanel.draft.clear();
positivePanel.yamlStatus = { document: { bridges: { positive: { policy: 'explicit_overrides', entities: { 'input_boolean.legacy_exclude': 'exclude' } } } } };
positivePanel.positiveListMigration = true;
const preservedDocument = positivePanel.desiredDocument().bridges.positive.entities;
assert.equal(preservedDocument['light.keep'], 'include', 'migration keeps the selected entity');
assert.equal(preservedDocument['input_boolean.legacy_exclude'], 'exclude', 'migration must preserve stored Manager exclusions');
const flurLamps = Array.from({ length: 8 }, (_, index) => `light.flur_flur_decke_${index + 1}`);
positivePanel.entities = [
  ...flurLamps.map(entity_id => ({ entity_id, homekit: { configured_by_filter: true, registry_eligible: true } })),
  { entity_id: 'light.flur_decke', homekit: { configured_by_filter: true, registry_eligible: true } },
  { entity_id: 'input_boolean.automations_wachter', homekit: { configured_by_filter: true, registry_eligible: true } },
];
positivePanel.yamlStatus = { document: { bridges: { positive: { policy: 'explicit_overrides', entities: { 'light.flur_decke': 'exclude', 'input_boolean.automations_wachter': 'exclude' } } } } };
const flurDocument = positivePanel.desiredDocument().bridges.positive.entities;
assert.deepEqual(flurLamps.filter(id => flurDocument[id] === 'include'), flurLamps, 'the eight individual Flur lamps stay selected');
assert.equal(flurDocument['light.flur_decke'], 'exclude', 'the Flur group stays excluded');
assert.equal(flurDocument['input_boolean.automations_wachter'], 'exclude', 'the virtual helper stays excluded');
const hiddenLamp = { entity_id: 'light.flur_flur_decke_1', name: 'Flur Decke 1', hidden_by: 'user', registry_entry_present: true, state_present: true, available: true, compatibility: { status: 'supported' }, homekit: { configured_by_filter: true, registry_eligible: false }, device_registry_status: 'main' };
positivePanel.entities = [hiddenLamp];
positivePanel.display.hidden = true;
assert.equal(positivePanel.migrationBaselineStatus(hiddenLamp), 'excluded', 'hidden native matches are not migrated automatically');
assert.equal(positivePanel.individualExclusionReason(hiddenLamp), null, 'hidden entities may be individually selected');
positivePanel.setDraft(hiddenLamp.entity_id, 'included', false);
assert.equal(positivePanel.desiredDocument().bridges.positive.entities[hiddenLamp.entity_id], 'include', 'explicit hidden selection is included');
assert.match(positivePanel.entityRow(hiddenLamp), /Versteckt · explizite Auswahl nötig/);

const hiddenUnselected = { ...hiddenLamp, homekit: { configured_by_filter: false, registry_eligible: false } };
positivePanel.entities = [hiddenUnselected];
positivePanel.draft.clear();
positivePanel.setDraft(hiddenUnselected.entity_id, 'included', false);
assert.equal(positivePanel.desiredDocument().bridges.positive.entities[hiddenUnselected.entity_id], 'include', 'hidden entities excluded by the native filter remain individually selectable');
panel.overview = { configuration_alignment: { state: 'mismatch', message: 'Mismatch', differences: { count: 2, desired_not_native: [], native_not_desired: [] }, deviations: [{ id: 'a', classification: 'manager_exclude_native', entity_id: 'light.flur_decke', cause: 'Native Auswahl' }, { id: 'b', classification: 'stale_manager_decision', entity_id: 'sensor.gone', cause: 'Nicht vorhanden' }] } };
panel.view = 'changes'; panel.activationStatus = { state: 'unknown', has_operation: true };
panel.render(); assert.match(panel.shadowRoot.innerHTML, /Ergebnis unbekannt/); assert.match(panel.shadowRoot.innerHTML, /Abweichungsdetails \(2\)/); assert.match(panel.shadowRoot.innerHTML, /sensor\.gone/); assert.match(panel.shadowRoot.innerHTML, /data-apply disabled/);
panel.activationStatus = { state: 'unknown', has_operation: false };
panel.render(); assert.match(panel.shadowRoot.innerHTML, /Keine Anwendung protokolliert/);
let writes = 0; panel._hass = { callWS: async () => { writes++; } };
await panel.applyDraft(); assert.equal(writes, 0); assert.equal(panel.activationStatus.state, 'unknown');
for (const view of ['home', 'devices', 'changes', 'settings']) { panel.view = view; panel.render(); assert.match(panel.shadowRoot.innerHTML, /Hauptbereiche/); }
for (const section of ['general', 'configuration', 'diagnostics', 'rules', 'history', 'performance']) { panel.settingsView = section; panel.view = 'settings'; panel.render(); assert.match(panel.shadowRoot.innerHTML, /Einstellungsbereiche/); }
const before = panel.renderCount; panel.hass = { callWS: async () => ({}) }; assert.equal(panel.renderCount, before, 'unrelated hass setters do not rebuild the UI');
assert.equal(panel.escape('<script>'), '&lt;script&gt;');
let resolveFirst, updateReads = 0;
const context = [{ bridges: [] }, { findings: [] }, { entries: [] }, {}, {}, {}, {}, {}, {}];
panel._hass = { callWS: async () => {
  updateReads++;
  return updateReads === 1 ? new Promise(resolve => { resolveFirst = resolve; }) : { entities: [], overview: { refresh_count: 2 }, context };
} };
const first = panel.refresh(false);
panel.onInventoryUpdated({ data: { revision: 2 } });
resolveFirst({ entities: [], overview: { refresh_count: 1 }, context });
await first;
await new Promise(resolve => setTimeout(resolve, 0));
assert.equal(updateReads, 2, 'an event arriving during a read must be fetched after the stale response');
assert.equal(panel.overview.refresh_count, 2);
console.log('frontend panel behavior: ok');
