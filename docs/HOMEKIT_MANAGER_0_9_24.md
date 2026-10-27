# HomeKit Manager 0.9.24 – Umfang und Upgrade

## Implementierter und getesteter Umfang

0.9.24 liest vorhandene HomeKit-Config-Entries aus Home Assistant Core 2026.10.4. `SOURCE_USER` bleibt eine nativ konfigurierte Bridge; `SOURCE_IMPORT` bleibt YAML-verwaltet. Der Manager hält Entwürfe und Vorgangsmetadaten, aber keine dritte wirksame HomeKit-Konfiguration. Die vier Seiten HomeKit, Geräte, Änderungen und Einstellungen zeigen Bridge-Auswahl, redigierte Config-Entry-Werte, Inventar, Filterzuordnung, Entwürfe, Vorschau und Diagnosen. Unbekannte tatsächliche HAP-Publikation oder Apple-Home-Sichtbarkeit wird nicht als bestätigt ausgegeben.

Ein `SOURCE_USER`-Entry und ein eindeutig importierter `SOURCE_IMPORT`-Entry können in **isolierten** Core-2026.10.4-Tests Filterlisten durch einen revisionsgebundenen Vorgang ändern und verifizieren. Das ist Entwicklungs- und Testfunktionalität. Die normale Manager-Instanz erstellt den Operationsdienst ohne Schreibberechtigung; beide Admin-Apply-Endpunkte werden serverseitig abgewiesen. Die Bedienoberfläche zeigt den Sperrgrund. Eine Produktivinstallation oder produktive Schreibfreigabe gehört nicht zu diesem Auftrag.

## YAML-Unterstützung

Home Assistant liefert importierte HomeKit-Entries als lesbare effektive Werte. Für automatisiertes Schreiben ist in der Isolation nur `homekit: !include <Datei>` mit einer eindeutig zuordenbaren Bridge oder Bridge-Liste unterstützt. Name und Port des Ziel-Entries müssen genau einem Knoten entsprechen. Der Writer verändert nur Filterlisten, erhält die unberührten Bytes bei unterstützter Formatierung, erstellt ein Integritätsbackup und prüft Dateihash, Core-Schema und importierte Optionen. Ein gemischter nativer/YAML-HomeKit-Bestand wird für YAML-Apply blockiert, weil `homekit.reload` im geprüften Core auch native HomeKit-Entries neu lädt.

`!include_dir_*`, Packages, verschachtelte Includes, `!secret`, Anker/Aliase, Merge-Keys, Symlinks, nicht roundtrip-fähige Formatierung, kommentierte Ziel-Filter und mehrdeutige Zuordnung bleiben für automatisches Schreiben gesperrt. Der Manager löst solche Strukturen nicht auf, um sie anschließend in eine andere Dateistruktur zurückzuschreiben. Der konkrete Grund wird bei der Planung ausgegeben. Das Lesen effektiver Core-Werte ist kein Nachweis einer sicheren Originaldatei-Provenienz.

## Native Verwaltung und Werteprojektion

Der native Adapter unterscheidet Config-Entry-`data` von `options`. In der Isolation wird ausschließlich eine unterstützte Filteränderung eines `SOURCE_USER`-Entries über `hass.config_entries.async_update_entry()` angewendet und nach dem Core-Update erneut gelesen. Änderungen an Entry-Identität, `source`, HAP-Persistenz, Pairings oder AID/IID gehören nicht zum Adapter. Interne Projektion zwischen nativen Werten und YAML-Werten ist für bekannte Core-Felder getestet; unbekannte Felder blockieren sie. Die Projektion erstellt keine Bridge und ist keine Migration.

## Ausdrücklich nicht enthalten

- YAML→UI- oder UI→YAML-Quellenmigration, auch nicht für 0.10.0 geplant.
- Automatische Bridge-Erstellung oder -Ersetzung und Änderung von Config-Entry-`source`.
- Produktive Aktivierung der nativen oder YAML-Schreibpfade.
- Nachweis, dass Apple-Home-Pairings, Automationen oder HAP-AID/IID nach Konfigurationsänderungen erhalten bleiben.
- Automatische Bearbeitung einer YAML-Datei mit nicht bewiesener Provenienz.

## Upgrade von 0.9.19 oder 0.9.20

Der Kandidat ändert weder HomeKit-Config-Entry-Quelle noch Pairing-Dateien. Bestehende Manager-Entwürfe und Manager-Metadaten werden weiterhin gelesen; veraltete Migrationswünsche werden nicht ausgeführt. Ein isolierter Upgrade-Test speichert einen alten YAML-Moduswunsch für eine native Bridge und bestätigt nach Manager-Start, dass Entry-Quelle, `data` und `options` unverändert bleiben. Der Legacy-Endpunkt `set_mode` verweigert neue Moduswünsche, und `migration_start` gibt nur einen schreibfreien Blockierungsstatus zurück. Für eine spätere, gesondert autorisierte Installation: Manager-Verzeichnis und Manager-Metadaten sichern, Version/Manifest und Home-Assistant-Core-Version prüfen, nach dem Update Bridge-Auswahl und Inventar lesend verifizieren. Eine Produktivinstallation wurde in diesem Auftrag nicht durchgeführt, daher ist der reale Upgradepfad **nicht produktiv getestet**.

## Tests und Nachweise

`docs/DEVELOPMENT_0_9_24.md` nennt die isolierten Core-, YAML-Datei-, Browser-, Performance- und Sicherheitsnachweise sowie offene Freigabebedingungen. `scripts/build_release.py` erzeugt ein byte-reproduzierbares ZIP mit Dateihashes; nur ein nach CI und Review freigegebener Commit darf getaggt und veröffentlicht werden. Ein Konfigurationsbackup ist kein Pairing-Backup und keine Garantie für Apple-Home-Wiederherstellung.
