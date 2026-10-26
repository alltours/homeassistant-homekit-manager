# HomeKit Manager – Konsolidierter Gesamtbericht 0.9.2 bis 0.9.9

**Berichtsstand:** 26.10.2026  
**Lokaler Quellenstand:** Branch `feature/homekit-manager-0.9.9`, getesteter Quellstand `67b73ac`
**Produktiver Zielstand:** zuletzt autorisiert und dokumentiert als 0.9.2  
**Bewertung:** **CONDITIONAL-GO**

## Quellen und Nachweisqualität

Dieser Bericht wurde anhand der folgenden Quellen erstellt:

| Quelle | Prüfung | Nachweisstatus |
|---|---|---|
| Lokale Git-Historie | Commits, Branches und Tags | selbst überprüft |
| Lokale Quelltexte | Integration, Frontend, Tests und Manifest | selbst überprüft |
| Lokale Dokumentation | Versionsberichte, Roadmap, Testbericht und Release-Manifest | selbst überprüft |
| GitHub Repository API | Sichtbarkeit, Default-Branch und Releases | selbst überprüft |
| GitHub Actions API | Workflow-Läufe und Ergebnisse | selbst überprüft |
| Produktive Home-Assistant-Oberfläche | frühere autorisierte Live-Prüfungen | dokumentierter früherer Nachweis |
| Aktuelle produktive Browserprüfung | aktueller Browserzugriff | aktuell nicht möglich, Mac gesperrt |
| Home-Assistant-Logs | aktueller vollständiger Logzugang | nicht aktuell nachgewiesen |

Historische Phasenberichte werden als dokumentierte Behauptungen gekennzeichnet. Aktuelle lokale Tests und aktuelle GitHub-API-Daten werden als selbst überprüfte Ergebnisse behandelt.

## A. Management Summary

### Ausgangssituation

Der HomeKit Manager entstand als Home-Assistant-Custom-Integration für die read-only-Erfassung einer bestehenden HomeKit-Bridge. Das ursprüngliche Risiko bestand darin, die vorhandene HomeKit-Konfiguration, Bridge-Identität oder Pairings durch eigene Verwaltungslogik unbeabsichtigt zu verändern.

Die zentrale Sicherheitsentscheidung war deshalb:

- `apply_enabled = False`
- `HomeKitWriter.async_apply()` verweigert jede Anwendung.
- Keine automatische Änderung an HomeKit-Config-Entries.
- Keine HomeKit-Reloads.
- Keine Pairing-, Accessory- oder IID-Manipulation.
- Keine automatische Bridge-Neuanlage, Löschung oder Verschiebung.

### Entwicklungsziele

Die Reihe 0.9.2 bis 0.9.9 sollte:

- eine native Home-Assistant-Oberfläche bereitstellen,
- Entitäten, Geräte, Bereiche und Bridges erfassen,
- HomeKit-Kompatibilität und Filterstatus auswerten,
- Desired-State-Entwürfe und Vorschauen ermöglichen,
- Konflikte und Risiken sichtbar machen,
- mehrere Bridges konservativ behandeln,
- Diagnose-, Regel-, Historien- und Performancefunktionen ergänzen,
- eine sichere Release-Basis schaffen,
- aber keine ungesicherte HomeKit-Änderung durchführen.

### Erreichter Zustand

Lokal ist eine umfangreiche 0.9.9-Implementierung vorhanden:

- 30 Integrationsdateien.
- Backend mit Inventar, Reader, Diagnose, Regeln, Vorschau, Historie und Performance-Metriken.
- Native Paneloberfläche.
- Authentifizierte Admin-WebSocket-Endpunkte.
- 42 bestandene lokale Unit-/Integrationstests.
- Erfolgreiche Frontend- und JavaScript-Prüfungen.
- Erfolgreiche Desktop- und mobile Chromium-Fixture-Prüfung.
- Accessibility- und Tab-Semantik-Regressionstests.
- Vollständig hashverifiziertes 30-Dateien-ZIP-Archiv.
- CI-Prüfung für Release-Manifest und SHA-256-Dateien.

### Wichtigste Verbesserungen

- Geräte- und Bereichsaggregation.
- Konservative Multi-Bridge-Sicherheitslogik.
- Read-only-Diagnose.
- Simulierte HomeKit-Gerätevorschau.
- Deterministische Regelvorschau.
- Begrenzte Desired-State-Historie.
- Performance- und Größenmetriken.
- Mobile Layoutkorrektur.
- Accessibility-Semantik.
- Release-Manifestprüfung in CI.

### Aktuell produktiv installierte Version

Die zuletzt autorisiert und über den File Editor dokumentierte produktive Version ist **0.9.2**.

Die aktuelle erneute Browserprüfung war bei Erstellung dieses Berichts wegen eines gesperrten Macs nicht möglich. Ein unauthentifizierter HTTP-Readiness-Check lieferte HTTP 200, ersetzt aber keine authentifizierte Live-Abnahme.

### Verbleibende Einschränkungen

- 0.9.3 bis 0.9.8 sind lokal entwickelt, aber nicht als 0.9.x-Tags oder 0.9.x-GitHub-Releases veröffentlicht; `v0.9.9` ist als Git-Tag vorhanden, ein GitHub-Release fehlt noch.
- GitHub enthält zusätzlich historische 1.0.1-, 1.0.2- und 1.0.3-Releases.
- Der 0.9.9-Branch ist nach GitHub gepusht, aber noch nicht nach `main` gemergt.
- CI, HACS und Hassfest sind für den Branch erfolgreich durchgelaufen.
- HACS zeigt produktiv zuletzt den Status „Ausstehende Aktualisierung“; eine Aktualisierung wurde nicht durchgeführt.
- Die Historie ist nur laufzeitbezogen und nicht restartpersistent.
- Es gibt keine vollständige Screenreader-Abnahme mit einem realen Screenreader.
- Es gibt keine realen Live-Lasttests mit 2.500 oder 5.000 Home-Assistant-Entitäten.
- Apple-Home-Pairing-Erhalt wurde nicht unabhängig verifiziert.

## B. Vollständige Versionshistorie

