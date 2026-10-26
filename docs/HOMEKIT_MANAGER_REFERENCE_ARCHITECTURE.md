# HomeKit Manager – Referenzarchitektur

## Status

Stand 26.10.2026. Diese Architektur beschreibt den lokal implementierten, weiterhin
read-only abgesicherten Stand. Sie ist keine produktive Abnahme.

## Leitlinien

Die Integration folgt den Home-Assistant-Mustern für Custom Integrations:

- `manifest.json` aktiviert `config_flow`.
- `config_flow.py` verwendet `ConfigFlow(..., domain=DOMAIN)`.
- `__init__.py` besitzt `async_setup`, `async_setup_entry` und `async_unload_entry`.
- Registry-Zugriffe verwenden `entity_registry`, `device_registry` und `area_registry`.
- Das Panel wird über `panel_custom.async_register_panel()` und einen statischen Modulpfad
  registriert.
- WebSocket-Befehle sind mit `require_admin`, Schema-Validierung und konsistenten Fehlern
  geschützt.

## Schichten

1. **HA-Adapter:** Integration-Lifecycle, Registries, States, Config Entries und WebSocket.
2. **Read Model:** `inventory.py`, `homekit_reader.py`, `coordinator.py`.
3. **Pure Domain Logic:** `filtering.py`, `compatibility.py`, `change_planner.py`,
   `reconcile.py`, `fingerprint.py`.
4. **Desired-State Storage:** `yaml_store.py`, `draft.py`, `exporter.py`.
5. **UI:** `panel.py` und `www/homekit-manager.js`.
6. **Safety Boundary:** `homekit_writer.py`; `async_apply()` verweigert weiterhin jede
   tatsächliche HomeKit-Anwendung.

## Datenfluss

`Home Assistant Registries/States → Coordinator → Inventory + HomeKit Reader → WebSocket
→ native Custom Panel`.

Entwürfe werden separat als `homekit_manager.yaml` gespeichert. Diese Datei ist ein
Desired-State-Dokument und enthält weder Pairing-Daten noch HomeKit-Config-Entry-Daten.

## Referenzen

- Home Assistant Core 2026.10.4: `ConfigFlow`, HomeKit-Filter und Config-Entry-Lifecycle.
- Offizielle Custom-Panel-Architektur: `panel_custom.async_register_panel()`.
- Home Assistant Config-Flow-Dokumentation: `ConfigFlow(..., domain=DOMAIN)` und
  standardisierte Entry-Migration.

Maßgebliche Quellen:

- [Home Assistant Core 2026.10.4 HomeKit Config Flow](https://raw.githubusercontent.com/home-assistant/core/2026.10.4/homeassistant/components/homekit/config_flow.py)
- [Home Assistant Core 2026.10.4 HomeKit Setup](https://raw.githubusercontent.com/home-assistant/core/2026.10.4/homeassistant/components/homekit/__init__.py)
- [Offizielle Custom-Panel-Dokumentation](https://developers.home-assistant.io/docs/frontend/custom-ui/custom-panel/)
- [Offizielle Config-Flow-Dokumentation](https://developers.home-assistant.io/docs/config_entries_config_flow_handler/)
- [Home Assistant Integration Blueprint](https://github.com/roquerodrigo/ha-integration-blueprint)
  (MIT; aktueller `main`-Stand am 26.10.2026)
- [Home Assistant example-custom-config](https://github.com/home-assistant/example-custom-config)
  (Apache-2.0; aktueller `master`-Stand am 26.10.2026)

Drittanbieter-Code wurde nicht in die Laufzeit übernommen.

