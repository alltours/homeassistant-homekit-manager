# HomeKit Manager 0.9.24 – Entwicklungsstand und Fortsetzung

Stand: 27.10.2026. Branch `feature/homekit-manager-0.9.24`, abgezweigt vom gepushten 0.9.20-HEAD `c22f21748e8e37c7ef437c7768d47abad6dbbb21`. Manifest, Python-Konstante und Frontend-Paket sind für den 0.9.24-Releasekandidaten konsistent. Dieser Branch ist **noch kein offiziell veröffentlichter oder produktiv freigegebener Release**.

## Strategische Entscheidung: Quellen bleiben erhalten

Eine bestehende YAML-Bridge bleibt `SOURCE_IMPORT`, eine bestehende UI-Bridge bleibt `SOURCE_USER`. YAML→UI, UI→YAML, Änderungen von Config-Entry-`source` und automatische Quellenmigration sind weder Teil von 0.9.24 noch der geplanten 0.10.0. Die gemeinsame Wertübersetzung in `conversion.py` bleibt für internes Modell, Validierung und adapterspezifische Projektion erhalten; sie erzeugt, ersetzt oder migriert keine Bridge. Der Legacy-Endpunkt `set_mode` speichert keine Quellwünsche mehr. `migration_start` liefert nur einen schreibfreien Blockierungsstatus; die nicht gerenderte Migrationsoberfläche wurde entfernt. Alte, bereits persistierte Manager-Metadaten werden weiterhin lesend behandelt.

0.9.24 konzentriert sich auf lesende Verwaltung beider Quellen, einheitliches Inventar, Planung, Validierung und die produktive Default-Sperre. Die isoliert getesteten Writer bleiben als Grundlage erhalten. Eine spätere gesonderte 0.10.0-Prüfung betrifft sichere produktive Schreibfreigabe und breitere YAML-Abdeckung, **nicht** Quellenmigration.

## Nachgewiesene Core-2026.10.4-Verträge

- `SOURCE_USER` nutzt den nativen Options Flow. HomeKit hält `name` und `port` in `data`, `filter`, `entity_config`, `mode` und `devices` in `options`. Ein Options-Update über `hass.config_entries.async_update_entry()` löst den Core-Update-Listener und dessen Entry-Reload aus.
- `SOURCE_IMPORT` stammt aus YAML. Der Options Flow bietet hierfür keine Bearbeitung. Beim YAML-Abgleich aktualisiert Core importierte Entries anhand von Name oder Port. Direkte Änderung von `source` ist keine unterstützte `async_update_entry()`-Operation.
- **Abweichung zwischen Dokumentation und geprüftem Core-Code:** `homekit.reload` liest YAML neu, führt anschließend aber `async_reload()` für **alle** HomeKit-Entries aus, auch `SOURCE_USER` (`homeassistant/components/homekit/__init__.py`, `_handle_homekit_reload`). Die isolierte YAML-Aktivierung blockiert deshalb eine gemischte native/YAML-Installation. Die produktive Bridge wurde nicht neu geladen.
- HAP-Persistenz und Pairings werden durch Konfigurationswert-Transfer nicht übertragen. Für den Erhalt einer Apple-Home-Kopplung liegt kein unabhängiger Test vor. Wiederholte UI↔YAML-Quellenmigration bleibt gesperrt.

## Implementierter sicher begrenzter Umfang

