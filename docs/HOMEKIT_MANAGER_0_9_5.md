# HomeKit Manager 0.9.5

## Ziel

0.9.5 ergänzt eine sichere Gerätekonfigurationsvorbereitung und eine visuelle,
nicht persistente HomeKit-Vorschau.

## Vorschau

Der authentifizierte Endpunkt `homekit_manager/device_preview` akzeptiert ausschließlich
eine Entity-ID und optionale Vorschauwerte für `name` und `type`. Die Antwort enthält:

- simulierten Titel
- simulierten Service-Typ
- Domain und aktuellen Zustand
- begrenzte, nicht sensible Attribute
- unterstützte Vorschaufelder
- `simulation: true`
- `applied: false`

Unbekannte Optionen wie Pairing-Schlüssel werden abgelehnt. Die Vorschau behauptet
nicht, dass die Darstellung exakt der aktuellen Apple-Home-Oberfläche entspricht.

## Frontend

Die Entitätsdetailansicht bietet die Aktion „Simulierte HomeKit-Vorschau“. Das Ergebnis
wird als Simulation gekennzeichnet und nicht gespeichert.

## Sicherheitsstatus

- Keine Config-Entry-Änderung.
- Keine HomeKit-Aktivierung.
- Keine Pairing- oder Identitätsdaten.
- `apply_enabled = False` bleibt aktiv.
- `HomeKitWriter.async_apply()` bleibt gesperrt.

## Teststatus

- Python-Kompilierung: bestanden.
- JavaScript-Syntaxprüfung: bestanden.
- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests und Unit-Tests: 35 bestanden.

Die produktive Installation wurde nicht verändert.
