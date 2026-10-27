# HomeKit Manager 0.9.19 – Nachtrag zu den fünf Originalaufnahmen

Datum: 27.10.2026. Dieser Nachtrag ergänzt den Abschlussbericht; frühere Angaben über nicht vorliegende Originalbilder sind erledigt. Alle fünf JPEGs wurden vollständig angesehen. Sie haben jeweils 589×1280 Pixel. Daraus wird kein bestimmtes iPhone-Modell oder CSS-Viewport abgeleitet.

## Quellen und Grenzen

Originale, Hashliste, Browsernachweise und neue Aufnahmen liegen unter `/Users/felixalshut/Documents/ChatGPT/Homeassistant/evidence/homekit-manager-0.9.19/original-reference/`. Die Gegenüberstellung `index.html` funktioniert lokal und lädt keine externen Ressourcen.

Die Bilder belegen die dargestellte Oberfläche zum Aufnahmezeitpunkt. Sie belegen nicht die installierte Integrations-/Core-Version, die tatsächliche Backend-Antwort, den Erfolg einer Aktivierung, einen Netzwerkabbruch oder den Zustand von Pairings. Der gegenwärtige Produktionsstand bleibt unbestätigt. Die sichtbare Navigation ist auf den Originalbildern vollständig vorhanden; aus den Bildern wird kein zuvor nachgewiesener Navigationsausfall abgeleitet.

## Direkter Vergleich

| Original | Sichtbarer Befund | 0.9.19 / Prüfbeleg |
|---|---|---|
| Foto 1 – Einstellungen | Technischer Modus homekit_bridge im Haupttext, fünf unterschiedlich verteilte Schaltflächen, wenig direkte Systeminformation. Die Klickfunktion lässt sich aus einem Foto nicht bewerten. | Sechs konsistente Einstellungsbereiche und unmittelbar sichtbare Version/Core-/Bridge-Werte. Referenztest prüft Erreichbarkeit der Ansicht und sechs Navigationsziele. |
| Foto 2 – Änderungen | Langer Anwesenheitsname, Entity-ID und Zustandswechsel laufen optisch zusammen. Unknown und ein behaupteter Verbindungsabbruch stehen oberhalb eines als normal verfügbaren Apply-Buttons. | Name/ID/Bridge auf eigenen Zeilen, bisher/geplant getrennt, unknown neutral, Apply ausdrücklich deaktiviert. Tests prüfen Textgrenzen, Zeilenabstand, Überdeckungsfreiheit und unterbliebene Apply-Anfragen. |
| Foto 3 – Geräte | Lange Bereichszeilen vermischen Geräte, Entitäten, eingeschlossene, kompatible und nicht verfügbare Werte. „Ohne Bereich: 190 Geräte“ ist ohne Definition nicht mit global 129 Geräten vergleichbar. | Bereichskarten mit getrennten Kennzahlen; eindeutige Geräte-IDs und Entitäten ohne Gerät separat. Test mit 1.172 synthetischen Entitäten und 129 eindeutigen Geräten prüft Werte, Mengen und Überläufe. |
| Foto 4 – Verwaltung/Bridge | Große grüne Fläche, „Änderungen anwenden: Verfügbar“, Backend-Verifikation als bestätigt, zusammengedrängter Bridge-Titel/Status. Global 129 Geräte, 1.172 Entitäten, 368 eingeschlossen, ein Entwurf. | Kompakte Statusübersicht, Quelle und Verwaltung getrennt, kein freigegebener Schreibpfad. Aktive Verwaltungszuordnung und unbekanntes historisches Anwendungsergebnis werden getrennt dargestellt. |
| Foto 5 – HomeKit oben | Viel erklärender Text vor den Kerninformationen; SOURCE_USER im primären Text; große grüne Quellenkarte. | Vier kompakte Kennzahlen, verständliche Quellenbezeichnung, technische Details nachgeordnet und native Quelle klar von Verwaltung getrennt. |

Die Originalbilder sind damit eine konkrete visuelle Referenz. Die neuen Bilder zeigen ausdrücklich isolierte Referenzdaten und keine aktualisierte Produktivinstallation.

## Zähler und Aussage des alten Codes

Im 0.9.18-Basiscommit `13cc106781aae4ababd84972d35a62c3def85140` verwendet `custom_components/homekit_manager/www/homekit-manager.js:96` für Entitäten ohne Geräte-ID eine Ersatzgruppe `entity:<entity_id>`. Zeile 99 zeigt die Anzahl dieser Gruppen als „Geräte“ an. Dadurch können physische Geräte und einzelne Entitäten ohne Gerätezuordnung in denselben Zähler eingehen.

Der Code erklärt eine mögliche Ursache des sichtbar schwer vergleichbaren Bereichszählers. Die konkreten produktiven Werte 190 und 129 können ohne das damalige Inventar und einen gemeinsamen Snapshot nicht vollständig nachgerechnet werden. Insbesondere wird kein neuer korrekter produktiver Bereichswert behauptet.

Die neue Frontend-Funktion `counts()` in `custom_components/homekit_manager/www/homekit-manager.js:189` zählt ausschließlich unterschiedliche vorhandene Geräte-IDs. Bereichs- und globale Gerätezahlen haben damit dieselbe Definition; Entitäten ohne Geräte-ID erscheinen separat. Backend-Aggregation: `grouping.py`.

