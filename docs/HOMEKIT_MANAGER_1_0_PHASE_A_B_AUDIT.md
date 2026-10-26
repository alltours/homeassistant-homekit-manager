# HomeKit Manager 1.0 – Phase A/B Architektur- und Schreibpfad-Audit

Stand: 2026-10-26  
Branch: `feature/homekit-manager-1.0-architecture-audit`  
Basis: `origin/main`, Release-Commit `8af4d6b68db1d99094951477195463f18145e681`  
Lokale Home-Assistant-Testlaufzeit: 2026.10.4, Python 3.14

## Ergebnis

Phase A und Phase B sind lokal abgeschlossen. Die vorhandene Architektur ist für eine sichere read-only-Verwaltung und Änderungsplanung geeignet. Die produktive Anwendung von HomeKit-Änderungen ist technisch noch nicht als sicher unterstützter Cross-Integration-Pfad nachgewiesen und bleibt deshalb gesperrt.

**Entscheidung: NO-GO für einen produktiven Schreibpfad; CONDITIONAL-GO für die read-only-Weiterentwicklung.**

Es wurden keine produktiven Home-Assistant-Dateien, Config-Entries, Pairings, `.storage`-Daten oder HomeKit-Bridges verändert.

## 1. Prüfgrundlage

### Repository

Der Stand von `origin/main` enthält:

- die Custom Integration unter `custom_components/homekit_manager/`;
- Config Flow, Setup/Unload und Panelregistrierung;
- Coordinator mit Entity-, Device- und Area-Registry-Auswertung;
- HomeKit-Reader mit Redaction sensibler Schlüssel;
- Filterauswertung, Draft-/YAML-Speicher, Fingerprints, Vorschau und Export;
- WebSocket-Endpunkte mit Administratorprüfung;
- den ausdrücklich gesperrten `HomeKitWriter`;
- Python-/Home-Assistant-Integrationstests und Frontend-Fixturetests;
- CI-, HACS- und Release-Manifest-Prüfungen.

### Home-Assistant-Core

Geprüft wurde die lokal installierte Core-Laufzeit 2026.10.4, insbesondere:

- `homeassistant/components/homekit/__init__.py`;
- `homeassistant/components/homekit/config_flow.py`;
- `homeassistant/helpers/entityfilter.py`;
- `homeassistant/config_entries.py`.

Die Aussagen beziehen sich auf diesen lokal vorliegenden Quellstand, nicht auf eine ungeprüfte zukünftige Core-Version.

## 2. Architektur-Bestandsaufnahme

| Komponente | Tatsächlicher Stand | Bewertung |
|---|---|---|
| Integration Setup/Unload | `async_setup`, `async_setup_entry`, `async_unload_entry` vorhanden | umgesetzt |
| Config Flow | eigener einmaliger Manager-Config-Entry | umgesetzt |
| Panel | statische Ressource und Custom Panel | umgesetzt |
| Coordinator | Registry-/State-Lesen, Debouncing, Fingerprint | umgesetzt, weiter zu härten |
| Inventory | Entity-, Device- und Area-Registry-Zuordnung | umgesetzt |
| HomeKit Reader | liest vorhandene `homekit`-Config-Entries, redigiert sensible Schlüssel | umgesetzt, Mehrfach-Bridge-Auswahl ausbauen |
| Filterauswertung | Include/Exclude für Domains, Entities und Globs | umgesetzt, gegen Core-Regressionen zu erweitern |
| Change Planner | Entwurf, Vorschau, Konflikt-/Scope-Prüfung | umgesetzt |
| YAML Store | validierter Draft-Speicher mit Versionskonflikten | umgesetzt |
| History | bounded In-Memory-Historie und Restore-as-Draft | teilweise; Neustartpersistenz fehlt |
| Rules | Vorschau/Suggestion | teilweise; keine automatische Anwendung |
| Diagnostics | Findings und Zusammenfassung | umgesetzt, fachlich zu vervollständigen |
| WebSocket API | authentifizierte Admin-Kommandos | umgesetzt |
| HomeKit Writer | `async_apply()` verweigert jede Anwendung | sicherheitskonform, bewusst unvollständig |
| Multi-Bridge | Erkennung und konservatives Blockieren bei Mehrdeutigkeit | teilweise |
| Frontend | vier Hauptansichten, Draft-/Statusdarstellung | umgesetzt; echte Browsermatrix offen |

