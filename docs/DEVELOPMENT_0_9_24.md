# HomeKit Manager 0.9.24 – Entwicklungsstand und Fortsetzung

Stand: 27.10.2026. Branch `feature/homekit-manager-0.9.24`, abgezweigt vom gepushten 0.9.20-HEAD `c22f21748e8e37c7ef437c7768d47abad6dbbb21`. Das Integrationsmanifest bleibt bewusst auf 0.9.20, bis ein 0.9.24-Releasekandidat die verbindliche Definition of Done erfüllt. Dieser Branch ist **kein** installierbarer oder freigegebener 0.9.24-Release.

## Nachgewiesene Core-2026.10.4-Verträge

- `SOURCE_USER` nutzt den nativen Options Flow. HomeKit hält `name` und `port` in `data`, `filter`, `entity_config`, `mode` und `devices` in `options`. Ein Options-Update über `hass.config_entries.async_update_entry()` löst den Core-Update-Listener und dessen Entry-Reload aus.
- `SOURCE_IMPORT` stammt aus YAML. Der Options Flow bietet hierfür keine Bearbeitung. Beim YAML-Abgleich aktualisiert Core importierte Entries anhand von Name oder Port. Direkte Änderung von `source` ist keine unterstützte `async_update_entry()`-Operation.
- **Abweichung zwischen Dokumentation und geprüftem Core-Code:** `homekit.reload` liest YAML neu, führt anschließend aber `async_reload()` für **alle** HomeKit-Entries aus, auch `SOURCE_USER` (`homeassistant/components/homekit/__init__.py`, `_handle_homekit_reload`). Die isolierte YAML-Aktivierung blockiert deshalb eine gemischte native/YAML-Installation. Die produktive Bridge wurde nicht neu geladen.
- HAP-Persistenz und Pairings werden durch Konfigurationswert-Transfer nicht übertragen. Für den Erhalt einer Apple-Home-Kopplung liegt kein unabhängiger Test vor. Wiederholte UI↔YAML-Quellenmigration bleibt gesperrt.

## Implementierter sicher begrenzter Umfang

- `source_model.py`: unveränderliche interne Snapshots für native und importierte Entries, getrennte `data`/`options`, Core-Version, Quelle, Revision und technische Adapterfähigkeiten. Rohwerte sind intern; sie dürfen niemals in UI oder Journal serialisiert werden.
- `native_adapter.py`: lesender Snapshot, revisionsgebundener Filterplan, isoliertes Apply über den Core-Config-Entry-Mechanismus, Options-Nachverifikation, Reconcile und isolierte Options-Rücknahme. Die vorhandene produktive Coordinator-Sperre bleibt vor jedem Writer-Aufruf bestehen. Pairing oder HAP-Aktivierung werden damit nicht bewiesen.
- `yaml_adapter.py`: **nur** eindeutiges `homekit: !include datei.yaml` mit einer Bridge oder Bridge-Liste in ruamel-kompatibler Formatierung. Ein importierter Entry muss exakt mit Name und Port passen. Tags, Secrets, Anker, Aliase, Merge-Keys, Packages, Verzeichnis-Includes, Symlinks, unbekannte Filterfelder, Kommentare im zu ersetzenden Filter und nicht exakt roundtrip-fähige Formatierung sind schreibgeschützt. Vor Apply: Core-Schema und Dateihash. Apply: 0600-Backup mit Integritätsprüfung, atomarer Dateiersatz, fsync, Nachverifikation und metadata-only-Journal. Reconcile schreibt nie automatisch erneut. Isolierte Core-Aktivierung ist nur bei ausschließlich importierten HomeKit-Entries zugelassen.
- `conversion.py`: reversibler **Wert**-Transfer für `name`, `port`, `ip_address`, `advertise_ip`, `filter`, `entity_config`, `mode` und `devices` nach Core-Schema. Ein unbekanntes oder anders gelagertes Feld blockiert die Konvertierung. Ein neuer Config Entry, Quellenwechsel, HAP-Identität und Pairings sind ausdrücklich nicht Teil des Transfers.
- CSS-Korrektur für die vier Haupttabs bei 393 px. Der GitHub-CI-Fehler der 0.9.20-PR-Browserjobs (`nav.scrollWidth - clientWidth == 8`) ist lokal in Chromium und WebKit behoben; ein GitHub-Lauf dieses neuen Branches steht noch aus.
- Zweiter Sicherheitsdurchgang: Der lesende Bridge-Serializer gab zuvor `entity_config.code` oder `setup_code` weiter, wenn solche Werte vorhanden waren. Die Redaction deckt diese exakten Codefelder jetzt ab, ohne `video_codec` zu entfernen; ein gezielter Test verhindert die Regression. Hassfest fand außerdem die fehlende HomeKit-`after_dependencies`-Deklaration; das Manifest wurde korrigiert. Beide Korrekturen benötigen einen neuen CI-Lauf.

## Feldmatrix für den unterstützten Wert-Transfer

