# HomeKit Manager – Testbericht

Stand 26.10.2026.

## Ausgeführt

Isolierte Laufzeit:

- Python 3.14.9 portable
- Home Assistant Core 2026.10.4
- Home Assistant Frontend 20260930.5
- pytest-homeassistant-custom-component 0.13.375

Befehle:

```text
.venv-ha-2026.10.4/bin/python -m unittest -v tests/test_homekit_manager.py
.venv-ha-2026.10.4/bin/python -m pytest -c tests/integration/pytest.ini -vv tests/integration/test_config_flow.py
node tests/frontend/test_panel.mjs
```

Ergebnisse:

- Unit-Tests: **20 bestanden, 0 fehlgeschlagen, 0 übersprungen**.
- HA-Integrationstests: **8 bestanden, 0 fehlgeschlagen, 0 übersprungen**.
- Frontend-Verhaltenstest: **bestanden** (`node tests/frontend/test_panel.mjs`).
- Isolierter Browser-Smoke-Test: **bestanden** mit `tests/frontend/browser_fixture.html`.
  Im Browser wurden Panel-Rendering, Suche, Entitätsauswahl und eine konkrete serverseitige
  Vorschauänderung verifiziert. Die Fixture verwendet ausschließlich simulierte Daten.
- Gemeinsame Python-Coverage der Unit- und HA-Integrationstests: **83 %**. Sie ist
  diagnostisch, kein künstlicher Abnahmewert; die nicht ausgeführten Pfade sind überwiegend
  Fehlerzweige und die bewusst deaktivierte produktive Anwendung.
- Discovery/Registration bestanden.
- Config Flow und Entry-Erstellung bestanden.
- Entry-Setup und Entry-Unload bestanden.
- WebSocket-Registrierung im echten HA-Command-Registry bestanden.
- Singleton-Schutz gegen doppelte Config Entries bestanden.
- Panel-Webcomponent-Registrierung, Suche/Filter, Desired-State-Erzeugung und Escaping
  im Node-Verhaltenstest bestanden.
- State-only-Entitäten werden als Registry-unbekannte Fallback-Datensätze sichtbar.
- Writer-Sperre bestanden.
- Rekursive Geheimnis-Redaktion bestanden.
- JavaScript-Syntaxprüfung, Python-Kompilierung und Manifest-JSON-Prüfung bestanden.

## Nicht ausgeführt

- keine produktive Live-Abnahme
- kein Browser-Test gegen eine laufende echte HA-Frontend-Instanz
- kein Browser-Test in einer laufenden produktiven Home-Assistant-Frontend-Instanz
- kein Test einer HomeKit-Optionsänderung
- kein Pairing-, Reload- oder Bridge-Test

Diese Punkte gelten nicht als bestanden.

