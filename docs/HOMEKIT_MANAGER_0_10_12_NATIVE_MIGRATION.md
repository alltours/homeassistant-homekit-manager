# HomeKit Manager 0.10.12 – Native-Quellenmigration: Tiefenanalyse

## Ergebnis

Die isolierte Untersuchung zeigt einen wichtigen Unterschied zwischen
technischer Machbarkeit und verantwortbarer Produktfunktion:

- **CODE VERIFIED:** Home Assistant Core 2026.10.4 und 2026.11.0b0 speichern
  `ConfigEntry.source` getrennt von `entry_id`; in einem strikt isolierten
  Test kann die Quelle intern umgestellt werden.
- **TEST VERIFIED:** Ein echter isolierter HAP-Controller konnte nach UI→YAML,
  YAML→UI, Reload und Neustart mit demselben Pairing weiter kommunizieren.
  MAC, Config-Entry-ID, AIDs und IIDs blieben in diesem kontrollierten Versuch
  stabil.
- **CODE VERIFIED:** Core stellt dafür keine öffentliche transaktionale API zur
  Verfügung. Die erfolgreiche Probe verwendet deshalb absichtlich eine
  unsupported interne Mutation und ist kein produktiver Integrationspfad.
- **NOT VERIFIED:** Apple-Home-Raumzuordnungen, Szenen und Automationen können
  ohne ein echtes Apple-Home-System nicht als erhalten gelten.

Die produktive Entscheidung bleibt deshalb **NO-GO für die Freischaltung einer
echten One-Click-Quellenmigration**. Version 0.10.12 enthält nur sichere
Verbesserungen an Quellenerkennung, Multi-Bridge-Tests und isolierter
Experiment-Infrastruktur. Die produktive Sperre in `migration.py` bleibt
unverändert.

## Untersuchte Core-Versionen und Quellen

Untersucht wurden die lokal installierten Home-Assistant-Core-Versionen
`2026.10.4` und `2026.11.0b0`. Die relevanten Pfade sind:

| Core-Pfad | Relevante Funktion/Klasse | Befund |
|---|---|---|
| `homeassistant/components/homekit/__init__.py` | `async_setup`, `_async_update_entries_from_yaml`, `async_setup_entry`, `HomeKit.setup`, `async_unload_entry` | YAML wird über den Importpfad mit `SOURCE_IMPORT` reconciliert; UI-Entries werden separat als `SOURCE_USER` erzeugt; Setup verwendet die unveränderte Entry-ID für Runtime und Persistenz. |
| `homeassistant/components/homekit/config_flow.py` | `ConfigFlow`, `OptionsFlow`, `async_step_init` | Der Flow unterscheidet `SOURCE_IMPORT` und UI-Entries. Ein Options-/Config-Flow-Update ist kein Quellenwechsel. |
| `homeassistant/components/homekit/const.py` | YAML-/Options-Projektion | `filter`, `entity_config`, `mode` und `devices` können in Optionen überführt werden; `ip_address` und `advertise_ip` bleiben YAML-spezifisch. |
| `homeassistant/components/homekit/util.py` | YAML-Reconciliation, Persistenz-Dateinamen | YAML-Entries werden nach Name oder Port gesucht. Das ist kein atomarer Entry-ID-Transfer und kann bei Mehrdeutigkeiten kollidieren. |
| `homeassistant/config_entries.py` | `ConfigEntry`, `ConfigEntries.async_update_entry`, `async_reload`, `async_unload` | `async_update_entry` akzeptiert Daten/Optionen, aber keine öffentliche `source`-Mutation. `source` wird persistiert, ist aber kein stabiler externer Änderungsvertrag. |
| `homeassistant/components/homekit/aidmanager.py` | AID-Zuordnung und Speicherung | AIDs sind Entry-gebunden und werden über stabile Entity-Identität verwaltet. Ein neuer Entry ist daher kein Identitätsäquivalent. |
| `homeassistant/components/homekit/iidmanager.py` | IID-Zuordnung und Speicherung | IIDs hängen von AID/Service/Characteristic ab und werden separat persistiert. |
| `pyhap/accessory_driver.py` | Runtime-Persistenz, `async_start`, `async_stop` | MAC, Pairing-State, Config-Version und Accessory-Hash werden in HAP-State persistiert; Stop/Start ist kein Core-Transaktionspunkt. |
| `pyhap/hap_server.py` | Server-Stop | Der Stop-Pfad schließt den Server, ohne einen vollständigen externen Transaktionsvertrag für Port-Freigabe und Folge-Setup zu liefern. Der POC wartet deshalb explizit auf die Portfreigabe. |