| Version | Schwerpunkt | Implementierung | Tests | GitHub-Release | Produktive Installation |
|---|---|---|---|---|---|
| 0.9.2 | UI und Konfigurationsverwaltung | Lokal implementiert und als `v0.9.2` veröffentlicht | Historischer Bericht nennt bestandene Python-, JSON-, JavaScript-, Frontend- und HA-Prüfungen; keine einheitliche Zahl im Bericht | **Ja**, `v0.9.2`; GitHub Actions erfolgreich | Zuletzt dokumentierter produktiver Stand |
| 0.9.3 | Geräte- und Bereichsverwaltung | `grouping.py`, Geräte-/Bereichs-WebSockets und Frontend-Tabs | Historischer Bericht: 31 HA-Integrationstests bestanden | **Nein** | Nicht produktiv installiert |
| 0.9.4 | Kompatibilität und Diagnose | `diagnostics.py`, Diagnose-WebSocket und Diagnoseansicht | Historischer Bericht: 33 Unit-/Integrationstests bestanden | **Nein** | Nicht produktiv installiert |
| 0.9.5 | Erweiterte Gerätekonfiguration | Simulierte `device_preview`-Vorschau, keine Anwendung | Historischer Bericht: 35 Unit-/Integrationstests bestanden | **Nein** | Nicht produktiv installiert |
| 0.9.6 | Multi-Bridge-Management | Bridge-Auswahlpflicht und Sperre bei Mehrdeutigkeit | Historischer Bericht: 35 Tests bestanden | **Nein** | Nicht produktiv installiert |
| 0.9.7 | Regelbasierte Freigabe | Deterministische Rules Engine und Konfliktvorschau | Historischer Bericht: 37 Tests bestanden | **Nein** | Nicht produktiv installiert |
| 0.9.8 | Historie und Wiederherstellung | In-Memory-Historie, Vergleich und Entwurfswiederherstellung | Historischer Bericht: 39 Tests bestanden | **Nein** | Nicht produktiv installiert |
| 0.9.9 | Performance und Produktreife | Performance-Metriken, große synthetische Inventare, Accessibility, Browser-Fixture und Releaseprüfung | Aktueller lokaler Stand: 42 Tests bestanden; Browser-/Mobile-Fixture bestanden | **Nein** | Nicht produktiv installiert |

Die historischen Testzahlen sind aus den jeweiligen Phasenberichten übernommen. Die aktuelle 0.9.9-Testzahl wurde lokal erneut ausgeführt.

### Lokale Commit-Zuordnung

| Version | Commit |
|---|---|
| 0.9.2 | `f3c4924`, integriert über `2effeb1` |
| 0.9.3 | `3caa974` |
| 0.9.4 | `f47dc70` |
| 0.9.5 | `5a0e726` |
| 0.9.6 | `19a4077` |
| 0.9.7 | `041ea7d` |
| 0.9.8 | `17e2080` |
| 0.9.9 | `3c482d9`, ergänzt durch Folgecommits bis `dda86b5` |

## C. Endgültige Architektur

### Frontend

Die Frontend-Datei ist:

`custom_components/homekit_manager/www/homekit-manager.js`

Sie implementiert ein Custom Element `homekit-manager-panel` mit:

- Übersicht.
- Entitäten.
- Geräte.
- Bereiche.
- Diagnose.
- Konfiguration.
- Änderungen.
- Suche.
- Filtern.
- Sortierung.
- Pagination.
- Mehrfachauswahl.
- Desired-State-Entwürfen.
- Vorschau.
- Export.
- Responsive Layout.
- Fehler- und Ladezuständen.
- Accessibility-Semantik.

Das Frontend nutzt Home-Assistant-CSS-Variablen und native HTML-Controls. Eine vollständige visuelle Dark-/Light-Mode-Abnahme für alle HA-Themes wurde nicht durchgeführt.

### Backend und Coordinator

`coordinator.py` ist die zentrale Orchestrierungsschicht. Sie:

- liest Home-Assistant-Registries und States,
- baut das Inventar,
- liest HomeKit-Config-Entries,
- berechnet Kompatibilität und Filterstatus,
- aggregiert Geräte und Bereiche,
- erstellt Diagnosebefunde,
- verwaltet YAML-Snapshots,
- berechnet Fingerprints,
- koordiniert Entwürfe,
- hält die begrenzte Laufzeithistorie,
- verwaltet gewünschte Verwaltungsmodi.

Die Aktualisierung reagiert eventgetrieben auf State-, Entity-Registry-, Device-Registry-, Area-Registry- und HomeKit-Ereignisse. Bursts werden debounced. Ein gewöhnlicher Frontend-State-Update löst keinen vollständigen Inventar-Reload aus.

### WebSocket-API

Alle Verwaltungs-WebSocket-Endpunkte sind mit `require_admin` geschützt.

Nachgewiesene beziehungsweise implementierte Endpunkte:

- `homekit_manager/inventory`
- `homekit_manager/bridges`
- `homekit_manager/devices`
- `homekit_manager/areas`
- `homekit_manager/diagnostics`
- `homekit_manager/device_preview`
- `homekit_manager/rules_preview`
- `homekit_manager/history`
- `homekit_manager/history_restore`
- `homekit_manager/performance`
- `homekit_manager/mode_status`
- `homekit_manager/set_mode`
- `homekit_manager/yaml_status`
- `homekit_manager/validate_draft`
- `homekit_manager/preview`
- `homekit_manager/save_draft`
- `homekit_manager/prepare_options_diff`
- `homekit_manager/reconcile`
- `homekit_manager/export`

Es gibt keine freigegebene HomeKit-Anwendungsoperation.

### Inventory Service

Der Inventory Service liegt hauptsächlich in `inventory.py` und `coordinator.py`.

Er verarbeitet:

- Entity Registry.
- Device Registry.
- Area Registry.
- State Machine.
- Entity-ID.
- Domain.
- Anzeigename.
- Bereich.
- Gerät.
- Integration.
- Device Class.
- Entity Category.
- Verfügbarkeit.
- State.
- Config-Entry-ID.

State-only-Entitäten ohne Registry-Metadaten werden als Fallback-Datensätze sichtbar gemacht.

### Configuration Reader

Der HomeKit Reader in `homekit_reader.py` liest bestehende HomeKit-Config-Entries über Home-Assistant-Config-Entry-APIs.

Er liefert:

- Entry-ID.
- Titel.
- Status.
- Quelle.
- Modus.
- Filter.
- Optionen, soweit zulässig.
- sichere Metadaten.

Sensible Schlüssel werden rekursiv redigiert. Pairing- und Geheimniswerte werden nicht ausgegeben.

### Configuration Generator

Die Generatorfunktionalität ist verteilt auf:

- `yaml_store.py`
- `draft.py`
- `exporter.py`
- `change_planner.py`
- `reconcile.py`

Sie erzeugt und validiert Desired-State-Dokumente sowie YAML- oder JSON-Exporte.

Sie verändert nicht automatisch die offizielle HomeKit-Config-Entry.

### Validation Service

Die Validierung liegt in `yaml_store.py`, `coordinator.py`, `filtering.py` und `change_planner.py`.

Sie prüft:

- Schema-Version.
- Entity-ID-Format.
- Bridge-Struktur.
- Include-/Exclude-Entscheidungen.
- Versionskonflikte.
- Fingerprint-Konflikte.
- Unbekannte Entitäten.
- Inkompatible Entitäten.
- Nicht eindeutig zuordenbare Bridges.

### Migration Controller

Ein eigenständiger vollständiger Migration Controller ist nicht implementiert.

Die vorhandene Migrationsebene besteht aus:

- Verwaltungsmodus-Modell.
- Migrationsmatrix im Coordinator.
- konservativer Statusberechnung.
- Sperre aller Cross-Mode-Aktivierungen.