## 3. Phase-B-Befund: HomeKit-Core-Vertrag

### 3.1 Bestehende Bridges lesen

Home Assistant verwaltet HomeKit-Instanzen als Config-Entries der Domain `homekit`. Der Manager liest `data`, `options`, `state`, `source`, Titel und Entry-Fähigkeiten. Der Reader redigiert Schlüssel mit Hinweisen auf Passwörter, Tokens, Secrets, PINs, Schlüssel oder Pairing-Material.

Aus dem Config-Entry darf nicht abgeleitet werden, dass ein Accessory tatsächlich in Apple Home sichtbar ist. Der Manager meldet diese Information daher konservativ als unbekannt.

### 3.2 Core-Filtersemantik

Core 2026.10.4 verwendet `homeassistant.helpers.entityfilter.EntityFilter`. Die Implementierung unterscheidet sechs Fälle:

1. keine Include-/Exclude-Regeln: alle Entities;
2. nur Includes: Entity-, Domain- oder Glob-Include;
3. nur Excludes: Entity-, Domain- oder Glob-Exclude;
4. Includes mit Domain-/Glob-Includes und möglichen Excludes;
5. Excludes ohne Domain-/Glob-Includes;
6. nur explizite Entity-Includes.

Explizite Entity-Includes haben Sonderprioritäten. Eine vereinfachte Regel „Exclude gewinnt immer“ wäre daher falsch. Der Manager muss die Core-Semantik nachbilden oder in einer versionsgebundenen Adapter-Schicht verwenden.

### 3.3 OptionsFlow und Reload

Die offizielle HomeKit-Integration stellt `ConfigFlow.async_get_options_flow()` und einen `OptionsFlowHandler` bereit. Dieser verarbeitet unter anderem `homekit_mode`, Include-/Exclude-Modus, Domains, Entities, `filter`, `entity_config`, Kamera-/Klimaoptionen und Bridge-Device-Trigger.

Nach einem erfolgreichen OptionsFlow wird der Config-Entry über den normalen Config-Entry-Lifecycle aktualisiert. Der geprüfte Core registriert einen Update-Listener und ruft anschließend `hass.config_entries.async_reload(entry.entry_id)` auf.

### 3.4 Schreibpfad-Entscheidung

Im geprüften Core wurde kein stabiler, öffentlich dokumentierter Dienst gefunden, mit dem eine fremde Custom Integration den vollständigen OptionsFlow einer bestehenden HomeKit-Config-Entry sicher und autorisiert im Namen des Benutzers absenden kann.

`hass.config_entries.async_update_entry(...)` ist zwar eine Core-Methode, aber ein direkter Cross-Integration-Aufruf würde Benutzerführung, Validierung und Verantwortungsgrenzen des offiziellen HomeKit-OptionsFlows umgehen. Der anschließende Reload kann abhängig von Modus, Filter, Entity-Konfiguration und Accessory-Verhalten Identitäts- oder Pairing-Risiken haben.

Daher gilt:

- kein direkter Aufruf von `async_update_entry` für produktive HomeKit-Entries;
- kein direkter Aufruf von `async_reload` für HomeKit aus dem Manager;
- keine direkte `.storage`-Manipulation;
- keine Pairing-, Accessory-ID- oder IID-Manipulation;
- keine simulierte Erfolgsmeldung;
- `HomeKitWriter.async_apply()` bleibt blockierend.

## 4. Sichere Architekturentscheidung

Bis ein unterstützter Schreibvertrag nachgewiesen ist, bleibt der Manager ein read-only Reader plus Draft-/Preview-/Export-Werkzeug:

1. aktuelle HomeKit-Config-Entries lesen;
2. Filter exakt bewerten;
3. Entitäten-, Geräte- und Bereichsstatus getrennt berechnen;
4. Änderungen als Draft speichern;
5. Fingerprint und Versionskonflikte prüfen;
6. Vorher-/Nachher-Vorschau erzeugen;
7. YAML beziehungsweise native Optionen exportieren;
8. den offiziellen HomeKit-OptionsFlow als manuelle Übernahme anweisen;
9. danach den Zustand erneut lesen und abgleichen.

