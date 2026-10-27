# HomeKit Manager 0.9.20 – Abschlussbericht zum lokalen Release-Kandidaten

Datum: 27.10.2026. Statuswörter in diesem Bericht: **BESTÄTIGT** = direkt im Quellcode, isolierten Test oder lesenden Zugriff nachgewiesen; **NICHT BESTÄTIGT** = behauptet oder plausibel, aber ohne erforderliche Produktionsdaten; **NICHT GETESTET** = absichtlich nicht ausgeführt oder keine geeignete Umgebung; **FEHLGESCHLAGEN** = ausgeführter Test oder Schritt mit negativem Ergebnis. Technische Hypothesen sind ausdrücklich als solche bezeichnet.

## 1. Executive Summary

**BESTÄTIGT:** Version 0.9.20 wurde aus dem Referenzcommit `4a4e73434e57ce3c1e66ae7f700c3d05328b7e97` auf `feature/homekit-manager-0.9.20` entwickelt. Der lokale ZIP-Kandidat enthält 38 Integrationsdateien; Manifest und ZIP stimmen byteweise überein. Die produktive HomeKit-Apply-Sperre bleibt serverseitig und im Panel aktiv. Inventarstatus, Geräte-ID-Aufschlüsselung und Bridge-bezogene Diagnose wurden verbessert. Der reine 1.172-Entitäten-Rechenpfad fiel im isolierten 100-Runden-Test von 52,230 auf 48,561 ms Median. Ein source-spezifisches Architekturkonzept und eine Konvertierungsmatrix liegen vor; eine Migration ist nicht freigeschaltet.

**NICHT BESTÄTIGT:** Ursache und Identität der acht produktiv abweichenden Geräte-IDs; produktive Refresh-Frequenz nach 0.9.20; tatsächlich veröffentlichte HomeKit-Accessories. **NICHT GETESTET:** Pairing-Erhalt, Apple Home, wiederholte Quellenwechsel, produktive Installation. Der Kandidat ist lokal prüfbar, aber keine Freigabe für eine produktive Installation oder Migration.

## 2. Ausgangszustand und autoritative Basis

Repository: `/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager`, Origin `https://github.com/alltours/homeassistant-homekit-manager.git`. Verifiziertes Start-HEAD `4a4e734` auf dem vorhandenen 0.9.19-Worktree; neuer Entwicklungs-Worktree im kanonischen Repository unter `.worktrees/feature-homekit-manager-0.9.20`. Nicht versionierte Kopien im Homeassistant-Arbeitsordner wurden nicht als Produktbasis verwendet. Der kanonische Hauptcheckout hatte eigene unversionierte Dateien und blieb unangetastet. Kein Merge auf `main`, kein Tag und keine Veröffentlichung.

Vom Nutzer berichteter Produktionsstand: Home Assistant Core 2026.10.4, HomeKit Manager 0.9.19, eine native `source=user`-Bridge im Bridge-Modus auf Port 21064. Diese Angaben waren eine Ausgangsinformation, keine erneute Bestätigung über eine authentifizierte Registry-API.

## 3. Tatsächlich untersuchte Produktivumgebung

**BESTÄTIGT:** `http://192.168.1.136:8123/api/` antwortete lesend mit HTTP 401; der Server war erreichbar, verlangte aber Authentisierung. Der autorisierte Home-Assistant-Live-Context lieferte einen begrenzten Überblick von Namen und States, darunter `unavailable`, jedoch keine vollständigen Entity-/Device-Registry-IDs, HomeKit-Config-Entry-Metadaten oder Event-Zähler. In der verfügbaren Browser-Sitzung war kein authentifiziertes Home-Assistant-Tab vorhanden. Es wurden keine Zugangsdaten gesucht oder umgangen.

**NICHT BESTÄTIGT:** Die aktuelle Installation der Version 0.9.19, der Core-Build, die eine Bridge, Port 21064 und die berichteten Produktionszahlen wurden nicht über authentifizierte API-Daten unabhängig verifiziert. **BESTÄTIGT:** Keine produktive HomeKit-Option, Config Entry, `.storage`-Datei, YAML-Datei oder Bridge wurde verändert oder neu geladen; kein produktiver Dienst wurde neu gestartet.

## 4. Inventar-Befunde und 5. Ursache der Gerätedifferenz

