# HomeKit Manager 0.10.11 – Dual-Mode-Verwaltung

## Ergebnis

0.10.11 ergänzt eine zentrale, einheitliche Verwaltungsoberfläche für zwei
Verwaltungssichten:

- `UI / Bridge`: Verwaltung der nativen UI-Config-Entry-Bridge.
- `YAML`: deterministische YAML-Projektion als Entwurf, Validierung, Vorschau
  und Export.

Die Begriffe „Verwaltungsmodus“ und „native Konfigurationsquelle“ werden bewusst
getrennt angezeigt. Eine Auswahl des YAML-Modus erzeugt keinen neuen
`SOURCE_IMPORT`-Entry, löscht keinen UI-Entry, verändert keine Pairings und
schreibt keine produktive YAML-Datei. Die echte Quellenmigration bleibt
zuverlässig gesperrt.

## Untersuchung von Home Assistant Core 2026.11.0b0

Nachweisbasis: installierter Core `2026.11.0b0` im isolierten Beta-Venv sowie
der identische offizielle Tag:

- [`homekit/__init__.py`](https://github.com/home-assistant/core/blob/2026.11.0b0/homeassistant/components/homekit/__init__.py)
- [`homekit/config_flow.py`](https://github.com/home-assistant/core/blob/2026.11.0b0/homeassistant/components/homekit/config_flow.py)
- [`homekit/const.py`](https://github.com/home-assistant/core/blob/2026.11.0b0/homeassistant/components/homekit/const.py)
- [`homekit/util.py`](https://github.com/home-assistant/core/blob/2026.11.0b0/homeassistant/components/homekit/util.py)
- [`homekit/aidmanager.py`](https://github.com/home-assistant/core/blob/2026.11.0b0/homeassistant/components/homekit/aidmanager.py)
- [`homekit/iidmanager.py`](https://github.com/home-assistant/core/blob/2026.11.0b0/homeassistant/components/homekit/iidmanager.py)
- [`homekit/accessories.py`](https://github.com/home-assistant/core/blob/2026.11.0b0/homeassistant/components/homekit/accessories.py)
- [`YAML-Konfigurationsregeln`](https://developers.home-assistant.io/docs/configuration_yaml_index/)
- [`HomeKit-Bridge-Dokumentation`](https://www.home-assistant.io/integrations/homekit/)

### UI- und YAML-Instanzen

`homekit/__init__.py:180-211` validiert die native YAML-Struktur als Liste von
Bridge-Konfigurationen. `async_setup()` in `:214-229` verarbeitet YAML und ruft
`async_update_entries_from_yaml(..., start_import_flow=True)` auf. Neue YAML-
Instanzen werden in `util.py:810-837` mit `context={"source": SOURCE_IMPORT}` in
den Config Flow gegeben. `config_flow.py:345-351` erzeugt daraus einen
Config-Entry.

Die UI-Instanz entsteht über den normalen Config Flow. Der Options-Flow ist in
`config_flow.py:389-396` registriert; `async_step_init()` in `:757-799`
unterscheidet `SOURCE_IMPORT` von der UI-Quelle. Für importierte Einträge wird
der YAML-Optionsschritt verwendet, UI-Einträge nutzen den nativen Options-Flow.

### Konfigurationsfelder

Core akzeptiert für eine Bridge mindestens `name`, `port`, optional
`ip_address`, `advertise_ip`, `mode`, `filter`, `entity_config` und `devices`.
Die Schema-Definition steht in `homekit/__init__.py:180-211`. In
`homekit/const.py:321-325` sind die von Core aus `data` nach `options`
übertragbaren Felder `filter`, `entity_config`, `mode` und `devices` definiert.
`ip_address` und `advertise_ip` werden in `async_setup_entry()` ausdrücklich als
YAML-only behandelt (`__init__.py:239-246`).

### Identität, Pairings, AIDs und IIDs

`async_setup_entry()` übergibt die unveränderte `entry.entry_id` an `HomeKit`
(`__init__.py:264-277`). `HomeKit.setup()` bildet daraus die Persistenzpfade
(`__init__.py:392-424`):

- `homekit.<entry_id>.state`
- `homekit.<entry_id>.aids`
- `homekit.<entry_id>.iids`

`util.py:633-664` definiert diese Dateinamen. Der AID-Manager verwendet die
Entity-Registry-Identität und persistiert Zuordnungen je Entry
(`aidmanager.py:57-81`, `:143-189`). Der IID-Manager persistiert Services und
Characteristics pro AID (`iidmanager.py:59-83`, `:84-114`).

Der pyhap-Zustand enthält MAC, Schlüssel, Pairing-Clients, Config-Version und
Accessories-Hash (`pyhap/encoder.py:50-90`). Die Persistenz wird atomar ersetzt
(`pyhap/accessory_driver.py:637-677`). AID/IID-Dateien, Pairing-State und
Config-Entry-ID sind daher eine gekoppelte Identitätskette. Ein bloßes
Übersetzen von YAML-Keys oder ein neuer Config Entry beweist deren Erhaltung
nicht.

### Reload und sichere Änderungen

UI-Optionsänderungen registrieren den Core-Update-Listener
(`__init__.py:279-302`). Für nicht importierte Entries führt er einen normalen
`async_reload()` aus; importierte Entries werden bei YAML-Aktualisierung durch
`util.py:867-895` aktualisiert. Core lädt dabei denselben Config Entry und kann
seine Persistenz wiederverwenden. Ein Filter-Reload innerhalb derselben Quelle
ist deshalb technisch anders als eine Quellenmigration.

## Architekturentscheidung

| Ansatz | Bewertung |
|---|---|
| A – echte UI↔YAML-Quellenmigration | Nicht freigegeben. Keine stabile öffentliche API zur Änderung von `ConfigEntry.source`; `ConfigEntries.async_update_entry` ändert nur Daten/Optionen. Entry-ID-, Persistenz- und Pairing-Erhalt wäre nicht beweisbar. |
| B – einheitliche Verwaltungsoberfläche | Gewählt. Native Quelle bleibt autoritativ. UI und YAML erhalten gemeinsame Inventar-, Filter-, Preview-, Export- und Validierungsfunktionen. |
| C – Hybrid mit eigener Source of Truth | Als internes Manager-Draft-Modell genutzt, aber nicht als zweite aktive HomeKit-Quelle. Optimistische Revisionen und Konflikterkennung verhindern, dass ein Draft native Core-Daten überschreibt. |

Die Sicherheitsentscheidung ist damit: Verwaltungsmodus darf wechseln; native
Konfigurationsquelle darf 0.10.11 nicht automatisch wechseln.

## Implementierung

### Backend

- `dual_mode.py` definiert native Quellen (`user`/`import`), Verwaltungssichten,
  Fähigkeiten und nicht-ausführbare Prüfpläne.
- `coordinator.mode_status()` liefert zusätzlich `dual_mode` mit:
  `native_configuration_source`, `mode_options`, `plans` und dem expliziten
  `source_migration`-Blocker.
- Die bisherige `migration_plan`-/`migration_start`-Kompatibilität bleibt
  erhalten und bleibt fail-closed.
- `conversion.py` validiert dieselbe unterstützte Feldprojektion gegen Core
  `2026.10.4` und `2026.11.0b0`.
- Bestehende YAML-Draft-Speicherung, Export, Revisionen, Backups und
  Berechtigungsprüfungen bleiben unverändert.

### Frontend

Die Konfigurationsansicht enthält nun:

1. Verwaltungsmodus `UI / Bridge` oder `YAML`.
2. native Konfigurationsquelle als separate, autoritative Anzeige.
3. eine Prüfkarte mit sicherer Aktion, Quellenmigrationsstatus und
   Pairing-Nachweis.
4. eine klare Erklärung, dass die YAML-Auswahl auf einer UI-Bridge nur
   Vorschau/Export/Validierung ist.

Die eigentliche Entitätsverwaltung, Sammelaktionen, Bereiche, Geräte,
Kompatibilität, Hidden-/Disabled-Entity-Gates, Runtime-Diagnose,
Abweichungserkennung und Positivlistenlogik werden weiter gemeinsam benutzt.

## YAML-Unterstützung

Unterstützt und getestet sind:

- Manager-YAML-Draft mit deterministischem Schema.
- YAML-Vorschau und Export.
- Validierung unbekannter Schlüssel, Entity-IDs, Statuswerte und Schema-Version.
- Core-Schema-Prüfung der unterstützten nativen Projektion.
- Import geeigneter YAML-Werte in einen nichtproduktiven Draft.
- Optimistische Revisionen, atomare Speicherung und Konfliktblockade.
- Sicherheitsblockaden für Symlinks, Hardlinks, ACLs, unsichere Dateirechte,
  ungültige Bestandsdateien und veraltete Snapshots.

Direkte native YAML-Dateiänderungen bleiben eine separat nachgewiesene,
quellengebundene Operation. 0.10.11 bietet daraus keine UI↔YAML-
Quellenmigration an.

## One-Click-Migration

Status: **nicht freigegeben**.

Der Assistent analysiert Quelle, Bridge-Modus, Core-Version, Snapshot und
Draft. Bei UI→YAML wird eine YAML-Projektion als Entwurf/Export angeboten; bei
YAML→UI bleibt die YAML-Quelle maßgeblich. Kein Schritt erstellt, löscht oder
ersetzt einen Config Entry. Kein Schritt fasst `.storage/homekit.*`, Pairings,
MAC, AIDs oder IIDs an.

Eine zukünftige echte Migration benötigt einen offiziellen Core-Vertrag, der
mindestens die atomare Übernahme von Entry-ID, Runtime-Persistenz und Pairing-
State garantiert. Ohne diesen Nachweis bleibt sie blockiert.

## Testnachweise

| Testart | Ergebnis |
|---|---|
| Python-Unit-Tests auf HA Core 2026.10.4 | **166 bestanden**, 0 fehlgeschlagen, 0 übersprungen, 7 Warnungen. |
| Python-Unit-Tests auf HA Core 2026.11.0b0 | **166 bestanden**, 0 fehlgeschlagen, 0 übersprungen, 4 Warnungen; inklusive Dual-Mode-/Conversion-Verträgen gegen den Beta-Core. |
| Core-Integrationstest auf HA Core 2026.10.4 | **114 bestanden**, einschließlich Config-Flow, WebSocket, YAML, HAP-Loopback und Browser-Backend. |
| Core-Integrationstest auf HA Core 2026.11.0b0 | **114 bestanden**, 0 fehlgeschlagen, 0 übersprungen, 4 Warnungen; mit dem dokumentierten Testadapter für den entfernten Logger-Hook. YAML-Apply bleibt auf dieser Beta absichtlich blockiert und wird als Blockade geprüft. |
| YAML-Core-Import/Reload | Vorhandene isolierte Tests bestehen auf dem kompatiblen Venv und prüfen `SOURCE_IMPORT`, Entry-ID und Reload. |
| HAP-Loopback | Vorhandener isolierter YAML-Loopback weist MAC-, Pairing-, AID- und IID-Erhalt innerhalb derselben YAML-Quelle nach; kein Quellenmigrationsnachweis. |
| Frontend-Unit-Test und JS-Syntax | Bestanden (`npm run test:frontend`, `node --check`). |
| Browser Chromium/WebKit | **104 bestanden** (`npm run test:browser`), einschließlich des neuen Dual-Mode-Tests. |
| Release-Reproduzierbarkeit | **3 bestanden** (`tests/test_release.py`), 51 Dateien; SHA-256 wird nach dem finalen Commit neu erzeugt. |
| Ruff-Qualitätsprüfung | Bestanden für geänderte Backend-/Testdateien. |

Für Core `2026.11.0b0` ist `pytest-homeassistant-custom-component 0.13.375`
weiterhin die verfügbare Plugin-Version; sie importiert einen Logger-Hook, den
der Beta-Core entfernt hat. `scripts/run_beta_integration.py` lädt deshalb
unter `tests/integration/_beta_pytest_adapter/sitecustomize.py` einen eng
begrenzten No-op-Kompatibilitätshook. Der Adapter ändert keinen Core-Code,
deaktiviert keine Assertions und wird nicht in das Release-ZIP aufgenommen.
Damit ist die vollständige Beta-Integration reproduzierbar ausführbar; die
YAML-Schreibpfade werden auf dieser nicht freigegebenen Core-Version weiterhin
serverseitig blockiert und auf Byte-Unverändertheit geprüft.

## Sicherheitsbewertung

- Produktive Bridge: nicht geöffnet, nicht geladen, nicht geändert.
- Kein produktiver Apply, Reload, Neustart, Pairing- oder `.storage`-Zugriff.
- Alle neuen Modus-/Migrationsfunktionen sind read-only bzw. Draft-Metadaten.
- Quellenwechsel ist serverseitig nicht ausführbar und nicht nur im Frontend
  versteckt.
- Pairing- und Identitätserhalt werden nur bei derselben Quelle behauptet, wenn
  der isolierte HAP-Test ihn tatsächlich prüft.
- Sensible Entry-Werte bleiben redigiert.
- Vor den Testläufen geprüft: lokaler Datenträger 460 GiB gesamt, ca. 6,2 GiB
  frei (99 % belegt). Es wurden keine zusätzlichen großen Test-Checkouts oder
  Auditkopien angelegt.

## Rückwärtskompatibilität

Bestehende Manager-Drafts, Ausschlüsse, Positivlisten, WebSocket-Verträge,
Admin-Berechtigungsprüfungen und native Filterpfade bleiben erhalten. Der alte
`mode_status`-Vertrag und die alten Migrations-Endpunkte liefern weiterhin ihre
fail-closed Werte; `dual_mode` ist eine additive Erweiterung. Es gibt keine
automatische Migration bestehender Installationen.

## Offene Einschränkungen

1. Eine echte UI↔YAML-Quellenmigration ist nicht sicher nachgewiesen und bleibt
   blockiert.
2. Apple-Home-Raumzuordnungen, Szenen und Automationen sind außerhalb eines
   kontrollierten Apple-Home-Systems nicht verifizierbar.
3. Core-interne Klassen und Dateiformate dürfen nicht als öffentliche API
   behandelt werden. Bei Core-Updates müssen Schema, Config-Flow und
   Persistenztests erneut geprüft werden.
4. Die Beta-Testumgebung benötigt den dokumentierten Testadapter, solange
   `pytest-homeassistant-custom-component` den entfernten Logger-Hook noch
   importiert. Das ist Testinfrastruktur und kein Produktbestandteil.

## Release-Bewertung

**Conditional Go für 0.10.11 als sichere Dual-Mode-/Draft-Version.**

Nicht enthalten und nicht als enthalten zu vermarkten: automatische native
Quellenmigration, Pairing-Migration oder One-Click-Übernahme zwischen
`SOURCE_USER` und `SOURCE_IMPORT`.
