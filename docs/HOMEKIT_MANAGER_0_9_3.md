# HomeKit Manager 0.9.3

## Ziel

0.9.3 ergänzt die zentrale Oberfläche um read-only Geräte- und Bereichsansichten.
Die Daten werden ausschließlich aus dem vorhandenen Entity-Inventar abgeleitet; es
gibt keine Registry-Schreiboperationen und keine HomeKit-Aktivierung.

## Backend

- `grouping.py` aggregiert stabile Geräte- und Bereichsmodelle.
- `coordinator.py` hält die aggregierten Ansichten zusammen mit dem Inventar vor.
- `homekit_manager/devices` liefert Geräteansichten.
- `homekit_manager/areas` liefert Bereichsansichten.
- Beide Endpunkte erfordern Administratorrechte und sind read-only.

## Frontend

Die Navigation enthält zusätzlich:

- Geräte
- Bereiche

Jede Ansicht zeigt Anzahl, Verfügbarkeit, Kompatibilität, HomeKit-Freigabestatus und
die zugehörigen Entitäten. Die Darstellung ist für große Bestände kartenbasiert und
responsive; Aktionen bleiben auf Entwurfsdaten beschränkt.

## Sicherheitsgrenzen

- Keine Änderungen an HomeKit-Config-Entries.
- Keine Pairing- oder Bridge-Änderungen.
- Keine `.storage`-Manipulation.
- `apply_enabled = False` bleibt unverändert.
- `HomeKitWriter.async_apply()` bleibt gesperrt.

## Teststatus

- Python-Kompilierung: bestanden.
- JavaScript-Syntaxprüfung: bestanden.
- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests: 31 bestanden.

Die produktive 0.9.2-Installation war zum Zeitpunkt dieser Entwicklung noch nicht
vollständig verifiziert. Deshalb wurde 0.9.3 noch nicht veröffentlicht oder produktiv
installiert.