0.9.19 zählte für `device_count` unterschiedliche `device_id`-Referenzen aus Entity-Registry-Einträgen. Der native Core-WebSocket `config/device_registry/list` serialisiert dagegen die enumerierbaren Haupt- und Kindgeräte. Der installierte Core 2026.10.4 kann beim Aufruf von `DeviceRegistry.async_get(id)` zusätzlich eine frühere Composite-ID synthetisch rekonstruieren; diese ID ist bewusst nicht in der enumerierbaren nativen Geräteliste. **BESTÄTIGT:** Das ist ein konkreter Unterschied der Zählkriterien, kein zwingender Registry-Fehler. Eine isolierte Fixture mit 121 Hauptgeräten und acht Composite-Referenzen reproduzierte exakt 129 gegen 121 ohne fehlende Geräte. Auch die umgekehrte Differenz ist möglich, wenn Registry-Geräte keine Inventar-Entität besitzen. UI-Suche, Integrations- und Sichtbarkeitsfilter können weitere Unterschiede erzeugen.

0.9.20 meldet `referenced_device_count`, `registered_referenced_device_count`, `native_registry_device_count`, `native_registry_devices_without_inventory`, `composite_reference_ids`, `missing_reference_ids` und `unlisted_reference_ids`. Die Oberfläche zeigt die wesentlichen Nenner an. Fehlende Referenzen und synthetische Composite-IDs werden getrennt. **NICHT BESTÄTIGT:** Ob genau die acht produktiven IDs Composite-IDs, fehlende Referenzen, UI-Filtereffekte oder eine Kombination sind. Ihre Kennungen konnten mangels lesenden vollständigen Registry-Zugriffs nicht ermittelt werden. Es wurde keine ID gelöscht und kein Zählwert auf 121 erzwungen. Ein späterer lesender Abgleich benötigt gleichzeitig: Entity Registry, Device Registry einschließlich Kindgeräten und Composite-Splits, State Machine, Manager-Snapshot und denselben UI-Filterzustand.

## 6. Implementierte Inventar- und Diagnosekorrekturen

Die sechs exklusiven Statusklassen werden in dieser Reihenfolge bestimmt:

| Kategorie | Eindeutige Evidenz |
|---|---|
| Deaktiviert | Entity oder zugehöriges Gerät in der Registry `disabled_by != None`. |
| Verwaist | Entity referenziert eine Device-ID, die eine verfügbare Device Registry definitiv nicht auflösen kann. |
| Ohne aktuellen State | Registry-Entität vorhanden, aber kein State-Machine-Eintrag. |
| unavailable | Aktueller HA-State ist wörtlich `unavailable`. |
| unknown | Aktueller HA-State ist wörtlich `unknown`. |
| Verfügbar | Jeder andere aktuelle State. |

Fehlt die Device Registry als Prüfquelle, wird keine Verwaisung behauptet. State-only-Entitäten ohne Device-ID sind ebenfalls nicht verwaist. Die rohen Felder `state`, `disabled_by` und `device_registry_status` bleiben zur Nachprüfung erhalten. Die UI bietet die sechs Statuswerte als Filter und zeigt sie je Entität an. `active_entities` und `disabled_entities` berücksichtigen jetzt auch eine Deaktivierung des Geräts.

Die Kompatibilitätsdiagnose trennt Inventarpräsenz, Filtereinschluss, technische Unterstützung, tatsächliche Publikation und Apple Home. `published` und `apple_home_visible` bleiben ohne eigenen Nachweis `unknown`. Eine nicht unterstützte Entität ist nur dann ein kritischer Bridge-Befund, wenn der Filter der ausgewählten Bridge sie ausdrücklich einschließt; bei Ausschluss oder unbekanntem Filter ist sie ein Inventarhinweis. Bedingte Unterstützung und Nichtverfügbarkeit erzeugen Bridge-Warnungen nur bei bestätigtem Einschluss. Explizite Aufnahme in zwei Bridges ist eine Warnung, weil Mehrfachveröffentlichung absichtlich sein kann. `SOURCE_IMPORT` plus passende YAML-Konfiguration wird nicht mehr als zweite native Quelle fehlgedeutet. Alle Bewertungen bleiben read-only.

## 7. Performance-Vergleich und Messgrenzen

