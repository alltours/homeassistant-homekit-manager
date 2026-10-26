# HomeKit Manager 0.9.18 – UI-Wiederherstellung und Speicherverwaltung

## Ziel

0.9.18 verbessert die Darstellung des verifizierten Konfigurationszustands und stellt
eine sichere, geführte Prüfung eines möglichen Speicherwechsels bereit.

## Speicherarten

| Anzeige | Technische Bedeutung | Status |
|---|---|---|
| Standard | native HomeKit-Config-Entry, typischerweise `SOURCE_USER` | lesbar; Änderungen nur über den bestehenden, separat gesicherten Optionspfad |
| YAML | direkte YAML-/`SOURCE_IMPORT`-Konfiguration | lesbar; automatische Migration gesperrt |
| HomeKit Manager | Manager-Drafts und gewünschte Verwaltungsquelle | Draft-/Historien-Metadaten persistent; keine automatische Bridge-Aktivierung |

Grün und „Aktiv“ wird ausschließlich für die vom Backend erkannte und stabile Quelle
angezeigt. „Vorgemerkt“ ist kein aktiver Zustand.

## Migrationsmatrix

Alle Cross-Source-Richtungen sind absichtlich gesperrt: Standard → YAML, Standard →
HomeKit Manager, YAML → Standard, YAML → HomeKit Manager, HomeKit Manager → Standard
und HomeKit Manager → YAML. Core 2026.10.4 stellt für eine fremde Custom Integration
keine stabile öffentliche Migrations-API bereit, die Bridge-Identität, Pairings,
Reload-Lifecycle und Fehlerrollback zugleich garantiert. Der Assistent erklärt den
Blocker und schreibt keine HomeKit-Konfiguration.

Eine Auswahl derselben Quelle ist keine Migration. Sie kann nach expliziter Bestätigung
read-only erneut verifiziert werden. Das Ergebnis wird mit Zeitstempel gespeichert;
alte Statusdaten werden nach 15 Minuten als unbekannt markiert und nicht automatisch
wiederholt.

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
