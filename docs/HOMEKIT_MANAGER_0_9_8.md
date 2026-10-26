# HomeKit Manager 0.9.8

## Ziel

0.9.8 ergänzt eine begrenzte Historie für gewünschte Konfigurationszustände und eine
sichere Wiederherstellungsvorschau.

## Historienmodell

Ein Eintrag enthält ausschließlich:

- Zeitpunkt
- Änderungsgrund
- validiertes Desired-State-Dokument
- Fingerprint
- `applied: false`

Pairing-Geheimnisse, Accessory-IDs und HomeKit-Identitätsdaten werden nicht gespeichert.
Die Historie ist auf die letzten 50 Einträge begrenzt.

## Schnittstellen

- `homekit_manager/history` liefert die Historie.
- `homekit_manager/history_restore` lädt einen Eintrag als neuen Entwurf.

Beide Endpunkte sind authentifiziert. Die Wiederherstellung führt keine Aktivierung,
keinen Reload und keine Config-Entry-Änderung aus.

## Sicherheitsstatus

- Wiederherstellung ist nur Entwurf.
- `applied` bleibt `False`.
- HomeKit-Writer bleibt gesperrt.
- Keine Pairing- oder Bridge-Daten werden protokolliert.

## Teststatus

- Python-Kompilierung: bestanden.
- JavaScript-Syntaxprüfung: bestanden.
- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests und Unit-Tests: 39 bestanden.

Die produktive Installation wurde nicht verändert.