| Feld | Native→YAML | YAML→native Werte | Grenze |
|---|---|---|---|
| `name`, `port` | identisch | identisch | Neuer Entry ist neue Identität; Name/Port-Eindeutigkeit bei Neuanlage separat prüfen. |
| `ip_address`, `advertise_ip` | identisch, Core-Schema-gültig | identisch als Datenprojektion | Native UI bietet hierfür keinen allgemeinen Editor. |
| Sechs HomeKit-Filterlisten | identisch | identisch als Optionsprojektion | Unbekannte Filterkeys blockieren. |
| `entity_config` | identisch, Core-Schema-gültig | identisch als Optionsprojektion | Domain-spezifische Felder bleiben wertgleich; native UI bearbeitet nicht alle. |
| `mode` (`bridge`/`accessory`) | identisch als Wert | identisch als Wert | Accessory-Eignung und Entry-Erzeugung sind gesondert zu prüfen. |
| `devices` | identisch | identisch als Optionsprojektion | Core kann Device-Trigger neu ableiten. |
| `index`, unbekannte Keys | blockiert | blockiert | Keine stillschweigende Entfernung. |
| YAML-Kommentare, Includes, Tags, Secrets | nicht übertragbar | nicht übertragbar | Struktur und Provenienz statt Konfigurationswert. |
| Entry-ID, `source`, HAP-State, Pairings, AID/IID | nicht übertragbar | nicht übertragbar | Keine identitätserhaltende Live-Migration. |

## Isolierte Nachweise

- Python 3.14.9, Home Assistant Core 2026.10.4, `pytest-homeassistant-custom-component` 0.13.375. Native: echter geladener Core-Config-Entry mit unterdrücktem Netzwerkstart; Optionsänderung, Reload-Status und Options-Rücknahme geprüft. YAML: echte isolierte `configuration.yaml` plus `!include`, Core-Import, Dateischreiben, `homekit.reload`, verifizierte importierte Optionen und unveränderte Entry-ID geprüft. Die Isolation benutzt synthetische Ports/Identitäten und keine produktiven Schlüssel.
- YAML-Dateitests prüfen Mehrbridge-Datei, Backup/Restore, stale Revision, zwei konkurrierende Sessions, verlorene Antwort nach atomarem Ersatz, unbekannte Felder, Secrets/Tags, Anker, Kommentare, Symlinks und unsichere Include-Strukturen.
- Conversion-Tests prüfen vier aufeinanderfolgende Roundtrips, zwei Bridges, Accessory-Wert und unbekannte Felder. Diese Tests beweisen keine Pairing-Stabilität.
- Chromium und WebKit: je 19 vorhandene responsive Browserfälle lokal bestanden; Frontend-Unit-Test bestanden.
- Isolierter reiner Inventar-Rechenpfad, je 20 Runden: 100 Entitäten 4,198 ms Median/216.715 Byte Python-Peak; 500: 20,510 ms/1.008.431 Byte; 1.172: 48,335 ms/2.296.425 Byte; 5.000: 208,254 ms/10.130.302 Byte. Das sind weder Prozess-RSS noch komplette Core-/WebSocket-/Browser-Refreshes oder Produktivwerte.

## Noch nicht erfüllte Freigabebedingungen

1. Der gemeinsame Admin-WebSocket-Workflow für beide Writer ist nicht implementiert. Der produktive Apply-Endpunkt muss bis zur vollständigen Autorisierung, persistenten Plan-/Backupbindung, Bestätigung, Konflikt- und Recovery-Prüfung gesperrt bleiben. Ein einfacher isolierter Bool-Parameter ist **keine** ausreichende spätere Produktivfreigabe.
2. YAML-Unterstützung ist absichtlich eng. Verzeichnis-Includes, Packages, mehrere bearbeitete Dateien, Secrets und komplexe Provenienz sind nur lesend/gesperrt. Gemischte native/YAML-Installationen können mit Core 2026.10.4 nicht über `homekit.reload` zielgerichtet aktiviert werden.
3. Native Sicherung und Crash-Recovery sind nicht dauerhaft implementiert. Die isolierte Options-Rücknahme ist kein HAP-/Pairing-Rollback.
4. UI-Änderungsablauf zeigt derzeit Preview und einen gesperrten Apply, aber keinen vollständigen Backend-gestützten Prepare/Backup/Apply/Verify-Workflow.
5. Produktive 129/121-IDs und produktive Performance sind wegen fehlender vollständiger authentifizierter Registry-/Event-Daten nicht verifiziert.
6. Keine gepairte unabhängige Apple-Home-Testbridge; Pairing-Erhalt und wiederholte Quellenmigration nicht getestet.
7. Ein zweiter Code-Audit fand und behob die Code-Redaction-Lücke, ist aber noch kein vollständiges unabhängiges Security-Go. Update-/Upgrade-Testmatrix, grüne GitHub-CI dieses Branches und 0.9.24-Release-Build/Hash stehen aus.

## Sichere Fortsetzung

Zuerst die produktive Default-Sperre unverändert lassen. Danach einen persistenten, revisionsgebundenen Operationsdienst mit serverseitiger Admin- und Bridge-Autorisierung implementieren; native/YAML-Adapter nur über diesen Dienst aufrufen. Echte Core-Lifecycle- und Recoverytests erweitern. Den UI-Workflow gegen diesen Dienst testen. Unbekannte YAML-Strukturen und Quellenmigration bleiben gesperrt. Anschließend vollständige Tests, Security-Audit, CI, Build, PR-Review und erst bei belegtem GO Version/Manifest auf 0.9.24 heben und die GitHub-Veröffentlichung durchführen.

Die produktive HomeKit-Bridge, Config Entries, YAML und Pairings wurden in diesem Entwicklungsstand nicht geschrieben oder neu geladen. Die bestehende serverseitige `HomeKitWriteDisabled`-Sperre wurde nicht entfernt.
