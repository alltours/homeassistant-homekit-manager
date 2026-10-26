# HomeKit Manager 0.9.10 – UI/UX-Redesign

## Ziel und Status

Version 0.9.10 überarbeitet die Verwaltungsoberfläche auf Basis des bestehenden,
read-only geschützten Backends. Die Hauptnavigation wurde auf **HomeKit**, **Geräte**,
**Änderungen** und **Einstellungen** reduziert. Die bestehende Bridge-Konfiguration
bleibt die Baseline; ein leerer Entwurf wird nicht als aktueller Zustand dargestellt.

## Architekturentscheidungen

- Der aktuelle HomeKit-Status wird serverseitig im Inventory mit `current_status`
  (`included`, `excluded` oder `unknown`) ausgeliefert.
- `published` und `apple_home_visible` bleiben getrennte, konservative Felder. Eine
  Konfigurationsauswertung wird nicht als Sichtbarkeit in Apple Home ausgegeben.
- Die UI verwendet einen getrennten Draft-State. Nur Abweichungen vom aktuellen Zustand
  erscheinen unter Änderungen.
- Unbekannte oder nicht kompatible Entitäten bleiben nicht schaltbar.
- `set hass` aktualisiert nur den Verbindungsindikator. Ein vollständiger DOM-Aufbau
  erfolgt nicht bei irrelevanten Home-Assistant-State-Updates.
- Vorschau, Validierung, Speichern und YAML-Export verwenden weiterhin die bestehenden
  WebSocket-Endpunkte. Der produktive HomeKit-Schreibpfad bleibt gesperrt.

## Benutzeroberfläche

### HomeKit

Zeigt Bridge, Modus, Entitätszahlen, den aus der Konfiguration abgeleiteten Status und
offene Änderungen. Die Darstellung benennt ausdrücklich, dass keine Apple-Home-Sichtbarkeit
behauptet wird.

### Geräte

Die Standardansicht gruppiert kompakte Gerätezeilen nach Bereichen. Eine Gerätezeile zeigt
verständlichen Namen, Bereich, Entitätsanzahl und einen Status. Details öffnen die
zugeordneten Entitäten; technische IDs liegen in einem aufklappbaren Bereich. Die
Entitätenansicht, Suche, Status-/Kompatibilitätsfilter und ein expliziter Auswahlmodus
bleiben verfügbar.

### Änderungen

Zeigt ausschließlich geplante Abweichungen mit Vorher-/Nachher-Zustand. Vorschau,
Entwurfsspeicherung, Export und Verwerfen bleiben vorhanden. Das UI bezeichnet diese
Operationen als Vorbereitung und führt keine automatische HomeKit-Änderung aus.

### Einstellungen

Bridge-/Modusinformationen und der read-only-Sicherheitsstatus bleiben erreichbar.

## Responsive Design

Die Oberfläche nutzt Home-Assistant-Theme-Variablen, kompakte Listen, große Touch-Ziele
und eine mobile Media Query. Dark- und Light-Mode werden über die HA-Farbvariablen
unterstützt. Horizontale Tabellen sind in der neuen Standardansicht nicht erforderlich.

## Tests

| Prüfung | Ergebnis |
|---|---|
| JavaScript-Syntax | Erfolgreich (`node --check`) |
| Python-Kompilierung | Erfolgreich (`compileall`) |
| Frontend-Panel-Fixture | Erfolgreich |
| Python-/HA-Tests | 42/42 erfolgreich |
| Große synthetische Inventare | Bestehende Tests für 1.500, 2.500 und 5.000 Entitäten erfolgreich |
| Echter produktiver Browser | In dieser Phase nicht ausgeführt |
| Produktive Installation | Nicht ausgeführt |

## Sicherheitsstatus

`apply_enabled = False` bleibt unverändert. `HomeKitWriter.async_apply()` und die
bestehende HomeKit-Bridge-Konfiguration wurden nicht geändert. Es wurden keine produktiven
Dateien, Config Entries, Pairings, `.storage`-Daten oder HomeKit-Reloads ausgeführt.

## Offene Punkte

- Ein echter Browser-Screenshot und eine visuelle Abnahme auf iPhone/Desktop müssen noch
  gegen die Fixture beziehungsweise eine autorisierte Testinstanz ausgeführt werden.
- Die Backend-Filtersemantik ist durch die vorhandenen Tests abgesichert; zusätzliche
  reale Live-Datenprüfungen gegen mehrere produktive Bridges bleiben ausstehend.
- HACS-/GitHub-Release und Produktivinstallation sind nicht Teil dieses lokalen Branches.

## Releaseentscheidung

Der Branch ist ein lokal geprüfter Entwicklungsstand für 0.9.10. Ein Release oder eine
Produktivinstallation darf erst nach Browserabnahme, vollständiger CI und Review erfolgen.