Eine echte automatische Migration von YAML, HomeKit Bridge oder HomeKit Manager findet nicht statt.

### Diagnostics Service

`diagnostics.py` erstellt Befunde für:

- Unsupported- oder Unknown-Entitäten.
- Nicht verfügbare Entitäten.
- Veraltete Filterreferenzen.
- Mehrfachzuordnungen.
- Ungültiges YAML.
- weitere inkonsistente Zustände.

Die Diagnose ist read-only und erzeugt Handlungsempfehlungen.

### Rules Engine

`rules.py` wertet Regeln deterministisch aus.

Sie unterstützt:

- Match-Felder.
- Prioritäten.
- Aktivierung.
- Include.
- Exclude.
- manuelle Entscheidungen.
- Konflikterkennung.

Regeln werden nur vorgeschlagen. Es gibt keine automatische Anwendung.

### History Service

`history.py` erzeugt:

- redigierte Desired-State-Einträge,
- Zeitstempel,
- Änderungsgrund,
- Fingerprint,
- Diff-Zusammenfassung,
- Wiederherstellung als neuen Entwurf.

Die Coordinator-Historie ist auf die letzten 50 Einträge begrenzt und nur im laufenden Manager-Prozess vorhanden. Eine persistente Historie über Home-Assistant-Neustarts hinweg ist nicht implementiert.

## D. Benutzeroberfläche

### Tatsächlich vorhandene Bereiche

| Bereich | Status |
|---|---|
| Übersicht | Implementiert |
| Entitäten | Implementiert |
| Geräte | Implementiert |
| Bereiche | Implementiert |
| Bridges | In Konfigurationsansicht und Übersicht dargestellt |
| Konfiguration | Implementiert |
| Änderungen | Implementiert |
| Diagnose | Implementiert |
| Historie | Backend-WebSockets vorhanden, kein eigener Frontend-Tab |
| Einrichtungsassistent | Nicht als eigener Frontend-Assistent implementiert |

### Übersicht

Die Übersicht zeigt:

- erkannte Bridge,
- Entitätsanzahl,
- Kompatibilitätsanzahl,
- freigegebene Entitäten,
- nicht verfügbare Entitäten,
- offene Änderungen,
- aktiven und gewünschten Modus,
- Synchronisierungsstatus.

### Entitäten

Die Entitätsansicht bietet:

- Suche.
- Bereichsfilter.
- Gerätefilter.
- Integrationsfilter.
- Domainfilter.
- Kompatibilitätsfilter.
- Statusfilter.
- Sortierung.
- Pagination.
- Mehrfachauswahl.
- Include-/Exclude-/Reset-Aktionen.
- Detailansicht.
- simulierte HomeKit-Vorschau.

### Geräte und Bereiche

Geräte und Bereiche werden als aggregierte Übersichten angezeigt. Sie sind keine vollständigen individuellen HomeKit-Konfigurationseditoren.

### Bridges

Bei genau einer Bridge kann der read-only Kontext verwendet werden.

Bei mehreren Bridges:

- wird keine erste Bridge implizit ausgewählt,
- wird `bridge_selection_required` gesetzt,
- werden Moduswechsel gesperrt,
- werden Änderungsplanung und native Optionsvorschau gesperrt.

Eine vollständige interaktive Einzelbridge-Auswahl mit separatem Inventar pro Bridge ist nicht fertig implementiert.

### Bedienbarkeit und Rendering

Nachgewiesen:

- Desktop-Chromium-Fixture.
- Mobile Chromium bei 500x844.
- sichtbare Lade- und Fehlerzustände.
- Pagination.
- responsive Karten.
- kontrolliertes horizontales Scrollen der Tab-Leiste.
- Tastaturbedienbare Sortierbuttons.
- semantische Tab-Navigation.
- beschriftete Formularelemente.

Nicht vollständig nachgewiesen:

- alle HA-Dark-/Light-Themes,
- reale iPhone-/iPad-Geräte,
- vollständige Screenreader-Abnahme,
- vollständige Langzeitbedienung.

## E. Konfigurationsverwaltung

Es existieren drei vorgesehene Verwaltungsmodi:

1. YAML.
2. HomeKit Bridge.
3. HomeKit Manager.

### YAML-Modus

Funktionsweise:

- Desired-State-Dokumente werden als YAML validiert.
- Standardpfad ist `/config/homekit_manager.yaml`.
- Der Pfad wird aus `hass.config.path` abgeleitet, wenn verfügbar.
- Speicherung erfolgt atomar mit Versionsprüfung.
- YAML-Status wird gelesen und als gültig/ungültig/nicht vorhanden gemeldet.

Unterstützte Schreiboperationen:

- Speichern eines HomeKit-Manager-Desired-State-Entwurfs.
- Kein automatisches Einfügen in `configuration.yaml`.
- Keine automatische Aktivierung des YAML-HomeKit-Modus.

Technische Einschränkungen:

- YAML wird nicht automatisch in die offizielle HomeKit-Konfiguration integriert.
- Der Manager ersetzt keine bestehende HomeKit-Bridge.
- Ein Include in `configuration.yaml` wird nicht automatisch erzeugt.

Produktiver Status:

- Als Manager-YAML-Speicher technisch implementiert.
- Keine produktive YAML-Migration nachgewiesen.

### HomeKit-Bridge-Modus

Funktionsweise:

- Bestehende HomeKit-Config-Entries werden gelesen.
- Filter und sichere Metadaten werden ausgewertet.
- Der aktuelle aktive Modus wird bei erkannter Bridge konservativ als `homekit_bridge` gemeldet.

Unterstützte Schreiboperationen:

- Keine produktive Änderung.
- `prepare_options_diff` erzeugt ausschließlich einen Diff.
- `HomeKitWriter.async_apply()` verweigert jede Anwendung.

Technische Einschränkungen:

- Keine unterstützte sichere API zur direkten Änderung einer fremden HomeKit-Config-Entry nachgewiesen.
- Bridge-Identität und Pairing-Erhalt werden nicht automatisch garantiert.
- Apple-Home-Sichtbarkeit wird nicht als sicher nachgewiesen.

Produktiver Status:

- Bestehende Bridge wurde in früheren Live-Prüfungen erkannt.
- Aktuelle erneute Browserprüfung ist wegen gesperrtem Mac nicht möglich.

### HomeKit-Manager-Modus

Funktionsweise:

- Der Manager stellt Inventar, Diagnose, Entwürfe, Vorschauen und Exporte bereit.
- Der gewünschte Modus kann als Manager-Metadatum gespeichert werden.
- Ein Moduswechsel wird nur vorbereitet, nicht aktiviert.

Unterstützte Schreiboperationen:

- Manager-eigene Metadaten über Home-Assistant-Store.
- Entwurfsspeicherung in `homekit_manager.yaml`.
- Keine HomeKit-Optionsänderung.

Technische Einschränkungen:

