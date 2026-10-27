# HomeKit Manager 0.10.0 — Arbeitsstand und Release-Gates

Stand: 2026-10-27. Branch `feature/homekit-manager-0.10.0`, aus `origin/main` / `v0.9.24` bei `21dc5b72144aa934e8df7a66bcc58625f5c992be` erstellt. **NO-GO; kein 0.10.0-Release.** Diese Datei ist ein Entwicklungs-Checkpoint, keine Installationsfreigabe.

## Verifizierte Ausgangsbasis

- Annotierter Tag `v0.9.24` zeigt auf denselben Commit wie `origin/main`. GitHub-Release wurde am 2026-10-27 um 20:34:18 UTC veröffentlicht.
- Das veröffentlichte `homekit-manager-0.9.24.zip` hat SHA-256 `88954598b4b61b1669065c40bc19f16afb97e7bd1c6f975afebc783496c23a5b`. GitHub-Checksum-Datei und ein frischer lokaler Build stimmen bytegenau überein.
- Ausgangstests mit Python 3.14.9 / Home Assistant Core 2026.10.4: 152 bestanden, 2 übersprungen. Baseline-Actions [CI](https://github.com/alltours/homeassistant-homekit-manager/actions/runs/40578723456) und [HACS](https://github.com/alltours/homeassistant-homekit-manager/actions/runs/40579148888) meldeten Erfolg.
- Ein lesender Home-Assistant-Kontext bestätigte lediglich, dass die Entität „Vorgartenbeleuchtung“ als `light` im Bereich Vorgarten aktuell `on` war. Der verfügbare Connector lieferte keine Sensoren, Registry-Daten, HomeKit-Config-Entries oder Core-Version. Browserzugriff war in dieser Sitzung deaktiviert. Die 1.216/375/251-Zählung, die vier Shelly-Sensoren und 129/121 sind deshalb **nicht live verifiziert**. Es wurde kein produktiver Schreib-, Reload- oder Neustart-Aufruf ausgeführt.

## Behandelte Befunde

| Schwere | Befund und Core-Vertrag | Korrektur | Nachweis |
|---|---|---|---|
| Hoch | Die Standalone-Filtervorschau behandelte `include_entities` plus Excludes wie eine reine Include-Liste. Core 2026.10.4 unterscheidet sechs Fälle; bei Entity-Include mit Domain-/Glob-Exclude bleibt die Default-Selektion der übrigen Entitäten erhalten. | `filtering.py` bildet die sechs Fälle ab. | `tests/test_filter_core_contract_0100.py`: 64 Filterkombinationen × 6 IDs × 4 Registry-Eigenschaften gegen Core `FILTER_SCHEMA`. |
| Hoch | Hidden-/Kategorie-Sperre wurde bei Domain-/Glob-Includes uneinheitlich behandelt. Core `EntityFilter.explicitly_included()` erkennt Entity-IDs **und Include-Globs**, nicht Domain-Includes. | Nach Core-Auswahl wird der HomeKit-Registry-Gate mit exakt dieser Unterscheidung angewandt. | Derselbe Core-Vertragstest. |
| Hoch | Eine Entity-Listenänderung konnte bei dünnem Inventar die Standardauswahl für unbekannte und künftige Entitäten kippen, ohne dass `_verify_scope()` es erkannte. | Analytische Default-Policy-Prüfung vor jedem Options-Diff; Scope-Wechsel blockiert. | `tests/test_writer_filter_boundary_0100.py`, einschließlich unbekannter zukünftiger Entität. |
| Mittel | Eine unauflösbare Gerätereferenz wurde allein deshalb „verwaist“ genannt, auch bei vorhandenem gültigem State. | Primärstatus folgt Disabled/State-Evidenz; Gerätereferenz, Registry-Eintrag und State-Präsenz sind separate Merkmale. | `tests/test_inventory_quality.py`, Browser-Regressionsfall in Chromium und WebKit. |
| Mittel | Die Status-Zeile im Geräte-Tab verwendete Gesamtzahlen, während daneben „Kennzahlen beziehen sich auf aktuelle Treffer“ stand. | Verfügbarkeitszahlen werden aus den gefilterten Treffern berechnet. | Browser-Regressionsfall mit Suche und Statuswechsel. |

## Versionierter Core-Vertrag und Capability-Stand

Referenz: installierter Home Assistant Core **2026.10.4**, besonders `homeassistant/helpers/entityfilter.py`, `homeassistant/components/homekit/__init__.py` und `config_flow.py`; öffentliche [HomeKit-Dokumentation](https://www.home-assistant.io/integrations/homekit/). Die Dokumentation beschreibt YAML-Optionen; der konkrete Core-Code ist für Apply- und Reload-Verhalten maßgeblich.

| Quelle / Struktur | Lesen | Filter-Entwurf und Vorschau | Isoliertes Apply | Produktives Apply | Grund / Grenze |
|---|---:|---:|---:|---:|---|
| Native `SOURCE_USER`, Bridge, bekannte Filterlisten | Ja | Ja | Ja, Core-Config-Entry-Tests | Nein | Coordinator erzeugt Operationsdienst ohne Writer-Autorität; HAP-/Pairing- und produktive Grant-Nachweise fehlen. |
| YAML `SOURCE_IMPORT`, `homekit: !include <Datei>`, eindeutiger Name und Port, sichere Formatierung, ausschließlich importierte Bridges | Effektive Core-Werte | Ja | Ja, Core-Import/Reload und Datei-Backup | Nein | Core `homekit.reload` lädt alle HomeKit-Entries; kein gezielter Reload bei gemischtem Bestand. |
| Direktes `homekit:` in `configuration.yaml` | Effektive Core-Werte | Teilweise | Nein | Nein | Verlustfreie Provenienz-/Write-/Recovery-Prüfung fehlt. |
| `!include_dir_*`, Packages, verschachtelte Includes, Tags/Secrets, Aliase, Symlinks, mehrdeutige Bridge | Effektive Core-Werte | Teilweise | Nein | Nein | Sichere Originaldatei-Zuordnung oder Roundtrip nicht nachgewiesen. |
| Accessory-Modus, Netzwerk-/IP-/Advertise-Felder, `entity_config`, `devices`, unbekannte Core-Felder | Source-Snapshot soweit Core liefert | Keine allgemeine Bearbeitung | Nein | Nein | Feldspezifische Schema- und Identitätsnachweise fehlen; unbekannte Felder werden nicht still verworfen. |

Die sechs von Core 2026.10.4 geprüften Filterlisten sind `include_entities`, `exclude_entities`, `include_domains`, `exclude_domains`, `include_entity_globs` und `exclude_entity_globs`. Core filtert danach beim Bridge-Start ausschließlich **vorhandene States**; Entity-Kategorie und `hidden_by` sperren außer bei expliziter Entity-ID oder Include-Glob. Ein Filtertreffer belegt weder technische Accessory-Erzeugung noch HAP-Publikation oder Apple-Home-Sichtbarkeit.

## Traceability-Auszug

| Anforderung | Core-Referenz | Implementierung | Test | Restlücke |
|---|---|---|---|---|
| Exakte Filterselektion | `entityfilter.py`, `HomeKit.async_configure_accessories` | `filtering.py` | Core-Vertragstest | HAP-Laufzeit-Publikation ungetestet. |
| Keine globale Nebenwirkung eines Entity-Diffs | Core-Fälle in `entityfilter.py` | `homekit_writer._verify_scope` | Writer-Boundary-Test | Formale Prüfung aller zukünftigen Core-Versionen fehlt; Version ist gepinnt. |
| State und Gerätereferenz getrennt | Core State-Machine / Entity-/Device-Registry | `inventory.py`, Geräte-UI | Inventory- und Browser-Test | Produktive Registry-Daten fehlen. |
| Native Options-Änderung | HomeKit-Config-Entry-Update-Listener | `native_adapter.py`, `operations.py` | Bestehende Core-Integrationstests | Echter HAP-Start/Neustart/Pairing fehlt. |
| YAML-Änderung ohne Quellenwechsel | Core YAML-Import und `homekit.reload` | `yaml_adapter.py`, `operations.py` | Bestehende Core-Integrationstests | Direkte/komplexe YAML-Strukturen und realer HAP-Lauf fehlen. |
| Fail-closed Writer | Nicht durch Core geliefert; Manager-Sicherheitsvertrag | `coordinator.py`, `operations.py` | Bestehende Negativtests | Kontrollierte spätere Produktivfreigabe fehlt. |

## Lokale Verifikation

- Python 3.14.9 / Core 2026.10.4: `pytest -q tests` **160 bestanden**; darin enthalten sind echte isolierte Core-Config-Entry-/YAML-Integrationstests. Der zuvor übersprungene Browser-Backend-Test wurde nach `npm ci` ausgeführt.
- Chromium + WebKit: **46 Browserfälle bestanden**, einschließlich 320/430-px-Mobile, Light/Dark, Entwurf, gesperrtem Apply, Filter-/Statuszahlen und 5.000-Entity-Seite. Das ist eine Browser-Fixture, kein produktives iPhone.
- `ruff 0.17.3` für die CI-Modulliste, `pip check`, JS-Syntaxtest, Frontend-Unit-Test und `npm audit --audit-level=high`: bestanden. Für diesen Branch liegt noch **kein** GitHub-CI-Lauf vor.
- Der lokale Build nach Aktualisierung des Dateimanifests ist nur ein unveröffentlichtes Entwicklungsartefakt mit der bisherigen Manifest-Version 0.9.24. Er ist **kein** 0.10.0-Release-Kandidat und darf nicht installiert oder veröffentlicht werden.

## Offene Gates

Der reguläre Core-Testharness verhindert absichtlich Netzwerk-Sockets. Ein Versuch, eine reale isolierte HAP-Bridge dort zu starten, endete schon bei der Socket-Erzeugung; er ist **kein** HAP-Testnachweis und wurde nicht als grüner Test aufgenommen. Es gibt kein unabhängig gepairtes Apple-Home-Testgerät. Folgende Arbeit bleibt vor einem GO nötig:

1. Echte isolierte HAP-Bridge und Persistenz/AID/IID vor und nach Filteränderung, Reload und Core-Neustart prüfen; Apple-Home-Pairings nicht behaupten.
2. Server-seitigen, begrenzten und widerrufbaren Produktiv-Grant implementieren und adversarial prüfen, ohne die bestehende Installation zu aktivieren.
3. Direkte YAML-Konfiguration und weitere sichere Strukturen mit Dateipfadsicherheit, Roundtrip, Recovery und realem Core-Reload testen; unsichere Formen präzise read-only lassen.
4. Produktive Registry-/State-/Entry-Zählung nur bei berechtigtem lesendem Zugriff nachholen; insbesondere 251/375, Shelly-Sensoren, aktiven UI-Filter und 129/121 prüfen.
5. Vollständige Core/HAP-, Browser-, Security-, Performance-, Upgrade- und Release-Extrakt-Prüfung für den **finalen** Commit, danach zweiter Review und GitHub-CI/Review-Gates.

Die produktive Bridge wurde in diesem Arbeitsstand weder verändert noch neu geladen. Ein 0.10.0-Tag oder Release ist bei diesem Stand unzulässig.
