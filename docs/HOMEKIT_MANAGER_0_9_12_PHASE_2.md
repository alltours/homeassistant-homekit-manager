# HomeKit Manager 0.9.12 – Phase 2

## Umfang

Phase 2 verbindet den zentralen Entwurf mit einer validierten, atomaren
YAML-Ablage. Produktive HomeKit-Config-Entries, Pairings, Bridge-Identitäten
und `.storage`-Daten werden nicht verändert.

## Unterstützte Speicherwege

| Quelle | Lesen | Schreiben | Aktivierung |
|---|---:|---:|---|
| Standard / Config Entry | Ja | Nein | Gesperrt; keine stabile unterstützte externe Options-API nachgewiesen |
| Direkte YAML-Konfiguration | Erkennung und Include-Inspektion | Nein | Manuell erforderlich |
| `homekit_manager.yaml` | Ja, wenn vorhanden | Ja, ausschließlich als validierter Manager-Entwurf | Nicht automatisch aktiv; Include und Dateizustand müssen eindeutig nachgewiesen sein |

Der YAML-Schreibpfad schreibt ausschließlich die Manager-Datei. Er aktualisiert
weder `configuration.yaml` noch Home-Assistant-Config-Entries und führt keinen
Reload oder Neustart aus.

## Sicherheitsmechanismen

- Schema- und Entity-ID-Validierung vor jedem Schreiben.
- Optimistische Versionsprüfung gegen den SHA-256-Inhalt der gelesenen Datei.
- Thread-Sperre und plattformabhängige Prozesssperre über eine Lock-Datei.
- Atomare temporäre Datei mit `fsync` und `os.replace`.
- Vorhandene Datei wird vor dem Ersetzen als `homekit_manager.yaml.bak`
  gesichert.
- Ungültige, leere oder zwischenzeitlich veränderte Dateien werden nicht
  überschrieben.
- Fremde Top-Level-Schlüssel und unbekannte Schema-Versionen blockieren die
  Speicherung.
- Historie enthält weiterhin nur redigierte gewünschte Zustände ohne Tokens,
  Pairing-Daten oder Secrets.

## Quellenprüfung

Die Quelleninspektion erkennt Config-Entry-, direkte YAML- und Include-Quellen.
Include-Pfade werden auf das Home-Assistant-Konfigurationsverzeichnis begrenzt.
Existenz, Lesbarkeit, Größe, SHA-256 und YAML-Parsefehler werden gemeldet;
Dateiinhalte werden nicht an die Oberfläche zurückgegeben. Fehlende oder nicht
lesbare Includes führen zu einem unklaren beziehungsweise blockierten Zustand.

## Migrationen

Die sechs Richtungen

- Standard → YAML
- YAML → Standard
- Standard → HomeKit Manager
- HomeKit Manager → Standard
- YAML → HomeKit Manager
- HomeKit Manager → YAML

werden als `manual_required` beziehungsweise `blocked` ausgewiesen. Eine
automatische Migration ist nicht implementiert, weil für eine externe Custom
Integration kein nachgewiesener stabiler Core-Schreibvertrag mit garantiertem
Pairing- und Identitätserhalt vorliegt. Gleichnamige Bridges oder unklare
Quellen werden nicht automatisch zusammengeführt.

## Tests

Die Phase ergänzt Tests für:

- atomare Sicherung vor Ersatz;
- Dateiversionskonflikte;
- ungültige YAML-Dateien;
- fehlende Include-Dateien;
- Include-Pfade außerhalb des Konfigurationsverzeichnisses;
- fehlende Manager-Datei trotz Include;
- vollständige Home-Assistant-Integration und WebSocket-Registrierung;
- unverändert gesperrten HomeKit-Writer.

## Sicherheitsstatus

`apply_enabled = False` bleibt verbindlich. `HomeKitWriter.async_apply()` löst
weiterhin `HomeKitWriteDisabled` aus. Es gibt keinen alternativen produktiven
HomeKit-Schreibpfad.
