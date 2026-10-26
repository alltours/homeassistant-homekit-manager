# HomeKit Manager 0.9.7

## Ziel

0.9.7 ergänzt eine deterministische, vorschlagsbasierte Regel-Engine für Entitäten.

## Regelmodell

Regeln besitzen stabile ID, Priorität, Aktivierungsstatus, Match-Bedingungen und die
Aktion `include` oder `exclude`. Unterstützte Match-Felder sind unter anderem Bereich,
Domain, Integration, Kompatibilitätsstatus, Verfügbarkeit und Entity-ID-Präfix.

Manuelle Entscheidungen haben Vorrang. Treffen aktive Regeln mit unterschiedlichen
Aktionen auf dieselbe Entität zu, wird ein Konflikt erzeugt und keine Entscheidung
automatisch übernommen.

## Schnittstelle

`homekit_manager/rules_preview` ist authentifiziert und read-only. Die Antwort enthält
Entscheidungen, Konflikte, die Regelanzahl und `applied: false`.

## Sicherheitsstatus

- Keine Regel wird automatisch gespeichert.
- Keine HomeKit-Option wird geändert.
- Keine YAML-Datei wird verändert.
- `apply_enabled = False` bleibt aktiv.
- `HomeKitWriter.async_apply()` bleibt gesperrt.

## Teststatus

- Python-Kompilierung: bestanden.
- JavaScript-Syntaxprüfung: bestanden.
- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests und Unit-Tests: 37 bestanden.

Die produktive Installation wurde nicht verändert.
