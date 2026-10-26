# HomeKit Manager 0.9.6

## Ziel

0.9.6 erkennt mehrere HomeKit-Bridges und verhindert jede implizite Auswahl der ersten
Bridge.

## Verhalten

- Die Bridge-Liste wird vollständig angezeigt.
- Bei genau einer Bridge bleibt der bestehende read-only Kontext verfügbar.
- Bei mehreren Bridges wird `bridge_selection_required` gesetzt.
- Moduswechsel werden bei mehrdeutiger Bridge-Auswahl gesperrt.
- Änderungsplanung und HomeKit-Optionen bleiben bei mehrdeutiger Auswahl blockiert.
- Es werden keine Bridges angelegt, gelöscht oder verschoben.

Damit werden Bridge-Verwechslungen verhindert, auch wenn die vollständige interaktive
Auswahl- und Einzelbridge-Inventaransicht noch weiter ausgebaut werden muss.

## Teststatus

- Python-Kompilierung: bestanden.
- JavaScript-Syntaxprüfung: bestanden.
- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests und Unit-Tests: 35 bestanden.

Die produktive Installation wurde nicht verändert.