- `source_model.py`: unveränderliche interne Snapshots für native und importierte Entries, getrennte `data`/`options`, Core-Version, Quelle, Revision und technische Adapterfähigkeiten. Ungeschützte Rohwerte bleiben intern; die Bridge-Ansicht zeigt nur die gesondert redigierten Reader-Werte. Journale enthalten keine Rohwerte.
- `native_adapter.py`: lesender Snapshot, revisionsgebundener Filterplan, isoliertes Apply über den Core-Config-Entry-Mechanismus, Options-Nachverifikation, Reconcile und isolierte Options-Rücknahme. Ein HA-Store-Journal sichert Operation-ID, Quell- und Kontextrevision sowie den vorherigen und geplanten Filter; doppelte Operation-IDs werden abgewiesen, und ein neu instanziierter Adapter kann den gespeicherten Vorgang lesend abgleichen. Es enthält keine HAP-Schlüssel. Die vorhandene produktive Coordinator-Sperre bleibt vor jedem Writer-Aufruf bestehen. Pairing oder HAP-Aktivierung werden damit nicht bewiesen.
- `yaml_adapter.py`: **nur** eindeutiges `homekit: !include datei.yaml` mit einer Bridge oder Bridge-Liste in ruamel-kompatibler Formatierung. Ein importierter Entry muss exakt mit Name und Port passen. Tags, Secrets, Anker, Aliase, Merge-Keys, Packages, Verzeichnis-Includes, Symlinks, unbekannte Filterfelder, Kommentare im zu ersetzenden Filter und nicht exakt roundtrip-fähige Formatierung sind schreibgeschützt. Vor Apply: Core-Schema und Dateihash. Apply: 0600-Backup mit Integritätsprüfung, atomarer Dateiersatz, fsync, Nachverifikation und metadata-only-Journal. Reconcile schreibt nie automatisch erneut. Isolierte Core-Aktivierung ist nur bei ausschließlich importierten HomeKit-Entries zugelassen.
- `conversion.py`: reversible **interne Wertprojektion** für `name`, `port`, `ip_address`, `advertise_ip`, `filter`, `entity_config`, `mode` und `devices` nach Core-Schema. Ein unbekanntes oder anders gelagertes Feld blockiert die Projektion. Entry-Erzeugung, Quellenwechsel, HAP-Identität und Pairings sind ausdrücklich nicht Teil dieser Funktion.
- `operations.py`: gemeinsame isolierte Plan-/Apply-/Status-/Reconcile-Schicht für beide Adapter. Ein Plan bindet Operation-ID, Entry, Quelle und Revision. Apply verlangt zusätzlich Admin-Flag und Bestätigung exakt dieser Operation. Secret-freie Metadaten werden dauerhaft gespeichert; unterbrochene Vorgänge werden ohne Wiederholungs-Write abgeglichen. Native und YAML-Kernabläufe sind gegen echte isolierte Core-Entries getestet. Admin-WebSocket-Kommandos für Plan, Apply, Status und Reconcile sowie ein UI-Plan-/Bestätigungsablauf sind angeschlossen. Die in normalem Home Assistant vom Coordinator erzeugte Serviceinstanz hat **keine** Schreibberechtigung: auch ein gefälschter Apply-Request endet mit `HomeKitWriteDisabled`; nur ein isolierter Test injiziert eine autorisierte Instanz. Die alte `apply_options_diff`-Sperre bleibt unverändert. Ein boolesches Test-Flag ist keine spätere Produktivfreigabe.
- CSS-Korrektur für die vier Haupttabs bei 393 px. Der erste GitHub-CI-Lauf des neuen Branches zeigte trotz lokaler Korrektur noch 2 px Navigationsoverflow unter Ubuntu. Mobile Tab-Texte dürfen jetzt umbrechen; der endgültige Linux-CI-Nachweis steht aus.
- Die Bridge-Detailansicht zeigt nach explizitem Öffnen die vom Reader bereits redigierten Config-Entry-`data` und `options` für native und importierte Bridges. Das ist eine Ansicht der von Core gespeicherten Werte, kein Beweis der ursprünglichen YAML-Dateistruktur, Kommentarpositionen oder Geheimnisse.
- Zweiter Sicherheitsdurchgang: Der lesende Bridge-Serializer gab zuvor `entity_config.code` oder `setup_code` weiter, wenn solche Werte vorhanden waren. Die Redaction deckt diese exakten Codefelder jetzt ab, ohne `video_codec` zu entfernen; ein gezielter Test verhindert die Regression. Hassfest fand außerdem die fehlende HomeKit-`after_dependencies`-Deklaration und danach die Manifest-Sortierung; beides wurde korrigiert. Ein grüner CI-Lauf des endgültigen HEAD steht aus.
- Die alte CI-Textsuche verbot jede isolierte `apply_enabled=True`-Verwendung und hätte damit den ausdrücklich geforderten Test-Writer zurückgewiesen. Der Check prüft nun die unveränderte Coordinator-Sperre und die getrennte Writer-Gate-Bedingung; die tatsächliche WebSocket-/Admin-Sperre wird zusätzlich durch HA-Integrationstests ausgeführt.

