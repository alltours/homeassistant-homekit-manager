# HomeKit Manager – Implementierungsstand

## Umgesetzt

- Minimaler Config Flow mit echtem Config Entry.
- Integration-Setup und Unload-Lifecycle.
- Event-basierte Aktualisierung des Inventars.
- Entity-, Device- und Area-Registry-Auswertung.
- Verfügbarkeits-, Disabled- und Metadatenmodell.
- Erkennung von HomeKit-Config-Entries ohne Schreibzugriff.
- Rekursive Redaktion sensibler Optionen.
- Filterauswertung für Include/Exclude-Entities, Domains und Globs.
- Konservative HomeKit-Kompatibilitätsklassifikation.
- Serverseitige Änderungsplanung, Konflikt- und Versionsprüfung.
- Atomare, validierte Desired-State-YAML mit Optimistic Concurrency.
- Admin-geschützte WebSocket-Befehle.
- Responsive Custom Panel mit Suche, Filtern, Sortierung, Auswahl, Entwurf,
  Vorschau, Export und Verweis auf den offiziellen HomeKit-Dialog.
- Browser-Smoke-Fixture für die isolierte visuelle/interaktive Panelprüfung.
- Desired-State-Datei-I/O wird bei Laufzeitpfaden über den Home-Assistant-Executor
  ausgeführt, damit keine synchronen Dateizugriffe den Event-Loop blockieren.

## Bewusst nicht aktiviert

`HomeKitWriter.async_apply()` ist eine harte Sicherheitsgrenze und wirft
`HomeKitWriteDisabled`. Es gibt keine Config-Entry-Updates, Reloads, Pairing-Operationen
oder direkten `.storage`-Zugriffe.

## Bewusste Statussemantik

„Konfiguriert durch Filter“ wird nicht als „in Apple Home sichtbar“ ausgegeben. Die
Veröffentlichung bleibt `unknown`, solange dafür kein belastbarer offizieller Read-only-
Nachweis existiert.

## Noch offen für 1.0-Abnahme

- produktiver Core-Mount-/Loader-Nachweis
- produktive Panel-Live-Abnahme
- vollständige Browser- und Frontend-Testautomatisierung
- produktiver, ausdrücklich freigegebener Übergabeprozess
- Live-Abgleich gegen die bestehende Bridge