## Technische Ursache der bisherigen Einschränkung

Ein HomeKit-Config-Entry besteht nicht nur aus einer sichtbaren YAML- oder
UI-Projektion. Für eine identitätserhaltende Umstellung müssen mindestens
folgende Zustände konsistent bleiben:

1. `ConfigEntry.entry_id` und persistierte Entry-Daten.
2. `ConfigEntry.source` sowie YAML-Reconciliation beim nächsten Core-Start.
3. HAP-State mit MAC und Pairing-Clients.
4. `homekit.<entry_id>.state`, `.aids` und `.iids`.
5. Portbindung, Advertiser und Runtime-Unload/Setup-Reihenfolge.
6. Native Optionen und YAML-only Felder.

Core liefert keine Transaktion über diese Zustände. Ein Fehler zwischen YAML-
Schreiben, Entry-Store, Unload, Setup und HAP-Persistenz kann daher eine
halb-migrierte Installation erzeugen. Außerdem kann der YAML-Importer beim
nächsten Start anhand von Name/Port eine andere Zuordnung treffen. Ein neuer
Config Entry oder eine Bridge mit gleichem Namen würde Pairing- und
Identitätserhalt nicht beweisen.

## Architekturvergleich

| Ansatz | Machbarkeit | Pairing/Identität | Sicherheit/Rollback | Wartbarkeit | Entscheidung |
|---|---|---|---|---|---|
| A – direkte `ConfigEntry.source`-Mutation | In isoliertem POC technisch reproduzierbar | Im POC nachgewiesen, nicht Core-vertraglich garantiert | Keine Core-Transaktion; Mid-step-Rollback nicht garantiert | Hoch abhängig von Interna | Nicht produktiv freigeben |
| B – Core-API-Abfolge aus Unload/Update/Reload | Teilweise zusammensetzbar | Kann dieselbe Persistenz wiederverwenden, aber Source-Update bleibt intern | Kein atomarer Commit über YAML und Entry-Store | Bricht bei Core-Änderungen | Nicht ausreichend |
| C – Bridge behalten, Manager-Backend wechseln | Sicher und bereits umgesetzt | Native Bridge bleibt unverändert | Read-only/Draft, sehr gut rückrollbar | Core-kompatibel | Gewählte Produktarchitektur |
| D – direkte Storage-/Persistenzmigration | Technisch machbar, aber gefährlich | Nur mit fehlerfreier Kopplung aller Dateien | Atomarität, Rechte, Crash-Recovery und Formatwechsel ungeklärt | Sehr instabil | Verworfen |
| E – eigene deklarative Adapterquelle | Einfache UX möglich | Keine echte native Quellenmigration | Sicher, wenn native Apply weiter gesperrt bleibt | Erweiterbar, aber zweites Datenmodell | Als sichere Zukunftserweiterung geeignet |

Die gewählte Lösung ist **C mit begrenzten Elementen aus E**: Der Manager
liefert eine gemeinsame Verwaltungsoberfläche, deterministische YAML-Projektion,
Draft-Import und Revisionen. Er behauptet dabei niemals, die native Quelle zu
wechseln.

## Isolierter Migrations-Prototyp

Die Testdateien
`tests/integration/_native_source_migration_worker_012.py` und
`tests/integration/test_native_source_migration_012.py` sind ausdrücklich
nicht Teil des Produktionspfads. Sie verwenden ausschließlich ein temporäres
Home-Assistant-Verzeichnis, einen Loopback-HAP-Port und einen lokalen
Advertiser ohne mDNS-Publikation.

Der Ablauf umfasst fünf getrennte Prozesse:

1. `pair_ui`: UI-Entry mit Test-Entity anlegen und mit `aiohomekit` pairen.
2. `migrate_ui_yaml`: kontrolliert unloaden, Portfreigabe abwarten, intern
   `source` auf `SOURCE_IMPORT` setzen, YAML-Testquelle schreiben und reloaden.
3. `restart_yaml`: YAML-Quelle aus persistiertem Testzustand neu laden.
4. `migrate_yaml_ui`: unloaden, YAML entfernen, intern auf `SOURCE_USER` setzen,
   UI-Daten/Optionen setzen und reloaden.
5. `restart_ui`: UI-Quelle aus persistiertem Testzustand neu laden.

Nach jedem Schritt prüft der Controller die HAP-Kommunikation sowie:

- dieselbe Config-Entry-ID,
- dieselbe Bridge-MAC/Identität,
- vorhandenes Pairing,
- vollständige AID-Liste,
- Entity-AID,
- vollständige Entity-IID-Liste.