Produktiv-Audit als **NICHT erneut BESTÄTIGTER** Ausgangswert: 1.172 Entitäten, etwa 320 ms pro vollständigem Refresh und 368 zusätzliche Refreshes in etwa zehn Minuten. Ohne authentifizierte Event- und Performance-Daten sind Auslöser und produktive Nachher-Werte nicht messbar. Die bisherige Architektur lauschte auf `state_changed`, drei Registry-Ereignisse und `homekit_state_change`; sie koaleszierte auf etwa einen Vollrefresh pro Sekunde. Ein HomeKit-Aktionsereignis ohne State-/Registry-Änderung ist für das Inventar redundant und wurde als Trigger entfernt. Identische alte/neue State- und Attributwerte werden nun gezählt und ignoriert. Relevante Events werden weiterhin vollständig und atomar verarbeitet; Events während Executor-I/O gehen nicht verloren.

| Isolierter gemeinsamer Rechenpfad, Core 2026.10.4, 1.172 Entitäten, 129 Geräte-Referenzen, 100 Runden | 0.9.19 | 0.9.20 |
|---|---:|---:|
| Wall-Median | 52,230 ms | 48,561 ms |
| Wall-p95 | 53,219 ms | 49,635 ms |
| CPU-Median | 52,232 ms | 48,563 ms |
| `tracemalloc`-Peak | 2.202.914 Byte | 2.300.761 Byte |

**BESTÄTIGT:** 7,0 % kürzere Median-Rechenzeit nach gezielter Vermeidung der vollständigen `dataclasses.asdict`-Kopie; 4,4 % höherer Python-Allocation-Peak wegen zusätzlicher Klassifikationsdaten. Das ist weder Prozess-RSS noch ein voller HA-/WebSocket-/Browser-Refresh und darf nicht mit den 320 ms gleichgesetzt werden. In der isolierten Event-Fixture führten 100 identische und 25 geänderte State-Ereignisse zu einer vollständigen Neuberechnung; alle 125 Events wurden erfasst. Neue Live-Zähler zeigen Eventtypen, ignorierte Events, Refresh-Anforderungen, abgeschlossene Vollberechnungen, Wall-/CPU-Zeit und fünf Phasen. Damit kann die produktive 320-ms-Lücke nach einer später autorisierten Installation lokalisiert werden.

Frontend: Ein automatischer Snapshot-Abruf löst nur noch ein Rendering aus. Trifft während eines laufenden WebSocket-Abrufs eine höhere Revision ein, folgt ein weiterer Abruf; eine fehlgeschlagene Anfrage erzeugt keine Endlosschleife. Zwei Browserläufe zeigten für 5.000 synthetische Entitäten eine begrenzte 80-Zeilen-Seite mit 25,1–31,1 ms in Chromium und 43,0–46,0 ms in WebKit in der lokalen Testumgebung. Diese Werte sind keine Produktionsmessung.

## 8. Neue Konfigurationsarchitektur

Jede Bridge hat langfristig genau eine wirksame Quelle: native `SOURCE_USER`-Konfiguration oder YAML mit `SOURCE_IMPORT`. Der Manager-Entwurf ist nur ein temporärer Plan. Vorgeschlagen wird ein unveränderliches gemeinsames Modell mit Core-Version, Bridge-/Entry-ID, Quelle, getrennten `data`/`options`, effektivem Filter, `entity_config`, Modus, Name, Port, unbekannten Feldern, Herkunftspfad und Revision/Hash. Beide Adapter sollen `discover`, `read_snapshot`, `capabilities`, `validate`, `compare`, `plan` und `verify` anbieten. Die technischen Schreib- und Reload-Grenzen bleiben adapter-spezifisch. In 0.9.20 sind diese Adapter ein dokumentierter Entwurf, kein aktiver Writer.

Ein Änderungsplan muss ein eindeutiges Ziel, Feld-Diff, unveränderte Felder, nicht abbildbare Optionen, erwartete Revision, Validierung, Seiteneffekte, Identitätsrisiko, Backup und Nachprüfungen enthalten. Konflikte (geänderter Entry/File-Hash, anderer Include-Graph, mehrdeutige Bridge, Port-/Namenskollision, Versionenwechsel, unbekanntes Feld oder fehlende Berechtigung) führen zu Abbruch und erneuter lesender Prüfung. Ein unbekanntes Anwendungsergebnis darf nicht automatisch wiederholt werden.

## 9. NativeHomeKitAdapter-Konzept