- Kein automatischer Wechsel einer bestehenden HomeKit-Bridge.
- Keine Pairing-Migration.
- Keine automatische Apple-Home-Migration.

Produktiver Status:

- Integration lokal implementiert.
- Produktive Manager-Installation zuletzt als 0.9.2 dokumentiert.
- 0.9.9 nicht produktiv installiert.

### `configuration.yaml`

Eine automatische YAML-Einbindung in `configuration.yaml` ist ausdrücklich nicht implementiert.

Der Manager erzeugt oder verändert keinen Include-Eintrag und ersetzt keine bestehende HomeKit-Konfiguration.

## F. Migration und Reversibilität

Die Matrix enthält sechs unterschiedliche Wechselrichtungen.

| Quelle | Ziel | Status | Begründung |
|---|---|---|---|
| YAML | YAML | Sicher | Keine Migration erforderlich |
| YAML | HomeKit Bridge | Manuell erforderlich | Bridge-Identität und Pairings werden nicht automatisch migriert |
| YAML | HomeKit Manager | Manuell erforderlich | Keine automatische Aktivierung |
| HomeKit Bridge | YAML | Manuell erforderlich | Keine automatische Übertragung von Bridge-Identität oder Pairings |
| HomeKit Bridge | HomeKit Manager | Manuell erforderlich | Manager liest vor, ersetzt aber die Bridge nicht |
| HomeKit Manager | YAML | Manuell erforderlich | Entwurfsexport vorhanden, Aktivierung nicht automatisch |
| HomeKit Manager | HomeKit Bridge | Manuell erforderlich | Offizieller HomeKit-Dialog und manuelle Prüfung erforderlich |
| HomeKit Manager | HomeKit Manager | Sicher | Keine Migration erforderlich |

Die sechs Cross-Mode-Richtungen sind technisch nicht als automatische Migration implementiert.

### Bridge-Identität und Pairings

Nicht nachgewiesen:

- Erhalt der Apple-Home-Zuordnung.
- Erhalt aller Pairing-Beziehungen bei einer Migration.
- Erhalt von Accessory-IDs und Instance-IDs über einen automatischen Wechsel.

Daher bleiben Cross-Mode-Aktivierungen gesperrt.

### Reversibilität

Reversibel sind lokal:

- Entwürfe verwerfen.
- YAML-Versionenkonflikte erkennen.
- YAML-Backup-/Snapshot-Mechanismen innerhalb des Managerpfads.
- Historieneintrag als neuen Entwurf wiederherstellen.

Nicht automatisch reversibel sind:

- Änderungen an einer offiziellen HomeKit-Bridge.
- Pairing-Änderungen.
- Apple-Home-Zuordnungen.
- Bridge-Neuanlage, Löschung oder Verschiebung.

## G. Geräte- und Bereichsverwaltung

### Geräteerkennung

Geräte werden aus der Device Registry gelesen und über Entity Registry-Einträge aggregiert.

Erfasst werden:

- Device-ID.
- Benutzername beziehungsweise Gerätename.
- Bereich.
- Entitätsanzahl.
- Kompatibilitätsanzahl.
- Konfigurationsanzahl.
- Verfügbarkeitsanzahl.
- Integrationszugehörigkeit.

### Bereichszuordnung

Bereiche werden aus Area Registry und Geräte-/Entitätszuordnung gelesen. Nicht zugeordnete Einträge werden als „Kein Bereich“ dargestellt.

### Sammelaktionen

Die Entitätsansicht unterstützt:

- sichtbare Entitäten auswählen,
- kompatible Entitäten auswählen,
- Auswahl einschließen,
- Auswahl ausschließen,
- Auswahl zurücksetzen.

Diese Aktionen verändern nur den lokalen Desired-State-Entwurf.

### Automatische Erkennung neuer Geräte

Der Coordinator hört auf:

- State-Änderungen,
- Entity-Registry-Updates,
- Device-Registry-Updates,
- Area-Registry-Updates,
- HomeKit-State-Änderungen.

Nach debounced Refresh werden neue Entitäten und Geräte im Inventar sichtbar.

Eine automatische HomeKit-Freigabe oder Veröffentlichung findet nicht statt.

### Konfliktbehandlung

Konflikte werden über:

- Fingerprints,
- erwartete YAML-Dateiversionen,
- eindeutige Bridge-Auswahl,
- Kompatibilitätsstatus,
- unbekannte Entitäten

erkannt und als Fehler oder Blockierung gemeldet.

## H. Kompatibilität und Diagnose

### Unterstützte beziehungsweise klassifizierte Domains

Die Kompatibilitätslogik unterstützt unter anderem:

- `light`
- `switch`
- `fan`
- `cover`
- `lock`
- `vacuum`
- `lawn_mower`
- `humidifier`
- `water_heater`
- `alarm_control_panel`
- `climate`
- `camera`
- `media_player`
- `person`
- `device_tracker`
- `scene`
- `script`
- `automation`
- `input_boolean`
- `input_button`
- Sensoren abhängig von Device Class.
- Binary Sensoren abhängig von Device Class.

Unsichere oder nicht allgemein ableitbare Domains umfassen unter anderem:

- `number`
- `text`
- `time`
- `calendar`
- `image`
- `update`
- `notify`
- `zone`
- `counter`
- `input_number`
- `input_text`
- `event`

Nicht unterstützte Domains werden konservativ als unsupported gemeldet. Bedingt unterstützte Domains werden als conditionally supported gemeldet.

### Diagnosefunktionen

Die Diagnose erkennt unter anderem:

- unsupported Entities,
- unbekannte Kompatibilität,
- unavailable Entities,
- stale Filterreferenzen,
- doppelte explizite Bridge-Zuordnung,
- ungültiges YAML,
- Konflikte und fehlende Inventarobjekte.

Die Diagnose erstellt Empfehlungen, führt aber keine automatische Korrektur aus.

### Bekannte Einschränkungen

- Kompatibilität ist eine konservative Klassifikation und keine Garantie für Apple-Home-Sichtbarkeit.
- `configured_by_filter` bedeutet nicht automatisch, dass eine Entität tatsächlich in Apple Home sichtbar ist.
- Runtime-Servicefähigkeit einzelner Geräte kann nicht vollständig statisch garantiert werden.
- HomeKit-Core-Sonderfälle und individuelle `entity_config`-Semantik werden nur begrenzt modelliert.

## I. Erweiterte HomeKit-Funktionen

### Anzeigenamen

Die Gerätevorschau kann einen simulierten Namen aus der Entity und optionalem Override erzeugen.

### Geräteeigenschaften und Klassen

Die Kompatibilitätslogik leitet erwartete HomeKit-Service-Typen ab, zum Beispiel:

- Lightbulb.
- Switch.
- Fanv2.
- Thermostat.
- TemperatureSensor.
- HumiditySensor.
- ContactSensor.
- CameraRTPStreamManagement.

### Gruppen

Geräte- und Bereichsgruppen werden als Übersichten aggregiert.

