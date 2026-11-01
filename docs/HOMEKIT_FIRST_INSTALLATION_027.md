# HomeKit Manager 0.10.27 – sichere Erstinstallation

Status: `CODE VERIFIED` / `TEST VERIFIED` für den beschriebenen Read-only-Pfad. Eine produktive Installation wurde nicht ausgeführt und ist nicht Bestandteil dieses Nachweises.

## Geltungsbereich

0.10.27 ist eine eigenständige HACS-/Custom-Integration für den offiziellen Home-Assistant-Core. Die native UI↔YAML-Quellenmigration, Config-Entry-Quellenwechsel, Pairing-Manipulation und direkte HAP-Persistenzänderung sind im Stable-Pfad deaktiviert.

Nachweisbare Zielbasis ist Home Assistant Core 2026.10.4. Andere Core-Versionen müssen vor der Installation separat geprüft werden; eine erfolgreiche Installation auf einer anderen Version wird nicht aus dieser Anleitung abgeleitet.

## Vorbedingungen

Vor jedem Eingriff:

1. Vollständiges Home-Assistant-Backup erstellen und außerhalb des Systems ablegen.
2. Erfolgreiche Verfügbarkeit und Lesbarkeit des Backups prüfen.
3. Home-Assistant-Core-Version, HomeKit-Integration und vorhandene HomeKit-Config-Entries dokumentieren.
4. Prüfen, dass keine experimentelle Core-Version oder ein experimenteller Patch installiert ist.
5. Prüfen, dass keine Datei `.homekit_manager_write_grant.json` aktiv verwendet werden soll. Für den Erststart wird kein Grant erstellt.
6. Geplante Wartungszeit und Rückfallmöglichkeit sicherstellen.

Abbruchbedingungen sind ein fehlendes Backup, eine unbekannte Core-Version, unklare Bridge-Zuordnung, eine unerwartete aktive Schreibberechtigung oder jede Aufforderung zur Quellenmigration.

## Paketprüfung

Das geprüfte Paket heißt `homekit-manager-0.10.27.zip`.

```text
SHA-256: 3efbe92a3207034d09dd345ee7ceb1b01864fd504291aa98fa30462cc46b87e9
```

Vor dem Entpacken die Prüfsumme gegen die freigegebene Prüfsumme vergleichen. Das Paket enthält ausschließlich `custom_components/homekit_manager/*` und `RELEASE_MANIFEST.json`; experimentelle Core-Patches, Pairings, HAP-Secrets und `.storage`-Dateien sind ausgeschlossen.

## Manuelle Custom-Integration-Installation

Dieser Weg ist für die kontrollierte Erstinstallation vorgesehen und wurde als Paket-/Runtime-Weg gegen den offiziellen Core geprüft. Eine HACS-UI-Installation wurde in diesem Sprint nicht ausgeführt und darf nicht als HACS-UI-Nachweis bezeichnet werden.

1. Home Assistant kontrolliert anhalten.
2. Backup und Prüfsumme erneut prüfen.
3. Das ZIP in einem temporären Verzeichnis entpacken.
4. Ausschließlich `custom_components/homekit_manager/` in das konfigurierte Home-Assistant-Verzeichnis unter `custom_components/` kopieren.
5. Keine Dateien aus `RELEASE_MANIFEST.json` oder Test-/Entwicklungsverzeichnissen in die Konfiguration kopieren.
6. Home Assistant starten und die Logs auf erfolgreiche Integrationseinrichtung prüfen.
7. Die Integration über den Config Flow hinzufügen.

Die Integration erstellt keine HomeKit-Bridge, erzeugt kein Pairing und ändert keine HomeKit-Config-Entry-Quelle. Ein unerwarteter HomeKit-Reload, eine neue Bridge oder eine Pairing-Aufforderung ist ein Stop-Signal.

## Read-only-Erststart

Der Erststart erfolgt ohne lokalen Write-Grant und ohne kurzlebigen Testmodus. In diesem Zustand bleibt der Apply-Pfad gesperrt. Der Manager darf Inventar, Diagnose, Planung, Vorschau und Export anzeigen; er darf keinen Filter schreiben.

Nach dem Start:

- Integration und Config Entry prüfen.
- Panel und authentifizierte WebSocket-Verbindung prüfen.
- Bridge-Inventar mit den nativen HomeKit-Config-Entries vergleichen.
- Keine Bestätigung, kein Apply und kein Reload aus dem Manager ausführen.
- Keine Datei `.homekit_manager_write_grant.json` anlegen.
- Native Migration nicht suchen, nicht aktivieren und keinen Quellenwechsel durchführen.

Falls der Manager eine Schreibaktion ohne Grant/Testmodus anbietet oder ausführt, Home Assistant anhalten, Logs sichern und die Installation abbrechen.

## Inventarprüfung

Für jede Bridge getrennt dokumentieren:

- Config-Entry-ID und native Quelle.
- Name, MAC und Port, soweit lesbar.
- aktuell gespeicherte Filter.
- tatsächlich sichtbare HAP-Accessories, soweit ein unabhängiger Controller verfügbar ist.
- Geräte, Entitäten, Bereiche und Etagen sowie unklare Zuordnungen.
- deaktivierte, ausgeblendete und nicht verfügbare Entitäten.

Manager-Anzeige, native Home-Assistant-Konfiguration und tatsächliche HAP-Veröffentlichung sind drei getrennte Beobachtungen. Unklare Zuordnungen werden nicht automatisch korrigiert.

## Erfolgsbedingung der Erstinstallation

Die Erstinstallation ist nur als Read-only-Erstinstallation abgeschlossen, wenn Home Assistant normal startet, der Manager geladen wird, Panel/WebSocket authentifiziert funktionieren, die vorhandene HomeKit-Konfiguration unverändert bleibt und kein Schreibpfad aktiviert ist.