Ein aktivierbarer Writer benötigt zuvor einen nachweisbaren Core-Vertrag, versionsgebundene Adaptertests, echte Config-Entry-Lifecycle-Tests, Konflikt- und Sperrlogik, einen verifizierten Wiederherstellungsweg sowie einen Nachweis zu Identitäts- und Pairing-Garantien. Ohne diese Nachweise bleibt die Anwendung blockiert.

## 5. Anforderungsmatrix

| Anforderung | Istzustand | Zielzustand | Risiko | Abnahmekriterium |
|---|---|---|---|---|
| Bestehende Bridge erkennen | umgesetzt | mehrere Bridges eindeutig auswählen | mittel | jede Bridge getrennt mit ID/Titel/Status |
| Core-Filter korrekt auswerten | umgesetzt, Regressionen ausbauen | vollständige Core-Parität | hoch | alle Core-Fälle identisch |
| Istzustand/Draft trennen | umgesetzt | über alle Ansichten konsistent | mittel | Öffnen erzeugt keinen Draft |
| Konflikte erkennen | Fingerprint vorhanden | vollständiger Bridge-/Registry-Konflikt | hoch | Anwendung bei Abweichung blockiert |
| Geräte mit mehreren Entities | teilweise | sichere mixed/unknown-Zustände | mittel | keine stille Massenänderung |
| Draft/Historie persistieren | Draft vorhanden, Historie In-Memory | sichere Neustartpersistenz | mittel | Schema ohne Pairingdaten |
| Schreibpfad | bewusst gesperrt | nur bei Core-Vertrag aktivieren | sehr hoch | echte Anwendung und Verifikation |
| Mobile UX | strukturell vorhanden | reale Viewport-/Theme-Abnahme | mittel | 390/430/768/1440, Light/Dark |
| Performance | Summarizer vorhanden | Messungen für 1k/2.5k/5k | mittel | Grenzwerte dokumentiert |

## 6. Sicherheitsstatus

| Schutzmaßnahme | Befund |
|---|---|
| `apply_enabled = False` | bestätigt |
| `HomeKitWriter.async_apply()` | wirft `HomeKitWriteDisabled` |
| HomeKit-Config-Entry-Update | nicht implementiert |
| HomeKit-Reload | nicht durch Manager implementiert |
| Pairing-Manipulation | nicht implementiert |
| `.storage`-Manipulation | nicht implementiert |
| Bridge-Neuanlage/Löschung | nicht implementiert |
| Admin-WebSocket-Schutz | vorhanden |
| Sensible Reader-Daten | redigiert |
| Produktivsystem | nicht verändert |

## 7. Tests zum Auditstand

Nachgewiesen sind auf dem geprüften Vorgängerstand:

- 42 Python-/Home-Assistant-Tests erfolgreich;
- Frontend-Verhaltenstest erfolgreich;
- JavaScript-Syntaxprüfung erfolgreich;
- Release-Manifest mit 30 Dateien und Hashes erfolgreich;
- CI erfolgreich;
- HACS validation erfolgreich.

Nicht als abgeschlossen nachgewiesen sind:

- vollständige echte Browsermatrix mit Chromium/WebKit;
- alle geforderten mobilen Viewports;
- Dark-/Light-Mode-Abnahme;
- fünfminütige Browser-Stabilitätsbeobachtung;
- echter Pairing-/Accessory-Identity-Erhalt nach produktiver Änderung;
- echte produktive Anwendung einer HomeKit-Änderung.

## 8. Nächste Schritte

1. Core-Adapter für Filtersemantik als versionsgebundene Testschicht ausbauen.
2. Multi-Bridge-Auswahl und Statusmodell deterministisch machen.
3. Persistenz von Draft-/Historienmetadaten mit Secret-Ausschluss prüfen.
4. Reproduzierbare Playwright-/WebKit-Browserumgebung herstellen.
5. Performance-Szenarien mit 1.000, 2.500 und 5.000 Entitäten messen.
6. Offiziellen HomeKit-OptionsFlow als sicheren manuellen Übergabepunkt dokumentieren.
7. Erst bei einem nachgewiesenen Core-Vertrag einen isolierten Writer-Adapter entwerfen.
8. Vor jeder Aktivierung des Writers eine separate Sicherheits- und Produktivfreigabe einholen.

## Schlussbewertung

**CONDITIONAL-GO für die sichere read-only-Weiterentwicklung.**

**NO-GO für eine produktive HomeKit-Schreibfunktion und für die Bezeichnung „vollständig 1.0.0-fertig“.**