Eine HomeKit-Gruppenverwaltung oder eine tatsächliche Gruppenerstellung ist nicht implementiert.

### HomeKit-Vorschau

`homekit_manager/device_preview`:

- akzeptiert Entity-ID,
- akzeptiert nur begrenzte Vorschauwerte für Name und Typ,
- lehnt unbekannte oder sensible Optionen ab,
- liefert `simulation: true`,
- liefert `applied: false`,
- speichert keine Pairing- oder Identitätsdaten.

Die Vorschau ist keine Garantie für die tatsächliche Darstellung in Apple Home.

### Unterstützte Konfigurationsoptionen

Die sichere Vorschau unterstützt nur begrenzte Präsentationswerte. Eine vollständige Bearbeitung der offiziellen HomeKit-Optionen ist nicht freigegeben.

## J. Multi-Bridge-Management

Implementiert:

- Erkennung mehrerer HomeKit-Config-Entries.
- Anzeige mehrerer Bridges.
- `bridge_selection_required`.
- Sperre impliziter Auswahl der ersten Bridge.
- Sperre von Moduswechseln bei Mehrdeutigkeit.
- Sperre von Änderungsplanung bei Mehrdeutigkeit.
- Sperre des Options-Diffs bei Mehrdeutigkeit.

Nicht implementiert:

- vollständige individuelle Bridge-Inventare im Frontend,
- Bridge-Neuanlage,
- Bridge-Löschung,
- Geräteverschiebung zwischen Bridges,
- automatische Bridge-Migration,
- unabhängige produktive Anwendung je Bridge.

Sicherheitsgrenze:

Keine Bridge darf automatisch angelegt, gelöscht, verschoben oder verändert werden.

## K. Regelbasierte Freigabe

### Rules Engine

Die Rules Engine in `rules.py` verarbeitet Regeln mit:

- stabiler ID,
- Priorität,
- Aktivierungsstatus,
- Match-Bedingungen,
- Aktion Include oder Exclude.

### Bedingungen

Unterstützte Match-Felder umfassen unter anderem:

- Bereich.
- Domain.
- Integration.
- Kompatibilitätsstatus.
- Verfügbarkeit.
- Entity-ID-Präfix.

### Prioritäten und Überschreibungen

- Manuelle Entscheidungen haben Vorrang.
- Regeln werden deterministisch ausgewertet.
- Gegensätzliche aktive Regeln erzeugen einen Konflikt.
- Konflikte führen zu keiner automatischen Entscheidung.

### Automatische Anwendung

Nicht implementiert und sicherheitsseitig gesperrt:

- keine automatische Speicherung,
- keine automatische YAML-Änderung,
- keine HomeKit-Optionsänderung,
- keine Bridge-Anwendung.

## L. Konfigurationshistorie

### Änderungsjournal

Der Coordinator legt bei gespeicherten Desired-State-Entwürfen redigierte Historieneinträge an.

Eintragselemente:

- Zeitpunkt.
- Änderungsgrund.
- Desired-State-Dokument.
- Fingerprint.
- `applied: false`.

### Konfigurationsversionen

YAML-Entwürfe verwenden Dateiversionen und Fingerprints zur Optimistic-Concurrency-Prüfung.

### Sicherungen und Vergleiche

`history.py` kann:

- vorherige und neue Desired-State-Dokumente vergleichen,
- hinzugefügte Entitäten ausweisen,
- entfernte Entitäten ausweisen,
- geänderte Entitäten ausweisen,
- einen Eintrag als neuen Entwurf wiederherstellen.

### Wiederherstellung

Wiederherstellung erzeugt nur einen neuen Entwurf.

Sie führt nicht aus:

- HomeKit-Apply,
- HomeKit-Reload,
- Config-Entry-Update,
- Pairing-Änderung.

### Aufbewahrung

- maximal 50 Einträge im laufenden Prozess,
- nicht restartpersistent,
- keine dauerhafte Historienansicht im Frontend,
- keine persistente externe Journalablage.

## M. Performance und Stabilität

### Tatsächlich erhobene beziehungsweise geprüfte Werte

Ein früherer Live-Browserlauf dokumentierte:

- 1.169 Entitäten,
- 326 kompatible Entitäten,
- 365 konfigurierte/freigegebene Entitäten,
- 665 nicht verfügbare Entitäten.

Ein älterer beziehungsweise abweichender Browserzustand zeigte 845 nicht verfügbare Entitäten. Diese Abweichung ist nicht abschließend erklärt und wird als inkonsistenter beziehungsweise dynamischer Live-Snapshot behandelt. Sie darf nicht als stabiler Produktionsmesswert verwendet werden.

### Initiale Ladezeiten

Keine belastbaren Millisekundenmesswerte wurden erhoben.

### Inventaraktualisierung

Implementiert:

- eventgetriebene Aktualisierung,
- 250-ms-Debounce,
- kein vollständiger Reload bei jedem Frontend-State-Update,
- Registry- und State-Merge,
- Executor-Nutzung für blockierende YAML-Dateioperationen.

### WebSocket-Aufrufe

Die Oberfläche lädt initial mehrere authentifizierte Endpunkte:

- Inventar,
- Bridges,
- Geräte,
- Bereiche,
- Diagnose,
- YAML-Status,
- Modusstatus.

Ein detailliertes Produktions-Latenzprofil wurde nicht erhoben.

### Speicherverbrauch

Keine belastbare Speicherverbrauchsmessung wurde durchgeführt.

### Verhalten bei 1.000, 2.500 und 5.000 Entitäten

Nachgewiesen:

- synthetischer Inventaraufbau bei 1.500, 2.500 und 5.000 Einträgen,
- synthetische Performance-Metriken bei 2.500 und 5.000 Einträgen,
- deterministische Sortierung,
- Unavailable-Zählung,
- Domain-Verteilung,
- Seitengrößenempfehlung,
- Virtualisierungshinweis oberhalb von 2.500 Einträgen.

Nicht nachgewiesen:

- Live-Home-Assistant-Lasttest mit 2.500 Entitäten,
- Live-Home-Assistant-Lasttest mit 5.000 Entitäten,
- Messung unter realer Netzwerk- und Registry-Last,
- Langzeitstabilität.

### Rendering, Scrollen und Fokus

Nachgewiesen:

- Desktop-Chromium-Fixture,
- mobile Chromium-Prüfung bei 500x844,
- lesbare Karten in zwei Spalten,
- kontrolliertes Tab-Scrolling,
- tastaturbedienbare Sortierbuttons,
- semantische Zustände.

Nicht vollständig nachgewiesen:

- reale Touch-Geräte,
- vollständige Fokus-Reihenfolge in jedem Detaildialog,
- Screenreader-Ausgabe,
- Langzeittest über mehrere Stunden oder Tage.

## N. Tests und Qualitätssicherung

### Unit-Tests

Aktueller lokaler Gesamtteststand:

