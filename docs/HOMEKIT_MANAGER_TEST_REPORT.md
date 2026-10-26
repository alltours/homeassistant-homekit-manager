# HomeKit Manager – Testbericht

Stand 26.10.2026, lokaler Branch `feature/homekit-manager-0.9.9`.

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

- Unit- und HA-Integrationstests: **42 bestanden, 0 fehlgeschlagen, 0 übersprungen**.
- Frontend-Verhaltenstest: **bestanden** (`node tests/frontend/test_panel.mjs`).
- Browser-Fixture: **bestanden** mit `tests/frontend/browser_fixture.html`.
- Frische Live-Browserprüfung: **bestanden**. Das Panel, die Entitätenansicht und die
  Konfigurationsansicht wurden gegen die laufende Home-Assistant-Instanz geladen; das
  Inventar wurde angezeigt und die Browser-Logprüfung lieferte keine Warnungen oder Fehler.
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

## Nicht ausgeführt oder noch nicht abgenommen

- keine produktive Live-Abnahme
- keine vollständige End-to-End-Abnahme jedes einzelnen UI-Workflows
- kein produktiver HACS-Update der lokalen 0.9.9-Entwicklung
- kein Test einer HomeKit-Optionsänderung
- kein Pairing-, Reload- oder Bridge-Test
- keine realen 2.500-/5.000-Entitäten-Lasttests
- keine vollständige mobile- oder Screenreader-Abnahme

Diese Punkte gelten nicht als bestanden.

Die synthetische Performance-Prüfung für 2.500 und 5.000 Entitäten wurde ausgeführt und
bestanden. Sie prüft die deterministische Metrikberechnung, Seitengrößenempfehlung,
Unavailable-Zählung und Virtualisierungsgrenze; sie ersetzt keinen Lasttest mit einer
laufenden Home-Assistant-Instanz.