## Unknown und vermeintlicher Netzwerkabbruch

Im alten JavaScript, Zeile 85, wird der Satz „Die Verbindung wurde während der Aktivierung unterbrochen“ im allgemeinen catch-Pfad bei unbekanntem Ergebnis erzeugt. Dieser Text unterscheidet nicht zuverlässig zwischen einem Netzwerkabbruch und anderen Fehlerursachen.

Foto 2 ist deshalb kein Nachweis eines tatsächlich erfolgten Netzwerkabbruchs oder einer bereits erfolgten Anwendung. Die Anzeige „Backend-Verifikation: bestätigt“ in Foto 4 bestätigt ihrerseits keinen historischen Aktivierungserfolg. Die Aufnahmen allein beweisen auch keine exakt gleichzeitigen Backend-Zustände.

0.9.19 übernimmt keine solche Ursache ohne Nachweis, löst keine automatische Wiederholung aus und sperrt produktive Anwendungen unabhängig von der Verwaltungszuordnung.

## Zusätzlicher bestätigter Befund HKM-019-12

Bei der Referenzprüfung fiel am bisherigen 0.9.19-Kandidaten abgeschnittener Buttontext „Entwurf speichern“ bei 393 Pixeln auf. Ein ergänzter Test der tatsächlichen Textrechtecke scheitert am vorherigen Release-ZIP in Chromium und WebKit: zwei erwartete Reproduktionsfehler, dokumentiert in `before-button-fix.json`.

Korrektur: Die mobilen Aktionsbuttons dürfen am Wortzwischenraum umbrechen, erhalten eine explizite Zeilenhöhe und werden innerhalb der Reihe auf gleiche Höhe gestreckt. Der Eingriff betrifft ausschließlich zwei CSS-Regeln in `styles()`; keine Python-, HomeKit- oder Persistenzlogik wurde verändert.

Priorität P2, Änderungsrisiko niedrig. Akzeptanz: Textrechtecke vollständig innerhalb der Buttons, gleiche Buttonhöhe, keine Überdeckung des Sperrhinweises, Apply weiterhin deaktiviert. Diese Kriterien bestehen in den acht ergänzenden Referenzfällen bei 320/393/430/1440 Pixeln und beiden Engines.

## Referenzdaten und Tests

Die Referenzdaten übernehmen sichtbare Bereichsgrößen und Teilmengenzähler als Layout-Szenario. Namen und Entity-IDs sind anonymisiert. Gerätezuordnungen und nicht sichtbare Daten sind künstlich. Die 72 Geräte und 190 Entitäten ohne Gerät des synthetischen Bereichs ohne Zuordnung sind Testwerte und keine Rekonstruktion der Produktion. Die zusätzlich benötigten 57 Entitäten liegen in einem ausdrücklich benannten zusätzlichen Testbereich.

Die Fixtures enthalten insgesamt 1.172 Entitäten, 129 eindeutige Geräte und 368 eingeschlossene Entitäten. Kennzahlen werden aus den einzelnen Testdatensätzen berechnet. Ein langer Name und eine längere Entity-ID prüfen das im Foto sichtbare Umbruchproblem.

Prüfdateien: `tests/frontend/screenshot_reference_data.mjs` und `tests/frontend/screenshot_reference.spec.mjs`. Die Referenzfälle sind in den lokalen Browser-Testbefehl und die Browser-CI aufgenommen. Sie ersetzen keine echten Backend- oder iPhone-Tests.

Es entstehen 32 neue Dark-Mode-Aufnahmen: vier Ansichten × vier Viewports × zwei Engines. 393 Pixel sind eine ergänzende repräsentative Testbreite, keine aus den JPEGs abgeleitete Geräteangabe.

Die abschließende gesamte Browser-Regression umfasst nun 38 funktionale/visuelle Fälle und zwei fünfminütige Beobachtungen. Endergebnis: **40 bestanden, 0 fehlgeschlagen, 0 übersprungen, 0 flaky**, Gesamtdauer rund 302,2 Sekunden. Die 107 Python-/HA-Tests wurden ebenfalls gegen das erneut extrahierte ZIP wiederholt und bestanden ohne Fehler oder übersprungene Tests. Der ZIP-Hash lautet `83f4383b7779f6b424eafed6cac156539ef86b0abe236a464e20cb5a05e6fa82`; der alte Kandidat ist unter `prior-release/` erhalten. Weitere Nachweise stehen im aktualisierten Hauptbericht und in `VERIFICATION.json`.

## Freigabestatus

Der fehlende Originalbildvergleich ist erledigt. Reale iPhone-/VoiceOver-Bedienung, aktuelle produktive Version, Pairing-/Identitätsnachweise und die offenen Pillow-Laufzeitbefunde sind weiterhin ungeklärt. Die Entscheidung **C – NOT RELEASE READY für eine uneingeschränkte Produktionsfreigabe** bleibt bestehen.

Kein Deployment, kein produktiver HomeKit-Optionsaufruf, kein Reload, kein Reset und keine automatische Wiederholung wurden ausgeführt.
