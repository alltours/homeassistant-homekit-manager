# HomeKit Manager 0.10.0: isolierte Performance-Evidenz

Stand 2026-10-28, Entwicklungsbranch; **kein produktiver Messwert und kein
Release-GO**. Testhost: Apple M4, 16 GiB RAM, Darwin 27.2.0 arm64, Python
3.14.9, Home Assistant Core 2026.10.4. Alle Entitäten und Bridges sind
synthetisch; die produktive HomeKit-Bridge wurde nicht benutzt.

## Befund und Korrektur

Ein unbeschränkter `homekit_manager/inventory`-WebSocket-Abruf mit 5.000
synthetischen Entitäten erzeugte 4.920.171 Byte und scheiterte am 4-MiB-Limit
des verwendeten `aiohttp`-Testclients (`MESSAGE_TOO_BIG`, Code 1009). Ein
Browser-Test, der 5.000 Entitäten direkt in das Panel setzte, konnte diesen
Transportfehler nicht entdecken.

Der Endpunkt liefert nun höchstens 500 Entitäten pro Seite und bindet jede
Antwort an Gesamtzahl, Inventar-Fingerprint und Refresh-Revision. Das Panel
holt alle Seiten und veröffentlicht nur einen vollständigen, konsistenten
Snapshot; bei Drift zeigt es einen Fehler. Der Endpunkt gibt keine beliebigen
State-Attribute mehr als Teil der Listenansicht zurück. Serverseitige
Kompatibilitäts- und Preview-Berechnungen behalten sie. Ein zweiter isolierter
Lauf mit 5.000 eindeutigen Registry-Geräten und 100 Bereichen zeigte, dass die
erste Antwort mit vollständigen Gruppierungen erneut das Clientlimit
überschritt (4.541.738 Byte, Code 1009). Deshalb enthält der Inventarkontext
keine Geräte-/Bereichsvollaggregate mehr. Ihre separaten WebSocket-Routen
liefern ebenfalls höchstens 500 Einträge mit Snapshot-Metadaten. Die
Panelansichten berechnen Gruppen aus dem vollständig geladenen Inventar.
Negative Tests sperren negative Offsets und Limits über 500. API-Clients müssen
für mehr als 500 Treffer selbst Seiten abrufen.

## Messwerte

Der reine Python-Rechenpfad (`scripts/benchmark_inventory.py`, 10 warme
Wiederholungen, 129 synthetische Gerätebezüge) misst Registry-Projektion,
Filter, Kompatibilität, Gruppierung und Diagnostik. `tracemalloc` ist während
der Messung aktiv. Er enthält keine Home-Assistant-Executorwartezeit und
keinen WebSocket- oder Browseraufwand.

| Entitäten | Median Wandzeit | p95 Wandzeit | Median CPU | `tracemalloc`-Peak |
|---:|---:|---:|---:|---:|
| 100 | 6,373 ms | 6,423 ms | 6,374 ms | 327.275 B |
| 500 | 24,774 ms | 25,417 ms | 24,775 ms | 1.298.807 B |
| 1.216 | 57,352 ms | 58,085 ms | 57,347 ms | 2.968.529 B |
| 5.000 | 232,465 ms | 235,352 ms | 232,459 ms | 12.249.286 B |

Der isolierte Core-/WebSocket-Test
(`tests/integration/test_performance_probe_0100.py`) erstellt Registry- und
State-Einträge, startet den Manager, misst drei manuelle vollständige
Aktualisierungen und liest anschließend alle Inventarseiten über einen
authentifizierten lokalen WebSocket. WebSocket-Zeit umfasst Senden, Core-
Serialisierung, Transfer und Empfang **aller** Seiten einschließlich Kontext.
Die Erzeugung der 5.000 Testeinträge liegt außerhalb der Messung; außerdem
sind Hintergrundereignisse während dieser Einzelmessung abgekoppelt und
separat auf Bündelung geprüft.

| Entitäten | Refresh-Median | WebSocket-Median | Seiten | Größte Antwort | Summe Antworten |
|---:|---:|---:|---:|---:|---:|
| 100 | 3,58 ms | 1,68 ms | 1 | 154.649 B | 154.649 B |
| 500 | 15,17 ms | 5,45 ms | 1 | 723.645 B | 723.645 B |
| 1.216 | 36,56 ms | 14,20 ms | 3 | 989.953 B | 1.747.685 B |
| 5.000 | 150,94 ms | 81,16 ms | 10 | 2.440.351 B | 7.160.337 B |

Die Tabelle oben bezieht sich auf den ersten Lauf **ohne** verknüpfte
Registry-Geräte. Im erweiterten Lauf mit 5.000 Geräten und 100 Bereichen
betrugen die Mediane 171,45 ms für den Refresh und 84,62 ms für alle zehn
Inventarseiten. Die erste Kontextseite war 2.378.149 Byte groß, die größte
Gruppenseite 317.411 Byte; alle Seiten blieben unter 4 MiB. Die Summe der
Inventarantworten betrug 7.498.771 Byte. Die Gruppenseiten wurden zusätzlich
über authentifizierte WebSocket-Abfragen auf Vollständigkeit geprüft.

Die Browser-Fixture zeigte bei 5.000 synthetischen Entitäten 80 DOM-Zeilen
pro Ansicht. Ein einzelner Render der Entitätenansicht lag im letzten
Chromium-Lauf bei 25,7 ms und im WebKit-Lauf bei 48 ms. Diese Werte sind
Fixture-Messungen im Desktop-Browser, keine iPhone- oder vollständigen
WebSocket-zu-Paint-Latenzen. Der neue Seitentest lädt 5.000 Entitäten über zehn
simulierte WebSocket-Seiten; ein zweiter Test verweigert einen Snapshot mit
Versionsdrift. Weitere Browserfälle prüfen Suche nach dem letzten Datensatz,
numerische Gesamtsortierung, Filter und Mehrfachauswahl über verschiedene
Transportseiten. Ein fünfminütiger Stabilitätstest in Chromium und WebKit
bestand mit unverändertem Renderzähler 3 und je 12 Fixture-Kommandos; dies
ist kein Lasttest gegen einen realen HA-Server.

Offen sind wiederholte E2E-Messungen mit produktionsähnlicher Last,
Browser-Speicherverbrauch, physisches iPhone/WebKit und eine
Messung bei tatsächlicher Home-Assistant-Ereignislast. Die Zahlen hier
begründen keine Aussage über die produktiven 1.216/375/251 Entitäten.
