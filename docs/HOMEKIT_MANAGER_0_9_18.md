# HomeKit Manager 0.9.18 – UI-Wiederherstellung und Speicherverwaltung

## Ziel

0.9.18 verbessert die Darstellung des verifizierten Konfigurationszustands und stellt
eine sichere, geführte Prüfung eines möglichen Speicherwechsels bereit.

## Tatsächliche Speicherarchitektur

HomeKit Manager trennt drei zuvor vermischte Begriffe:

1. **Konfigurationsquelle**: Home Assistant `SOURCE_USER`/Config Entry oder YAML
   (`SOURCE_IMPORT`). Das ist der Ort, aus dem Home Assistant die Bridge nativ
   lädt.
2. **Verwaltungsoberfläche**: Home Assistant selbst oder HomeKit Manager. Die
   Auswahl der Verwaltungsoberfläche verschiebt keine native Konfigurationsquelle.
3. **Entwurfsspeicher**: die getrennte, versionierte Manager-Persistenz für
   Entwürfe, Historie und Verwaltungsmetadaten. Sie enthält keine Pairingdaten,
   Tokens oder HomeKit-Geheimnisse.

Core 2026.10.4 verwaltet die native `SOURCE_USER`-Bridge über den Config-Entry-
und Options-Lifecycle. HomeKit Manager verwendet für zulässige Optionsänderungen
denselben geprüften Config-Entry-Optionspfad; die ausdrückliche Verwaltungsschaltung
verifiziert eine geladene `SOURCE_USER`-Bridge und persistiert nur, dass diese
Verwaltungsoberfläche für die konkrete Entry-ID aktiviert wurde. Es findet dabei
keine Migration und keine neue Bridge statt.

## Anzeige der Quelle und Verwaltung

| Kategorie | Auswahl | Bedeutung |
|---|---|---|
| Kategorie | Auswahl | Bedeutung |
|---|---|---|
| Konfigurationsquelle | Home Assistant | geladene native `SOURCE_USER`-Config-Entry |
| Konfigurationsquelle | YAML | YAML-/`SOURCE_IMPORT`-Quelle |
| Verwaltungsoberfläche | Home Assistant | native Home-Assistant-Verwaltung |
| Verwaltungsoberfläche | HomeKit Manager | verifizierte Verwaltung einer vorhandenen geladenen `SOURCE_USER`-Bridge |
| Entwurfsspeicher | HomeKit Manager | Entwürfe, Historie und Verwaltungsstatus; nicht die native Bridge-Konfiguration |

Die UI markiert ausschließlich den vom Backend verifizierten Zustand grün. Ein
vorgemerkter oder unbekannter Zustand bleibt davon getrennt.

Grün und „Aktiv“ wird ausschließlich für die vom Backend erkannte und stabile Quelle
angezeigt. „Vorgemerkt“ ist kein aktiver Zustand.

## Migrationsmatrix

Alle Cross-Source-Richtungen sind absichtlich gesperrt: Standard → YAML, Standard →
HomeKit Manager, YAML → Standard, YAML → HomeKit Manager, HomeKit Manager → Standard
und HomeKit Manager → YAML. Core 2026.10.4 stellt für eine fremde Custom Integration
keine stabile öffentliche Migrations-API bereit, die Bridge-Identität, Pairings,
Reload-Lifecycle und Fehlerrollback zugleich garantiert. Der Assistent erklärt den
Blocker und schreibt keine HomeKit-Konfiguration.

Eine Auswahl derselben Quelle ist keine Migration. Die Verwaltungsschaltung kann
nach expliziter Bestätigung eine geladene `SOURCE_USER`-Bridge erneut verifizieren
und den Verwaltungsstatus für genau diese Entry-ID speichern. Das Ergebnis wird
mit Zeitstempel und Request-ID gespeichert; alte Statusdaten werden nach 15 Minuten
als unbekannt markiert und nicht automatisch wiederholt. Optionsänderungen bleiben
zusätzlich durch Fingerprint-, Core-Version-, Admin- und Writer-Gates geschützt.

Eine YAML-Quelle (`SOURCE_IMPORT`) kann mit dieser Verwaltungsschaltung nicht
aktiviert werden, weil der Core dafür keinen gleichwertigen sicheren externen
Ownership-/Optionsvertrag bereitstellt.

Die Verwaltungsumschaltung ist außerdem von der Schreibberechtigung getrennt.
Bei aktiver HomeKit-Manager-Verwaltung meldet das Backend den Optionspfad als
`available`, sofern Bridge, Quelle, Core-Version und Writer-Gates gültig sind.
Bei Home-Assistant-Verwaltung bleibt der Optionspfad `locked`. Die grüne
Verwaltungsanzeige allein schaltet keine HomeKit-Schreiboperation frei.

Die Rückstellung auf Home Assistant speichert ausschließlich den Verwaltungsstatus
für die betreffende Entry-ID. Entwürfe, Historie und native HomeKit-Optionen bleiben
unverändert.

## UI-Änderungen

- aktive Speicherart als grüne Karte mit Häkchen;
- kompakter mobiler Footer mit zwei Hauptaktionen und Aktionsmenü;
- Filter standardmäßig geschlossen und mit Aktiv-Zähler;
- lange Entity-IDs und Gerätenamen umbrechbar;
- aufklappbare Bereichsgruppen mit Geräte-, Entitäts-, Kompatibilitäts- und
  Verfügbarkeitszahlen;
- gruppierte Diagnosemeldungen mit Anzahl, Details und Empfehlung;
- Backend-Progressmodell für den sicheren Verifikationspfad.

## Sicherheitsstatus

Der Migrationspfad verändert keine HomeKit-Config-Entries, Pairings, `.storage`-Dateien,
Bridge-Identitäten oder YAML-Dateien. Eine erfolgreiche Assistentenantwort bedeutet
„Quelle verifiziert“, nicht „Migration durchgeführt“.