`config_entries.async_entries("homekit")` liefert Entries; `source=user` und `source=import` sind getrennt zu behandeln. `data` und `options` müssen getrennt gelesen und erst für die effektive Sicht kombiniert werden. Native Options Flows sind der von HomeKit selbst angebotene Bedienweg. `hass.config_entries.async_update_entry(entry, options=...)` ist ein dokumentiertes Core-API für Änderungen an `data/options`, jedoch kein Beleg, dass ein fremdes Custom-Component damit jeden HomeKit-Options-Flow sicher ersetzen darf. In Core 2026.10.4 löst der HomeKit-Update-Listener für User-Entries einen Reload aus; für Import-Entries nicht. Reload und alle Optionen-Schreiboperationen bleiben in 0.9.20 gesperrt. Der Adapter müsste später Core-Schema, Flow-Abdeckung und genau einen Entry validieren; die Aktivierung erst nach Reload und tatsächlichem Effekt belegen.

## 10. YamlHomeKitAdapter-Konzept

Die maßgebliche Datei kann `configuration.yaml`, eine direkte `!include`-Datei, eines der vier `!include_dir_*`-Ergebnisse, eine verschachtelte Include-Kette oder ein Package sein. Mehrere HomeKit-Bridges können in einer Liste liegen. Eine Datei darf nur als Ziel gelten, wenn der vollständige Include-Graph, die konkrete Bridge-Zuordnung über eindeutigen Namen/Port und die aktive importierte Config Entry-Konfiguration konsistent sind. Der bestehende textuelle Quellen-Inspector ist nur ein Hinweis. Unklare Zuordnung, Symlinks außerhalb des Config-Verzeichnisses, `!secret`, Anker/Aliase, unbekannte Tags oder zusammengeführte Verzeichnisse blockieren automatisches Bearbeiten.

Ein zukünftiger YAML-Writer benötigt Berechtigungsprüfung, erwartete Bytes/Hashes jedes beteiligten Knotens, dateigleichen temporären Schreibort, fsync, atomaren Austausch, verifiziertes Backup und eine kommentartreue Bearbeitung. Generisches PyYAML-Neuschreiben ist dafür ungeeignet. Auf einer isolierten Kopie müssen das Core-HomeKit-Schema und `hass --script check_config` bestehen. Erst danach käme ein bewusst ausgelöster `homekit.reload` in Frage, der laut offizieller Dokumentation nur YAML-Instanzen betrifft. 0.9.20 ruft ihn nicht auf. Nach einer zukünftigen Übernahme wären importierte Entry-Werte und tatsächlicher Filter zu vergleichen; Dateirücknahme allein beweist weder HAP- noch Apple-Home-Wiederherstellung.

## 11. Bidirektionale Konvertierungs-Kompatibilitätsmatrix

„Verlustfrei“ bezieht sich nur auf den Konfigurationswert und ein gültiges Ziel-Schema, niemals auf Bridge-Identität oder Pairing. „Native“ meint den unterstützten HomeKit-UI-Flow; private Options-Injektion zählt nicht als unterstützte Konvertierung.