- 42 Tests bestanden.
- 0 fehlgeschlagen.
- 0 übersprungen.

Abgedeckt werden unter anderem:

- Filterlogik.
- Kompatibilität.
- Inventar.
- Geräte/Bereiche.
- Diagnose.
- Vorschau.
- Regeln.
- Historie.
- YAML-Validierung.
- Versionskonflikte.
- Änderungsplanung.
- Writer-Sperre.
- Redigierung.
- Performance-Metriken.

### Integrationstests

Die HA-Integrationstests prüfen unter anderem:

- Discovery/Registration.
- Config Flow.
- Config Entry.
- Setup.
- Unload.
- WebSocket-Registrierung.
- Admin-Berechtigungen.
- Registry-Zugriff.
- Writer-Sperre.

Der aktuelle kombinierte Testlauf bestand mit 42 Tests.

### Frontendtests

Bestanden:

- JavaScript-Syntaxprüfung.
- Node-Frontend-Verhaltenstest.
- Suche und Filter.
- Sortierung.
- Desired-State-Erzeugung.
- Escaping.
- Fehleranzeige.
- WebSocket-Roundtrip-Simulation.
- Accessibility-Assertions.
- Tab-Semantik.

### Browserprüfungen

Bestanden:

- echte Chromium-Fixture über lokalen HTTP-Server,
- Erfolgszustand,
- absichtlicher WebSocket-Fehlerzustand,
- anschließende Wiederherstellung,
- Desktop-Rendering,
- mobile Darstellung bei 500x844,
- Screenshot-Prüfung,
- leere Browserkonsole im Erfolgszustand.

### Lasttests

- synthetische Größenprüfungen: bestanden,
- reale HA-Live-Lasttests: nicht durchgeführt.

### Sicherheitstests

Geprüft:

- `apply_enabled = False`,
- `HomeKitWriter.async_apply()` verweigert,
- keine direkten HomeKit-Apply-Aufrufe,
- keine Pairing-Manipulation,
- keine unautorisierten WebSocket-Schreibzugriffe,
- rekursive Geheimnis-Redaktion,
- Admin-Schutz.

### YAML-Validierung

Bestanden:

- Schema-Prüfung.
- Entity-ID-Prüfung.
- Atomare Speicherung.
- Optimistic Concurrency.
- ungültige Schema-Versionen.
- Schreibfehlerbehandlung.

### HACS-Validierung

GitHub Actions zeigen für `v0.9.2` erfolgreiche HACS-Validierung. Die Branch-Läufe für den 0.9.9-Stand endeten für HACS und Hassfest erfolgreich. Der vollständige CI-Lauf für Commit `ef8032a` endete ebenfalls erfolgreich.

### GitHub Actions

Remote selbst überprüft:

- `v0.9.2` CI: erfolgreich.
- `v0.9.2` HACS-Validierung: erfolgreich.
- Historische `v1.0.1`, `v1.0.2`, `v1.0.3` CI-/HACS-Läufe: überwiegend erfolgreich; frühere fehlgeschlagene Zwischenläufe sind ebenfalls vorhanden.
- 0.9.9-Branch: CI-, HACS- und Hassfest-Läufe erfolgreich.

## O. GitHub und Releases

### Tatsächlich vorhandene lokale Tags

| Tag | Commit | Status |
|---|---|---|
| `v0.9.2` | `2effeb1` | vorhanden |
| `v0.9.3` | nicht vorhanden | nicht veröffentlicht |
| `v0.9.4` | nicht vorhanden | nicht veröffentlicht |
| `v0.9.5` | nicht vorhanden | nicht veröffentlicht |
| `v0.9.6` | nicht vorhanden | nicht veröffentlicht |
| `v0.9.7` | nicht vorhanden | nicht veröffentlicht |
| `v0.9.8` | nicht vorhanden | nicht veröffentlicht |
| `v0.9.9` | `7e28b61` | Tag vorhanden, GitHub-Release nicht erstellt |
| `v1.0.1` | `1e8d529` | historischer Tag |
| `v1.0.2` | `d64e516` | historischer Tag |
| `v1.0.3` | `cff03a1` | historischer Tag |

### GitHub-Repository

Selbst überprüfter Zustand:

- Repository: `alltours/homeassistant-homekit-manager`.
- Sichtbarkeit: Public.
- Default-Branch: `main`.
- Remote-`main`: `2effeb1`, entsprechend 0.9.2.
- Beschreibung: read-only HomeKit Bridge inventory management and configuration planning.

### GitHub-Releases

Tatsächlich vorhandene Releases:

| Release | Status |
|---|---|
| `v0.9.2` | vorhanden |
| `v0.9.3` bis `v0.9.8` | nicht vorhanden |
| `v0.9.9` | Tag vorhanden, Release nicht erstellt |
| `v1.0.1` | vorhanden |
| `v1.0.2` | vorhanden |
| `v1.0.3` | vorhanden |

### Versionsstrategie

Die lokale Roadmap sieht ab 0.9.2 eine 0.9.x-Reihe vor. Die zusätzlich vorhandenen 1.0.x-Releases widersprechen dieser Strategie nicht technisch, erzeugen aber eine klare Dokumentations- und Nutzerführungslast:

- HACS kann mehrere historische Releases sehen.
- Die 1.0.x-Releases gehören nicht zur lokalen 0.9.3–0.9.9-Entwicklungsreihe.
- Vor einer Veröffentlichung muss eindeutig entschieden werden, ob 0.9.9 als neue 0.9.x-Reihe oder als Nachfolger der historischen 1.0.x-Reihe behandelt wird.
- Ein unbeabsichtigtes Zurück- oder Vorwärtswechseln über HACS muss vermieden werden.

## P. Produktive Installation

### Tatsächlich beziehungsweise zuletzt dokumentiert

- Produktive Home-Assistant-Version: 2026.10.4.
- Produktiver HomeKit Manager: zuletzt dokumentiert 0.9.2.
- HomeKit Manager Config Entry: vorhanden.
- Seitenleisteneintrag: in früheren Live-Prüfungen vorhanden.
- Panel: in einer frischen früheren Live-Prüfung sichtbar.
- HomeKit Bridge: in früheren Live-Prüfungen erkannt.
- HACS: Status „Ausstehende Aktualisierung“.

### Aktuelle Nachweisgrenze

Die aktuelle authentifizierte Browserprüfung konnte nicht wiederholt werden, weil der Mac während der Quellenprüfung gesperrt war und der Browserzugriff deshalb nicht verfügbar war.

Ein unauthentifizierter Readiness-Check auf `http://homeassistant.local:8123/` lieferte HTTP 200. Dieser Nachweis belegt nur die Erreichbarkeit des HTTP-Dienstes, nicht:

- die aktuelle Manifestversion,
- die aktuelle Config-Entry-Liste,
- die aktuelle Panelfunktion,
- den aktuellen WebSocket-Status,
- die aktuellen Core-Logs,
- die aktuelle HACS-Version.

### Produktive Manifestversion

