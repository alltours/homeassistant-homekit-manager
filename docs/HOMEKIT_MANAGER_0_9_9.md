# HomeKit Manager 0.9.9

## Ziel

0.9.9 ergänzt die technische Performance- und Stabilitätsgrundlage für große
Inventare.

## Metriken

Der authentifizierte, read-only Endpunkt `homekit_manager/performance` liefert:

- Entitätsanzahl
- Anzahl nicht verfügbarer Entitäten
- Domain-Verteilung
- empfohlene Seitengröße
- Hinweis auf Virtualisierung bei sehr großen Beständen
- dokumentiertes event-driven Refresh-Modell

Die Antwort ist begrenzt und enthält keine Pairing- oder geheimen Daten.

## Stabilität

- Frontend-Inventar wird nur initial beziehungsweise explizit aktualisiert geladen.
- Normale Home-Assistant-State-Änderungen führen nicht zu vollständigem Inventar-Reload.
- Entitätsansicht verwendet Pagination.
- WebSocket-Endpunkte sind authentifiziert.

## Offene Reifeprüfungen

Noch nicht vollständig nachgewiesen sind:

- reale Home-Assistant-Live-Lasttests mit 2.500 und 5.000 Entitäten
- synthetische 2.500-/5.000-Entitätentests der Performance-Zusammenfassung sind abgedeckt
- der tatsächliche Inventaraufbau einschließlich deterministischer Sortierung ist für
  1.500, 2.500 und 5.000 synthetische Registry-/State-Einträge abgedeckt
- Tabellen-Checkboxen, Zustandsauswahlen, Sortiersteuerungen und Seitennavigation besitzen
  zugängliche Beschriftungen beziehungsweise tastaturbedienbare Controls
- mobile Layout-Regeln für schmale Ansichten sind statisch im Frontend enthalten und im
  Verhaltenstest auf Vorhandensein geprüft
- die Browser-Fixture liefert die seit 0.9.3 verwendeten read-only-Endpunkte für Geräte,
  Bereiche, Diagnose und simulierte Gerätevorschau
- vollständige mobile Browserabnahme
- vollständige Screenreader-Abnahme
- vollständige Übersetzungsabdeckung aller UI-Texte
- produktive Abnahme der gesamten 0.9.x-Kette

## Teststatus

- Python-Kompilierung: bestanden.
- JavaScript-Syntaxprüfung: bestanden.
- Frontend-Verhaltenstest: bestanden.
- Home-Assistant-Integrationstests und Unit-Tests: 42 bestanden.
- Echte Chromium-Fixture-Prüfung: bestanden; die Fixture wurde über einen kurzlebigen
  lokalen HTTP-Server geladen. Erfolgssicht, Fehleranzeige und leere Browserkonsole wurden
  geprüft.

Die produktive Installation wurde nicht verändert.