| Feld / Gruppe | Native → YAML | YAML → native UI | Grenze |
|---|---|---|---|
| `include_domains` / `exclude_domains` | Verlustfrei | Mit Einschränkungen | UI-Flow kann gemischte Filter umformen. |
| `include_entities` / `exclude_entities` | Verlustfrei | Mit Einschränkungen | Effektiven Filter nach Umformung vergleichen. |
| `include_entity_globs` / `exclude_entity_globs` | Verlustfrei | Mit Einschränkungen | Nicht jede Kombination ist im UI-Flow darstellbar. |
| `entity_config.name` | Verlustfrei | Nicht allgemein übertragbar | Apple Home kann den ersten Namen zwischenspeichern. |
| `entity_config` Batterie-, Lade-, Türgong-, Feuchte-, Bewegungs-, Temperatur-, PM2.5-, Filter-, Hindernis- und Ventil-Verknüpfungen | Verlustfrei, wenn domänenschema-gültig | Nicht allgemein übertragbar | Native UI deckt nur Teilmengen ab. |
| `entity_config` Schwellenwerte, Codes, Media-`feature_list`, Schalter-/Ventil-/Lüfter-`type` | Verlustfrei, wenn domänenschema-gültig | Nicht allgemein übertragbar | Domänenspezifische Validierung erforderlich. |
| Klima-`entity_config.type` | Verlustfrei | Mit Einschränkungen | Thermostat/HeaterCooler im aktuellen UI-Flow. |
| Kamera-Stream/Codec/Audio/Video-/Paket-/Profiloptionen | Verlustfrei, wenn domänenschema-gültig | Nicht allgemein übertragbar | Separate Accessory-Instanz und Laufzeitfähigkeiten nötig. |
| `mode=bridge` | Verlustfrei als Wert | Mit Einschränkungen | Entry-Erzeugung und HAP-Identität separat. |
| `mode=accessory` und eine Entität | Mit Einschränkungen | Mit Einschränkungen | Genau eine Entität, eigener Entry/Pairing. |
| `name`, `port` | Verlustfrei als Werte | Mit Einschränkungen | Eindeutigkeit, freier Port, Discovery. |
| `ip_address`, `advertise_ip` | Verlustfrei, falls vorhanden | Nicht über UI übertragbar | Dokumentierte YAML-Felder. |
| `devices`-Triggerliste | Verlustfrei, falls schema-gültig | Mit Einschränkungen | UI-Flow kann neu ableiten. |
| YAML-Includes, Kommentare, Anker, Secrets, Formatierung | Nicht anwendbar | Nicht übertragbar | Quellstruktur statt Entry-Option. |
| `SOURCE_USER`/`SOURCE_IMPORT`, Entry-ID | Nicht übertragbar | Nicht übertragbar | Entry-Metadaten, keine HomeKit-Option. |
| HAP-State/MAC, Pairings, AID/IID | Nicht übertragbar | Nicht übertragbar | Eigenständige Persistenz. |
| Unbekannte oder neue Keys | Unbekannt – blockieren | Unbekannt – blockieren | Keine stillschweigende Entfernung. |

Die vollständige Core-2026.10.4-Unterfeldliste und die technischen Nachweise stehen im Architektur-Dokument `docs/HOMEKIT_MANAGER_0_9_20.md`. Jede zukünftige Konvertierung muss alle ausgangsseitigen Keys mit Status und eventuellem Wertverlust in einem expliziten Diff auflisten; bei „unbekannt“ wird nicht angewendet.

## 12. Machbarkeit des Pairing-Erhalts

**BESTÄTIGT im Core-Code:** HomeKit benennt `.storage/homekit.<entry_id>.state`, `.aids` und `.iids` nach der Entry-ID. Der HAP-Treiber lädt Zustand und MAC aus der entry-spezifischen State-Datei; das Entfernen des HomeKit-Entries entfernt alle drei Dateien. Der öffentliche `async_update_entry`-Aufruf besitzt keinen `source`-Parameter. HomeKits YAML-Abgleich berücksichtigt nur Entries mit `SOURCE_IMPORT` und matcht Name/Port. Der Options-Flow verzweigt nach `SOURCE_IMPORT`. Ein bestehender `SOURCE_USER`-Entry lässt sich folglich nicht über eine unterstützte API einfach zur YAML-Quelle umstellen. Eine direkte Attribut-/Storage-Manipulation wäre ein interner Eingriff, besonders riskant bei Reload oder Core-Neustart.

**Hypothese, NICHT BESTÄTIGT:** Wenn ein bestehender Entry samt State-Dateien, Port, HAP-MAC und Accessory-Zuordnungen erhalten bliebe, könnte Pairing unter bestimmten Bedingungen fortbestehen. Das ist weder eine unterstützte Quellenmigration noch ein Apple-Home-Nachweis. Änderungen an Entity-IDs, Geräte-Gruppierung oder HomeKit-Typen können AID-/IID-Zuordnungen oder Apple-Home-Automationen beeinflussen. **NICHT GETESTET:** eine echte isolierte Apple-Home-Kopplung und Migration.

## 13. Risiken wiederholter Migrationen

