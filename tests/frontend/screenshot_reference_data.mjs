// Synthetic, anonymized reference data. Counts visible in the supplied photos
// guide layout coverage; device identities and hidden data are NOT reconstructed.
export function screenshotReferenceData() {
  const groups = [
    [null, 581, 248, 168, 378, 72],
    ['Zentrale', 47, 7, 10, 33, 16],
    ['Küche', 53, 6, 13, 53, 2],
    ['Flur', 212, 20, 57, 109, 17],
    ['Flur OG', 16, 2, 4, 16, 2],
    ['Garage', 49, 39, 2, 14, 3],
    ['Katzengefängnis', 36, 16, 15, 2, 3],
    ['Heizzentrale', 9, 1, 2, 7, 1],
    ['Gästezimmer', 87, 0, 32, 65, 3],
    ['Büro', 25, 2, 3, 19, 3],
    ['Zusätzlicher Testbereich', 57, 27, 0, 0, 7],
  ];
  const entities = []; let deviceOffset = 0;
  for (const [area, count, included, compatible, unavailable, devices] of groups) {
    for (let index = 0; index < count; index++) {
      const ordinal = entities.length;
      const noDevice = area === null && index < 190;
      const device = noDevice ? null : `synthetic-device-${deviceOffset + ((index - (area === null ? 190 : 0)) % devices)}`;
      entities.push({
        entity_id: `light.reference_${ordinal}`, name: `${area || 'Ohne Bereich'} – Entität ${index + 1}`,
        domain: 'light', device_id: device, device_name: device && `Referenzgerät ${device.split('-').at(-1)}`,
        area_id: area && `reference-area-${deviceOffset}`, area_name: area, integration_domain: 'reference_fixture',
        available: index >= unavailable,
        compatibility: {status: index < compatible ? 'supported' : 'conditionally_supported', expected_type: 'Lightbulb', publication_verified: false},
        homekit: {configured_by_filter: index < included, current_status: index < included ? 'included' : 'excluded', published: 'unknown'},
      });
    }
    deviceOffset += devices;
  }
  const presenceId = 'input_boolean.anwesenheit_einer_person_mit_besonders_langem_namen';
  Object.assign(entities[0], {entity_id: presenceId, name: 'Anwesenheit – Person mit besonders langem Namen', domain: 'input_boolean', compatibility: {status: 'supported', expected_type: 'Switch', publication_verified: false}});
  return {entities, presenceId, overview: {
    total_entities: entities.length,
    device_count: new Set(entities.map(entity => entity.device_id).filter(Boolean)).size,
    configured_entities: entities.filter(entity => entity.homekit.configured_by_filter).length,
    unavailable_entities: entities.filter(entity => !entity.available).length,
    compatible_entities: entities.filter(entity => entity.compatibility.status === 'supported').length,
    selected_bridge_id: 'fixture-bridge', accessories: 0,
    integration_version: '0.10.4', core_version: '2026.10.4', snapshot_stale: false,
    fingerprint: 'synthetic-photo-reference', write_policy: {enabled: false},
  }};
}
