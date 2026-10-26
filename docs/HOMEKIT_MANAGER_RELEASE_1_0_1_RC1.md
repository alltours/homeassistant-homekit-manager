# HomeKit Manager 1.0.1-rc1

## Releaseumfang

Der Release-Kandidat enthält exakt die 22 Integrationsdateien unter `custom_components/homekit_manager/`. Gegenüber `1.0.0-rc1` wurden ausschließlich folgende Dateien geändert:

- `manifest.json` – Integrationsversion auf `1.0.1` erhöht.
- `www/homekit-manager.js` – sichtbare Initialisierungs-, Lade- und Fehlerzustände, HA-Panel-Property-Setter, robuste Registrierung und Theme-Fallbacks.
- `tests/frontend/test_panel.mjs` – Regressionen für initiales Rendering, WebSocket-Fehler, erfolgreiche Initialisierung und Property-Reihenfolge.
- `tests/frontend/browser_fixture.html` – valide Initialisierung nach `DOMContentLoaded`.

## Tests

- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests und Unit-Tests: bestanden.
- Browser-Fixture: lokal strukturell korrigiert; ein Safari-Lauf war in dieser Entwicklungsumgebung nicht reproduzierbar automatisierbar.
- Produktive Installation: nicht verändert.

## Sicherheitsgrenzen

Kein Home-Assistant-Neustart, kein HomeKit-Reload, keine Änderung des bestehenden HomeKit-Config-Entry, keine Pairing-Manipulation und keine Aktivierung des Schreibpfads.

## Installation

Die Installation darf erst nach gesonderter Freigabe erfolgen. Vorher sind Archiv-Prüfsumme, vollständige Dateiliste und Zielpfad zu prüfen. Nach der Übertragung ist ein ausdrücklich freigegebener Core-Neustart erforderlich, bevor die Live-Abnahme wiederholt wird.