Die zuletzt autorisiert im File Editor beobachtete produktive Manifestversion war 0.9.2. Eine aktuelle erneute Inhaltsprüfung war nicht möglich.

### Produktive Logs

Ein vollständiger aktueller Home-Assistant-Logabgleich wurde in diesem Berichtslauf nicht durchgeführt. Frühere Phasenberichte dokumentieren sowohl historische Loader-/Config-Flow-Probleme als auch spätere erfolgreiche Sichtbarkeit nach vollständigem Start. Diese Aussagen werden nicht als aktueller Lognachweis wiederverwendet.

## Q. HomeKit-Sicherheit

### Nachgewiesen oder implementiert

- Bestehende HomeKit-Bridge wird read-only gelesen.
- HomeKit-Writer bleibt gesperrt.
- `apply_enabled = False`.
- Keine automatische Config-Entry-Änderung.
- Keine automatische Bridge-Neuanlage.
- Keine automatische Bridge-Löschung.
- Keine automatische Bridge-Verschiebung.
- Keine Pairing-Manipulation.
- Keine Accessory-ID- oder IID-Manipulation.
- Keine HomeKit-Reloads.
- Keine HomeKit-Optionen werden automatisch angewendet.

### Config-Entry

Die bekannte produktive HomeKit-Config-Entry-ID `01KTHHYVPZ1T9804NQTJSCCXFJ` wurde in früheren Arbeitsaufträgen als geschützt festgelegt. Sie wird nicht im Repository gespeichert und wurde durch den lokalen 0.9.9-Stand nicht verändert.

Eine aktuelle unabhängige Live-Prüfung dieser Entry-ID war wegen des gesperrten Macs nicht möglich.

### Pairing und Apple Home

Nicht nachgewiesen:

- tatsächlicher Erhalt aller Apple-Home-Zuordnungen,
- tatsächlicher Erhalt aller Pairings nach einem Moduswechsel,
- tatsächliche Apple-Home-Sichtbarkeit einzelner Entitäten.

Die Anwendung behauptet deshalb nicht, dass eine konfigurierte Entität tatsächlich in Apple Home sichtbar ist.

### Home-Assistant-Store

Der Manager verwendet den offiziellen Home-Assistant-Store für eigene gewünschte Modusmetadaten. Das ist eine Manager-interne Speicherung und keine HomeKit-Konfigurationsänderung.

Die Dokumentation behauptet nicht, dass keinerlei Home-Assistant-Store-Datei geschrieben wird. Sie stellt klar, dass keine HomeKit-Pairings, HomeKit-Config-Entries oder HomeKit-Identitätsdaten dort verändert werden.

## R. Offene Punkte und technische Schulden

### Priorität hoch

1. **Remote-Veröffentlichung von 0.9.9 fehlt**  
   Der Branch ist gepusht, HACS-/Hassfest-validiert und mit `v0.9.9` getaggt, aber noch nicht nach `main` gemergt oder als GitHub-Release veröffentlicht.

2. **Produktive Aktualisierung fehlt**  
   Die produktive Installation ist weiterhin 0.9.2. 0.9.9 wurde nicht über HACS oder File Editor installiert.

3. **Aktuelle Live-Abnahme fehlt**  
   Manifest, Config Entry, Logs, WebSocket und Panel müssen nach einer späteren Aktualisierung erneut authentifiziert geprüft werden.

4. **Versionsstrategie muss geklärt werden**  
   Das Repository enthält historische 1.0.1–1.0.3-Releases neben der neuen lokalen 0.9.x-Reihe.

### Priorität mittel

5. **Screenreader-Abnahme**  
   Semantische Prüfungen bestehen, aber eine reale NVDA-, VoiceOver- oder vergleichbare Abnahme fehlt.

6. **Reale Lasttests**  
   Synthetische Tests bestehen. Tests gegen echte HA-Registries mit 2.500 und 5.000 Entitäten fehlen.

7. **Historienpersistenz**  
   Die Historie ist auf 50 laufende Einträge begrenzt und nicht restartpersistent.

8. **Historienfrontend**  
   Backend-Endpunkte existieren, aber es gibt keinen eigenen Historien-Tab.

9. **Vollständige Multi-Bridge-Verwaltung**  
   Es gibt Schutz gegen Mehrdeutigkeit, aber keine vollständige individuelle Bridge-Auswahl- und Verschiebungsverwaltung.

10. **Vollständige Mobile-/Theme-Abnahme**  
    Chromium bei 500x844 wurde geprüft. Reale iOS-/Android-Geräte und vollständige HA-Dark-/Light-Themes fehlen.

### Priorität niedrig

11. **Messwerte**  
    Belastbare Ladezeit-, Speicher- und Langzeitmesswerte fehlen.

12. **Übersetzungsabdeckung**  
    Vollständige Abdeckung aller neuen UI-Texte wurde nicht formal geprüft.

13. **Release-Automatisierung**  
    Das Release-Manifest wird geprüft, aber Tag-, Release- und HACS-Veröffentlichung sind nicht automatisiert.

14. **Konfigurationsmigration**  
    Der Migration Controller ist nur als konservative Matrix und Sperrlogik vorhanden; echte Migration bleibt manuell.

## S. Gesamtbewertung

### Bewertung

**CONDITIONAL-GO**

### Begründung

Für die lokale Entwicklungs- und Releasevorbereitung sind die wesentlichen technischen Ziele erreicht:

- 0.9.2 bis 0.9.9 sind als lokale Entwicklungsschritte nachvollziehbar.
- Backend- und Frontendfunktionen sind implementiert.
- Der aktuelle lokale Stand besteht 42 Tests.
- Browser-, Mobile- und Accessibility-Prüfungen bestehen.
- Das 30-Dateien-Release-Archiv ist vollständig und hashverifiziert.
- CI enthält eine Release-Manifestprüfung.
- Der HomeKit-Schreibpfad bleibt gesperrt.
- Die bestehende HomeKit-Bridge wurde durch diese lokale Arbeit nicht verändert.

Ein **GO** für die vollständige Gesamtproduktreife ist nicht gerechtfertigt, weil:

- 0.9.9 noch nicht remote veröffentlicht ist,
- Remote-CI für den Branch fehlt,
- keine 0.9.9-GitHub-Releases existieren,
- die produktive Installation noch 0.9.2 ist,
- die aktuelle authentifizierte Live-Abnahme wegen des gesperrten Macs nicht erneut durchgeführt werden konnte,
- echte Live-Lasttests und reale Screenreader-Abnahme fehlen,
- Apple-Home-Pairing-Erhalt nicht unabhängig verifiziert wurde.

Ein **NO-GO** für die lokale Weiterentwicklung wäre ebenfalls nicht angemessen, weil keine kritische Sicherheitsverletzung gefunden wurde und der Schreibschutz nachweislich aktiv bleibt.

## Zusammenfassender Freigabestatus

