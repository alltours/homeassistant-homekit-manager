# HomeKit UI↔YAML-Migration – Architekturentscheidung 0.10.31

Status: Architekturentscheidung, keine produktive Aktivierung

## Entscheidung

Die sichere Produktionsimplementierung benötigt eine offizielle Home-Assistant-Core-Erweiterung. Eine Custom-Integration darf den Wechsel zwischen `SOURCE_USER` und `SOURCE_IMPORT` nicht durch direkte `.storage`-Schreibvorgänge, private Config-Entry-Mutationen oder das Löschen und Neuerstellen einer Bridge emulieren.

Bis diese Core-Schnittstelle verfügbar und gegen echte isolierte HAP-Controller abgenommen ist, bleiben UI→YAML und YAML→UI blockiert.

## Befund in Core 2026.10.4 und 2026.11.0b0

Die HomeKit-Integration behandelt YAML-Konfiguration als `SOURCE_IMPORT` und gleicht sie über `async_update_entries_from_yaml()` beziehungsweise `_async_update_config_entry_from_yaml()` ab. Der vorhandene Abgleich aktualisiert Daten und Optionen eines bereits importierten Eintrags, ändert aber nicht dessen Quelle.

Die UI-OptionsFlow arbeitet mit `SOURCE_USER`. Der `ConfigEntry` besitzt zwar ein persistiertes `source`-Feld, aber `ConfigEntries.async_update_entry()` akzeptiert nur Daten, Optionen, Titel, Version und Verwaltungsmetadaten; eine atomare Quellenänderung ist nicht Teil der öffentlichen API.

Der HomeKit-YAML-Reload liest die YAML-Konfiguration und reloadet anschließend alle HomeKit-Config-Entries. Das ist für einen einzelnen Bridge-Wechsel keine ausreichende Transaktionsgrenze.

Die HomeKit-Runtime lädt AID- und IID-Speicher anhand der bestehenden Entry-ID. Die Bridge-Persistenzdatei wird ebenfalls anhand der Entry-ID bestimmt. Ein Löschen und Neuerstellen des Eintrags ist daher kein identitätserhaltender Ersatz.

## Variante A – Core-Erweiterung

Empfohlene Architektur.

Core sollte eine transaktionale API bereitstellen, sinngemäß:

```python
async def async_prepare_homekit_source_migration(
    hass,
    *,
    entry_id: str,
    target_source: Literal["user", "import"],
    target_data: Mapping[str, Any],
    target_options: Mapping[str, Any],
    expected_entry_revision: str,
    expected_identity_fingerprint: str,
) -> MigrationTransaction:
    ...

async def async_commit_homekit_source_migration(
    hass, transaction_id: str, confirmation: str
) -> MigrationResult:
    ...

async def async_recover_homekit_source_migration(
    hass, transaction_id: str
) -> RecoveryResult:
    ...
```

Die Core-Seite muss dabei:

1. den laufenden HAP-Driver kontrolliert stoppen,
2. den vollständigen Config-Entry-Zustand und die YAML-Repräsentation journalisieren,
3. die Quelle atomar ändern, ohne die Entry-ID zu ändern,
4. Daten und Optionen normalisiert übernehmen,
5. genau die betroffene Bridge wieder laden,
6. Bridge-MAC, Port, Pairing-State, AID-/IID-Fingerprints und Accessory-Menge prüfen,
7. bei Fehlern aus Journal und Snapshot wiederherstellen,
8. nach Prozessabsturz einen manuellen oder explizit bestätigten Recovery-Zustand liefern,
9. andere HomeKit-Bridges unangetastet lassen.

Die Core-API muss außerdem eine Versions-/Revisionsnummer, einen Identity-Fingerprint und einen eindeutigen Transaktionsstatus exportieren. Der Manager darf lediglich planen, bestätigen und lesend verifizieren.

Bewertung: PARTIAL. Technisch machbar, aber Core-Änderung und Upstream-Akzeptanz erforderlich.

## Variante B – vorhandene öffentliche Core-APIs

Nicht ausreichend.

`async_update_entry()` kann die Quelle nicht ändern. `async_reload()` lädt nur einen vorhandenen Eintrag neu. Der YAML-Reload ist integrationsweit und liefert keine atomare Bridge-Transaktion. Das Entfernen und Neuerstellen eines Config Entries würde die bestehende Entry-ID und damit die Zuordnung der HAP-Persistenz gefährden.

Bewertung: FAIL für das verbindliche Ziel.

## Variante C – gemeinsames Verwaltungsmodell

Als Zwischenstufe sinnvoll, aber kein Ersatz für Quellenmigration.

Der Manager kann für beide Quellen dieselbe read-only Reconciliation-, Preview- und Bestätigungslogik verwenden. Native `SOURCE_USER`-Filter können mit dem bestehenden Write-/Apply-Pfad verwaltet werden. YAML-Filter können nur in einer isolierten oder ausdrücklich unterstützten Einzelquellenumgebung geschrieben werden; ein integrationsweiter Reload darf nicht als sichere Einzel-Bridge-Transaktion ausgegeben werden.

Bewertung: PASS als Verwaltungsarchitektur, FAIL als UI↔YAML-Migration.

## Implementierungsplan

1. Core-Design und API-Vertrag mit Entry-ID-, Identity- und Recovery-Invarianten festlegen.
2. Core-Tests für UI→YAML, YAML→UI, Crashpunkte, Journalbeschädigung und parallele Bridges ergänzen.
3. Einen isolierten Core-Patch mit echter HomeKit-Bridge und `aiohomekit`-Controller ausführen.
4. MAC, Port, Entry-ID, Pairing-Reconnect, AID, IID und Accessory-Liste vor/nach jeder Richtung vergleichen.
5. Erst nach erfolgreicher Core-Abnahme den Manager-Adapter implementieren.
6. Manager-seitig dieselbe Write-Grant-, Fingerprint-, Lock- und Bestätigungslogik wie bei Native Apply verwenden.
7. YAML-/UI-Rückmigration erst nach erfolgreichem Recovery- und Multi-Bridge-Nachweis freischalten.

## Sicherheitsentscheidung

Bis zur Core-API und vollständigen End-to-End-Abnahme bleibt jede produktive Quellenmigration fail-closed deaktiviert. Ein erfolgreicher Track A oder ein isolierter Migrationsengine-Test ist kein Beweis für die Erhaltung produktiver Pairings oder Apple-Home-Identitäten.

## Verifizierte Core-Quellen

Die Entscheidung basiert auf den isoliert installierten offiziellen Paketen:

- Core 2026.10.4: `homeassistant/components/homekit/__init__.py:316-345`, `348-419`, `594-626`, `898-935`; `config_entries.py:2668-2796`; `helpers/reload.py:165-173`.
- Core 2026.11.0b0: `homeassistant/components/homekit/util.py:810-895`, `__init__.py:214-301`, `696-737`; `config_entries.py:2733-2860`.
- AID-Persistenz: `homeassistant/components/homekit/aidmanager.py:61-90`, `143-190`, `229-242`.
- IID-Persistenz: `homeassistant/components/homekit/iidmanager.py:63-134`.