Für UI → YAML → UI → YAML → UI wären eine unterstützte Quellenumschaltung oder eine verlustfreie, identitätserhaltende Neuverknüpfung, stabile Entry-ID/Persistenz, eindeutige Name-/Port-Zuordnung, unveränderte AID/IID, sichere Reload-/Neustart-Reihenfolge und eine Apple-Home-Abnahme nach jedem Schritt erforderlich. Diese Voraussetzungen sind in Core 2026.10.4 nicht vollständig nachgewiesen. Bei YAML-Import eines bestehenden User-Entries drohen stattdessen zweiter Entry, Portkonflikt oder neue HAP-Identität. Beim Löschen eines Entries droht dokumentiert der Verlust der entry-spezifischen Persistenz. **NICHT GETESTET:** Wiederholmigrationen. Eine erfolgreiche reine Konfigurationskonvertierung wäre kein Pairing-Beweis.

## 14. Architekturentscheidung

Bewertung: H = günstig/hoch, M = mittel, N = ungünstig/niedrig, ? = unbekannt; Aufwand/Risiko: H bedeutet hoch.

| Ansatz | Sicherheit | Wartbarkeit | HA-Kompatibilität | Pairing-Erhalt | Migration | Fehlerbehandlung/Wiederherstellung | Benutzerfreundlichkeit | Aufwand | Update-Risiko |
|---|---|---|---|---|---|---|---|---:|---:|
| A: bestehende Quelle direkt verwalten | H mit Gates | M/H | H bei offiziellen Pfaden | Keine Quelle geändert | N | M/H mit quellenspezifischem Backup | H | M | M |
| B: Entry erhalten, Quelle umstellen | N | N | N, keine öffentliche Source-Mutation | ? | H theoretisch | N | M, falls es ginge | H | H |
| C: Export in neue Bridge | M | H | H für Neuanlage | Neue Kopplung zu erwarten | M | M/H bei alter Bridge als Rückfall | M | M | M |
| D: YAML maßgeblich, Manager verwaltet Datei | M bei eindeutiger Quelle | M | M | Keine Quelle geändert | N | M, Include-/Formatkonflikte | H | H | M |

**Entscheidung:** A als Grundlage; D ist die YAML-Ausprägung von A. B bleibt Forschung und wird nicht aktiviert. C kann später ein ausdrücklich neuer-Identität-Export sein, nicht eine Pairing-erhaltende Migration. 0.9.20 enthält nur sichere Lese-, Planungs- und Inventaränderungen; die produktive Apply-Sperre bleibt.

## 15. Tests und Freigabegates

**BESTÄTIGT:** 118 Python-Tests bestanden auf dem aus dem endgültigen ZIP in ein temporäres Verzeichnis extrahierten Integrationsquellstand; Testwerkzeuge und `pytest.ini` wurden für diesen Prüfaufbau kopiert, die temporäre Umgebung danach entfernt. Die Suite enthält echte isolierte HA-WebSocket-/Browser-Backend-Fälle, Multi-Bridge-Drafts, YAML-`!include` und `!include_dir_merge_list`, Core-Config-Entry- und Identitätsverträge, Registry-/State-Konsistenz, Berechtigungen, unbekannte Aktivierungszustände, Writer-Sperre, Fehler und Timeout. Der Frontend-Unit-Test bestand. 38 Responsive-/Screenshot-/Workflow-Browsertests bestanden in Chromium und WebKit. Zwei weitere Browsertests beobachteten das Panel je fünf Minuten; in beiden blieb `renderCount` von 3 auf 3, bei 12 Fixture-Kommandos. `npm ci` meldete null Advisory-Treffer; Python- und JS-Syntaxprüfungen bestanden. Die aktualisierte GitHub-Actions-Konfiguration pinnt Ubuntu 24.04, das Playwright 1.55 unterstützt, und nutzt für Browserläufe einen Worker. **NICHT GETESTET:** ein tatsächlicher GitHub-Actions-Lauf des unveröffentlichten Branches und ein physisches iPhone.

**BESTÄTIGT:** Der Admin-WebSocket `apply_options_diff` antwortete in isolierten HA-Tests mit `write_blocked`; native Options blieben unverändert. Ein Non-Admin wurde von allen Manager-Kommandos abgewiesen. Der Coordinator wirft vor Validierung oder Writer-Aufruf `HomeKitWriteDisabled`, auch bei alter oder neuer Request-ID. **FEHLGESCHLAGEN und behoben:** Ein erster temporärer ZIP-Testlauf ohne die benötigte `pytest.ini` aktivierte die HA-Async-Fixtures nicht; mit vollständigem Prüfaufbau bestanden alle 118 Tests. Es gibt keine ungelösten Testfehler.

## 16. Release-Artefakt und SHA-256