## Feldmatrix für interne Wertprojektion ohne Quellenwechsel

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
- Chromium und WebKit: je 22 responsive Browserfälle lokal bestanden; Frontend-Unit-Test bestanden. Die fünfminütige Chromium-Stabilitätsprobe zeigte 3 Renderings zu Beginn und am Ende sowie 12 Fixture-Kommandos.
- Ein zusätzlicher Chromium-/WebKit-Fall prüft den isolierten UI-Plan, die Bestätigung exakt einer Operation und den Verifikationsstatus. Core-WebSocket-Integrationstests prüfen den Admin-Transport bis zum isolierten nativen Writer sowie bis zum isolierten YAML-Writer mit tatsächlichem Dateibackup, Core-Reload und Config-Entry-Nachverifikation. Der native Test bestätigt die Default-Sperre vor der isolierten Autorisierung. Ein Konkurrenztest zeigt, dass Reconcile einen laufenden Apply abwartet und dessen alten Quellstand nicht als `not_applied` fehlklassifiziert.
- Isolierter reiner Inventar-Rechenpfad, je 20 Runden: 100 Entitäten 4,198 ms Median/216.715 Byte Python-Peak; 500: 20,510 ms/1.008.431 Byte; 1.172: 48,335 ms/2.296.425 Byte; 5.000: 208,254 ms/10.130.302 Byte. Das sind weder Prozess-RSS noch komplette Core-/WebSocket-/Browser-Refreshes oder Produktivwerte.

## Bekannte Grenzen und Freigabebedingungen

1. Der Admin-WebSocket- und UI-Pfad ist angeschlossen und beide Writer wurden durch den echten WebSocket-Transport in Isolation getestet. Die produktive Backend-Sperre bleibt geschlossen. Eine spätere produktive Freigabearchitektur ist ein gesondertes 0.10.0-Ziel; ein isolierter Bool-Parameter ist **keine** Produktivfreigabe.
2. YAML-Unterstützung ist absichtlich eng. Verzeichnis-Includes, Packages, mehrere bearbeitete Dateien, Secrets und komplexe Provenienz sind nur lesend/gesperrt. Gemischte native/YAML-Installationen können mit Core 2026.10.4 nicht über `homekit.reload` zielgerichtet aktiviert werden.
3. Der native Filter-Vorzustand und Status sind nun in einem HA-Store-Journal gesichert; ein vollständiger Core-Neustart-, Crash- und unabhängiger HAP-/Pairing-Recoverytest fehlt. Die isolierte Options-Rücknahme ist kein HAP-/Pairing-Rollback.
4. Der UI-Änderungsablauf kann Plan, Bestätigung und Apply/Verify im isolierten Browser-Test ausführen; der reale produktive Apply bleibt gesperrt. Backupstatus in der UI, vollständige Änderungshistorie, Timeout-/Offline-UX und produktive Upgradefälle sind noch nicht vollständig nachgewiesen. Sie gehören nicht zum produktiv aktivierten 0.9.24-Umfang.
5. Produktive 129/121-IDs und produktive Performance sind wegen fehlender vollständiger authentifizierter Registry-/Event-Daten nicht verifiziert.
6. Keine gepairte unabhängige Apple-Home-Testbridge; Pairing-Auswirkungen isolierter Filteränderungen sind nicht unabhängig bestätigt. Wiederholte Quellenmigration ist nach der neuen Produktentscheidung kein Ziel.
7. Ein zweiter Code-Audit fand und behob die Code-Redaction-Lücke und ein Reconcile-Race. Der endgültige Sicherheits-/Release-Audit, grüne GitHub-CI des endgültigen HEAD und die PR-Abnahme stehen vor einem offiziellen Release aus. Das 0.9.24-ZIP liegt lokal als reproduzierbarer Kandidat vor; es wurde nicht veröffentlicht oder produktiv installiert.

## Sichere Fortsetzung

Die produktive Default-Sperre unverändert lassen. Für 0.9.24 den lesenden und planenden Umfang, UI, Sicherheitsprüfung, CI und PR-Abnahme abschließen. Isolierte Writer erhalten; spätere produktive Autorisierung, breitere YAML-Bearbeitung und Core-Lifecycle-/Recovery-Prüfungen gesondert für 0.10.0 bewerten. Quellenmigration bleibt für beide Versionen außerhalb des Ziels. Die Versionsdateien sind für den Kandidaten konsistent; die GitHub-Veröffentlichung erfolgt nur bei belegtem GO.

Die produktive HomeKit-Bridge, Config Entries, YAML und Pairings wurden in diesem Entwicklungsstand nicht geschrieben oder neu geladen. Die bestehende serverseitige `HomeKitWriteDisabled`-Sperre wurde nicht entfernt.
