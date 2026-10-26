# HomeKit Manager 0.9.4

## Ziel

0.9.4 ergänzt eine reproduzierbare, konservative Diagnose für HomeKit-relevante
Konfigurationsprobleme. Die Diagnose behauptet keine tatsächliche Sichtbarkeit in Apple
Home und nimmt keine automatischen Korrekturen vor.

## Befundarten

- Nicht unterstützte Entität: kritisch.
- Unklare oder bedingt unterstützte Kompatibilität: Warnung.
- Nicht verfügbare Entität: Warnung.
- Veraltete Ein-/Ausschlussreferenz: Warnung.
- Explizite Mehrfachzuordnung zu mehreren Bridges: kritisch.
- Ungültiger YAML-Status: kritisch.

Jeder Befund enthält Code, Schweregrad, Titel, Detail, betroffene Entity-ID soweit
vorhanden und eine manuelle Handlungsempfehlung.

## Schnittstelle

Der authentifizierte Endpunkt `homekit_manager/diagnostics` liefert Befunde, Summen und
den aktuellen Fingerprint. Er ist read-only und führt weder HomeKit- noch Registry-
Änderungen aus.

## Frontend

Die Navigation enthält den Bereich „Diagnose“ mit Schweregradkarten und einer
sortierten Befundliste. Die Darstellung ist als Diagnosehilfe gekennzeichnet; sie
behauptet nicht, dass eine Entität tatsächlich in Apple Home sichtbar ist.

## Sicherheitsstatus

- `apply_enabled = False` bleibt aktiv.
- `HomeKitWriter.async_apply()` bleibt gesperrt.
- Keine `.storage`- oder Config-Entry-Manipulation.
- Keine automatischen Migrationen oder Korrekturen.

## Teststatus

- Python-Kompilierung: bestanden.
- JavaScript-Syntaxprüfung: bestanden.
- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests und Unit-Tests: 33 bestanden.

Die produktive Installation wurde nicht verändert.