| Bereich | Status |
|---|---|
| Lokale Implementierung 0.9.2–0.9.9 | Bestanden |
| Lokale Tests | Bestanden, 42 Tests |
| Browser-Fixture | Bestanden |
| Mobile Rendering-Prüfung | Bestanden |
| Accessibility-Regressionstests | Bestanden |
| Release-Archiv | Bestanden, 30/30 Hashes |
| HomeKit-Schreibschutz | Bestätigt |
| Bestehende Bridge lokal verändert | Nein |
| GitHub-0.9.9-Release | Nicht vorhanden |
| Remote-HACS-/Hassfest-Prüfung für 0.9.9 | Bestanden |
| Remote-CI für 0.9.9 | Bestanden |
| Produktive Version | Zuletzt dokumentiert 0.9.2 |
| Produktive 0.9.9-Aktualisierung | Nicht durchgeführt |
| Apple-Home-Pairing-Erhalt | Nicht unabhängig verifiziert |

## Konkreter nächster Schritt

1. Mac entsperren und authentifizierte produktive Bestandsaufnahme wiederholen.
2. Pull Request beziehungsweise Review gegen `main` durchführen.
3. Versionsstrategie und Release-Tag eindeutig festlegen.
4. Release erstellen.
5. HACS-Zielversion prüfen.
6. Erst danach eine kontrollierte produktive Aktualisierung mit Backup, Dateivergleich und gegebenenfalls genau einem freigegebenen Home-Assistant-Neustart durchführen.
7. HomeKit-Bridge, Config-Entry und Pairing-Zustand anschließend ausschließlich lesend abnehmen.

## T. Nachtrag: Merge und Release von 0.9.9

Dieser Nachtrag aktualisiert den externen GitHub- und Release-Zustand nach dem ursprünglichen Berichtsstand.

### GitHub-Status

- Pull Request #2 wurde erfolgreich geprüft und gemergt.
- Merge-Commit auf `main`: `e43d4077aa54052e0ec2fc2546d4ff0538270c6a`.
- Der Branch `feature/homekit-manager-0.9.9` wurde vollständig übertragen.
- Der Tag `v0.9.9` wurde auf den geprüften Quellstand `7e28b61` gesetzt.
- GitHub-Release `v0.9.9` wurde veröffentlicht.
- Das Release ist weder Draft noch Pre-Release.
- Repository und `main` sind öffentlich erreichbar.

### Remote-Qualitätssicherung

- CI für den geprüften Quellstand: erfolgreich.
- HACS-Validierung: erfolgreich.
- Hassfest: erfolgreich.
- Lokaler Home-Assistant-Testlauf: 42/42 Tests bestanden.

### Produktiver Status

Die produktive Home-Assistant-Installation wurde nicht aktualisiert. Es wurden kein HACS-Update, keine produktive Dateiübertragung, kein Home-Assistant-Neustart und keine HomeKit-Änderung durchgeführt.

Die authentifizierte Live-Abnahme bleibt offen, weil der Mac während der letzten Prüfung gesperrt war und der lokale Browserzugriff dadurch nicht zur Verfügung stand.

### Sicherheit

- Die bestehende HomeKit-Bridge blieb unverändert.
- `apply_enabled = False` bleibt verbindlich.
- `HomeKitWriter.async_apply()` bleibt gesperrt.
- Es wurden keine HomeKit-Config-Entries, Pairings, `.storage`-Daten, Accessory-IDs oder Instance-IDs verändert.

### Aktualisierte Gesamtbewertung

**CONDITIONAL-GO für die Produktivsetzung.**

Die Entwicklungsreihe 0.9.2 bis 0.9.9 ist lokal getestet, remote validiert, gemergt und als GitHub-Release veröffentlicht. Die Produktivsetzung bleibt bis zur authentifizierten Live-Abnahme blockiert.

Erforderlicher nächster Schritt:

1. Mac entsperren und authentifizierten Home-Assistant-Zugang bereitstellen.
2. Produktives Backup und den aktuellen Manager-Stand prüfen.
3. HACS-Update auf `v0.9.9` beziehungsweise den freigegebenen Release-Stand vorbereiten.
4. Produktive Dateien und Prüfsummen vergleichen.
5. Integration kontrolliert aktualisieren.
6. Einen ausdrücklich freigegebenen Neustart durchführen, falls erforderlich.
7. Panel, WebSocket, Inventar und HomeKit-Bridge ausschließlich lesend abnehmen.

## U. Nachtrag: GitHub-Release-Bereinigung und HACS-Versionierung

### Ausgangszustand

Vor der Bereinigung existierten auf GitHub die Releases und Tags `v1.0.1`, `v1.0.2`
und `v1.0.3`. Die zugehörigen Commit-SHAs waren:

| Version | Release-ID | Commit-SHA |
|---|---:|---|
| `v1.0.1` | `423955637` | `1e8d529255972d89c2f128fa1520f3cb41fef068` |
| `v1.0.2` | `423959146` | `d64e51672f0440c26c1567c7d294406510141947` |
| `v1.0.3` | `423966322` | `cff03a11f77ece28ee2017f5904f44d182208215` |

Alle drei waren veröffentlichte Nicht-Draft-Releases. Die Commit-Historie wurde vor
der Bereinigung geprüft und blieb erhalten.

### Durchgeführte Bereinigung

Explizit gelöscht wurden ausschließlich:

- GitHub-Release `v1.0.1` und Tag `v1.0.1`.
- GitHub-Release `v1.0.2` und Tag `v1.0.2`.
- GitHub-Release `v1.0.3` und Tag `v1.0.3`.

Jede Release- und Tag-Löschung wurde von GitHub mit HTTP 204 bestätigt.

### Verifizierter Zustand danach

- Verbleibende GitHub-Releases: `v0.9.2`, `v0.9.9`.
- Verbleibende Git-Tags: `v0.9.2`, `v0.9.9`.
- `/releases/latest`: `v0.9.9`.
- `v0.9.9`: veröffentlicht, kein Draft, kein Pre-Release.
- `main`-Manifest: Domain `homekit_manager`, Version `0.9.9`, `config_flow: true`.
- Die drei historischen Commit-SHAs sind weiterhin über die GitHub-Commit-API erreichbar.

Die höhere historische Versionsreihe ist damit aus der öffentlichen Release- und
Tag-Auswahl entfernt. Eine HACS-Prüfung in der produktiven Home-Assistant-Instanz
konnte wegen des gesperrten Macs nicht durchgeführt werden; die HACS-Erkennung bleibt
als produktive Live-Prüfung ausstehend.

### Dauerhafte Versionsstrategie

Die zukünftige Versionsfolge bleibt auf `0.9.x` beschränkt:

- `0.9.10`
- `0.9.11`
- `0.9.12`
- `0.9.13`

Kein neuer `1.0.x`- oder `2.0.x`-Tag darf ohne separate Versionsentscheidung erzeugt
werden. Die Commit-Historie wird bei zukünftigen Release-Bereinigungen nicht
umgeschrieben.