Lokaler Pfad: `/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager/.worktrees/feature-homekit-manager-0.9.20/.release/0.9.20-rc/homekit-manager-0.9.20.zip`.

SHA-256: `0ccf8de24cd6ce99ec8ff0a53b8a3d63f75ababb3079da52055484a48129bb68`.

**BESTÄTIGT:** Zwei unabhängige Builds lieferten identische Bytes; das ZIP enthält 38 Integrationsdateien plus Release-Manifest, dessen Einzelhashes gegen die Quellbytes geprüft wurden. Die Release-Datei ist lokal und Git-ignoriert. Versionsnummer, Integrationsmanifest, Paketversion, Changelog, README, Architektur-Dokument, Tests und CI-Archivname wurden auf 0.9.20 gebracht. Kein Tag, Push, GitHub-Release, Merge oder produktives Deployment.

## 17. Offene Probleme und Nachweislücken

1. **NICHT BESTÄTIGT:** acht konkrete produktive IDs und tatsächliche Ursache der 129/121-Differenz. Erforderlich ist ein zeitgleicher authentifizierter, ausschließlich lesender Export der Device-/Entity-Registries, States, Composite-Splits und aktiven UI-Filter.
2. **NICHT BESTÄTIGT:** produktive Refresh-Quellen, Wall-/CPU-/RSS-Verlauf, WebSocket-Menge und Nachher-Frequenz. Die neue Instrumentierung ist lokal getestet, aber nicht installiert.
3. **NICHT GETESTET:** tatsächliche HAP-Publikation, Apple-Home-Sichtbarkeit, Pairing-Erhalt und AID/IID-Stabilität bei Migration.
4. **NICHT BESTÄTIGT:** allgemeine automatische Editierbarkeit komplexer YAML-Include-/Package-Graphen und unbekannter künftiger Core-Optionen. Der YAML-Adapter ist deshalb noch kein Writer.
5. **NICHT GETESTET:** CI auf GitHub, physisches iPhone und produktive Core-2026.10.4-Regressionsmessung. Der lokale Kandidat bleibt ohne Publikation und Installation.

## 18. Empfohlene Roadmap

| Version | Schwerpunkt und Gate |
|---|---|
| 0.9.21 | Nach autorisiertem lesendem Registry-Zugriff die acht IDs und UI-Filter exakt abgleichen; produktive Event-/Phasenmetrik ohne HomeKit-Schreiboperationen erfassen; Rest-RSS messen. |
| 0.9.22 | Gemeinsames unveränderliches Konfigurationsmodell und ausschließlich lesende Native-/YAML-Adapter implementieren; Include-Graph, mehrere Bridges, Feldprovenienz und vollständige Konvertierungs-Diffs testen. |
| 0.9.23 | Quellenspezifische Validatoren und transaktionale Pläne in isolierten HA-Instanzen entwickeln; YAML-Kommentarerhalt, Konflikt-/Backup-/Rollback-Szenarien und Core-Updates prüfen; produktive Sperre beibehalten. |
| 0.9.24 | Nur bei verfügbarer isolierter Apple-Home-Testumgebung Identität, Pairing, AID/IID, Reload, Neustart und wiederholte Wechsel untersuchen; danach getrennte Entscheidung über unterstützte Schreibpfade oder einen expliziten neue-Bridge-Export treffen. |

Quellen: [HomeKit Bridge](https://www.home-assistant.io/integrations/homekit/), [YAML-Includes](https://www.home-assistant.io/docs/configuration/splitting_configuration), [HomeKit-Reload](https://www.home-assistant.io/actions/homekit.reload/), [Config Check](https://www.home-assistant.io/docs/tools/check_config/), [Config-Entry-Updates](https://developers.home-assistant.io/blog/2024/02/12/async_update_entry/), [Playwright CI](https://playwright.dev/docs/ci) und [Playwright 1.54/1.55 Release Notes](https://playwright.dev/docs/release-notes). Exakte Core-2026.10.4-Verhaltensnachweise stammen aus dem lokal installierten Home-Assistant-Quellcode in `homeassistant/components/homekit/{__init__,config_flow,util}.py`, `homeassistant/config_entries.py`, `homeassistant/helpers/device_registry.py` und `homeassistant/components/config/device_registry.py`. Es wurden keine Produktionsdateien als Quelle kopiert oder verändert.