Das ist ein belastbarer **isolierter interner POC**, aber kein Beweis für
Apple-Home-Verhalten und kein Beweis für Crash-Sicherheit. Die Mutation
`entry.source = ...` und der direkte interne Config-Entry-Store-Aufruf sind
bewusst auf diesen Test beschränkt.

## Transaktion und Rollback: erforderlicher Zielvertrag

Ein zukünftiger produktiver Versuch müsste mindestens diese Zustände und
Übergänge implementieren:

`READY → PREFLIGHT → BACKUP_CREATED → MIGRATING → VERIFYING → COMMITTED`

Fehler müssen in `FAILED` oder `MANUAL_RECOVERY_REQUIRED` enden; Rollback darf
nicht automatisch über einen unklaren Zwischenstand hinweg wiederholt werden.
Erforderlich wären:

- exklusiver Bridge-/Migration-Lock,
- unveränderter Revisions-Snapshot von Entry, YAML und HAP-State,
- atomare und crash-sichere Sicherung aller beteiligten Dateien,
- Core-seitiger Quiesce-/Unload-Vertrag,
- bestätigte Portfreigabe vor Setup,
- Verifikation durch einen echten HAP-Controller,
- Wiederanlauf nach Prozessabbruch und Stromausfall-Simulation,
- expliziter Rollback-Plan ohne Pairing-Reset,
- erneute Verifikation nach Neustart,
- offizielle Core-Unterstützung oder ein stabiler Adaptervertrag.

Diese Anforderungen sind in 0.10.12 noch nicht als produktive Migration
implementiert.

## HKM-012, HKM-013 und HKM-014

### HKM-012 – Include-Verzeichnisse

`config_source.py` erkennt nun `!include_dir_merge_list` und
`!include_dir_merge_named` getrennt von normalen Datei-Includes. Directory-
Quellen werden wie der Core-Lader rekursiv auf sichtbare `*.yaml`-Dateien
begrenzt (`secrets.yaml` wird ignoriert), deterministisch nach relativem Pfad
aufgelistet, gehasht und auf tokenbasierte YAML-Syntax geprüft. Symlinks,
Sonderdateien, fehlende Dateien, Parserfehler und Include-Pfade außerhalb des
Config-Verzeichnisses führen zu einer sicheren Blockade. Es wird kein
Schreibziel aus dem Verzeichnis abgeleitet.

Die Prüfung ist absichtlich eine read-only Provenienz- und Syntaxprüfung; die
vollständige semantische Merge-Bedeutung des Home-Assistant-Importers wird
nicht nachgebaut.

### HKM-013 – Multi-Bridge-Browserfälle

Die isolierte Browser-Fixture enthält drei Bridges: UI, YAML und eine zweite
UI-Bridge. Chromium und WebKit prüfen explizite Auswahl, korrekte
Quellenanzeige und Ablehnung unbekannter Bridge-IDs. Draft-Zuordnung und
Konfliktverhalten bleiben zusätzlich im Backend-Vertrag durch Entry-Bindung und
Revisionen abgesichert.

### HKM-014 – Beta-Bootstrap

Der native Quellen-POC startet seine Child-Prozesse mit aktivierter HA-
pytest-Plugin-Kette, auch wenn der umgebende Beta-Runner Auto-Discovery
deaktiviert. Dadurch wird ein reiner Test-Bootstrap-Fehler behoben, ohne
fachliche Assertions zu wiederholen oder zu unterdrücken. Die bestehende
Bootstrap-Suite wird weiterhin ohne pauschale Assertion-Retries ausgeführt.

## Sicherheits- und Produktgrenzen

- `custom_components/homekit_manager/migration.py` bleibt fail-closed.
- Es gibt keinen produktiven Endpunkt, der `ConfigEntry.source` mutiert.
- Der Verwaltungsansichtswechsel schreibt weder YAML noch `.storage` und
  verändert keine Pairings, AIDs oder IIDs.
- YAML-Drafts bleiben vom nativen HomeKit-Config-Entry getrennt.
- Keine produktive Installation, Bridge, Pairing-Datei oder HAP-Persistenz wurde
  gelesen oder verändert.

## Offene Nachweise

Nicht verifiziert sind insbesondere Stromausfall-/Prozessabbruch während des
kritischen Commit-Fensters, echte Apple-Home-Szenen und Raumzuordnungen,
mehrere gleichzeitig laufende Core-YAML-Reconciliations während einer
Migration sowie ein offizieller Core-Vertrag für die Source-Mutation. Solange
diese Nachweise fehlen, bleibt eine One-Click-Quellenmigration gesperrt.
