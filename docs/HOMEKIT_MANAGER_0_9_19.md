# HomeKit Manager 0.9.19 – Sanierung und Release-Prüfung

Prüfdatum: 27.10.2026. Zielversion nach ausdrücklicher Nutzerentscheidung: **0.9.19**, Weiterentwicklung von 0.9.18. Kein Deployment, Push oder produktiver Neustart.

## A. Executive Summary

Der aktuelle Git-Stand wurde technisch überarbeitet und die vier Hauptseiten wurden neu gestaltet. Produktive HomeKit-Anwendungen sind unabhängig im Coordinator und Writer gesperrt. Entwürfe, Historie und Verwaltungszuordnungen bleiben von nativen HomeKit-Daten getrennt. Ein unbekannter Aktivierungszustand bleibt unbekannt; Wiederholungen erfolgen nicht automatisch.

**Entscheidung: C – NOT RELEASE READY für eine uneingeschränkte Produktionsfreigabe.** Ein reproduzierbarer, lokal geprüfter Release-Kandidat liegt vor. Die produktive Installation war nicht erreichbar. Ihre Version, Dateien, Pairings und der tatsächliche frühere Aktivierungsvorgang konnten nicht verifiziert werden. Zusätzlich besteht ein offener Sicherheitsbefund für die untersuchte Home-Assistant-Testlaufzeit: Pillow 12.3.0 hat 37 bekannte Advisory-Treffer. Eine Ausnutzbarkeit über Manager-Endpunkte ist nicht nachgewiesen.

Nachweise und ZIP: `/Users/felixalshut/Documents/ChatGPT/Homeassistant/evidence/homekit-manager-0.9.19/` (nachfolgend **E**).

Autoritatives Repository: `/Users/felixalshut/Documents/ChatGPT/homeassistant-homekit-manager`, Origin `https://github.com/alltours/homeassistant-homekit-manager.git`. Entwicklung im zugehörigen Git-Worktree `/Users/felixalshut/Documents/ChatGPT/Homeassistant/.worktrees/homekit-manager-0.9.19` (nachfolgend **R**), Branch `fix/homekit-manager-0.9.19-safety-ux`. Alle relativen Quellpfade beziehen sich auf R; **C** bezeichnet `custom_components/homekit_manager/` innerhalb R.

## B. Tatsächlicher Ausgangszustand

| Quelle | Festgestellter Zustand | Beweisgrenze |
|---|---|---|
| Alter Homeassistant-Ordner | Nicht versionierte Kopie 1.0.1; Gegenstand des früheren Audits | Keine aktuelle Produktbasis |
| Kanonisches Git-Repository | Version 0.9.18; Basis `13cc106781aae4ababd84972d35a62c3def85140`, Tag v0.9.18 | Verifizierter Quellstand |
| GitHub-Release 0.9.18 | Keine separat hochgeladenen Assets; öffentliches Quell-ZIP des Tags vorhanden | Nicht mit einer tatsächlich installierten Kopie gleichzusetzen |
| 0.9.18-Quell-ZIP | 35/35 Dateien stimmen mit Git und Release-Manifest überein, keine zusätzlichen Integrationsdateien | E/baseline-comparison.json |
| Produktive Installation | HTTP-Endpunkt 192.168.1.51:8123 nicht erreichbar; kein verwendbares Authentisierungstoken in dieser Sitzung | Aktive Version, Hashes, Core-Version und Bridge-Zustand NICHT BESTÄTIGT |
| Ursprüngliche iPhone-Screenshots | Nutzer meldet separate Zusendung; in diesem Gespräch keine Bildanhänge sichtbar | Kein belastbarer direkter Vorher/Nachher-Abgleich dieser Bilder |
| Vorhandene Vergleichsbilder | Acht gespeicherte 0.9.18-Ansichten aus dem kanonischen Repository | Herkunft nicht mit aktueller Produktion gleichzusetzen |

0.9.18 enthielt bereits Verwaltungsübernahme, Rückstellung, Aktivierungs-API, Migrationsplanung und die vier Hauptbereiche. Diese Funktionen wurden selbst im Code untersucht; frühere Abschlussbehauptungen wurden nicht als Testnachweise übernommen. Die unveränderte Python-Baseline bestand mit 70 Tests. Die zusätzliche unversionierte Datei `www/homekit-manager 2.js` und vorhandene Screenshots im kanonischen Checkout wurden nicht verändert.

## C. Vergleich mit dem Audit vom 27.10.2026

Das ursprüngliche Audit ist unter E/original-audit-2026-10-27.md gesichert. Es beschreibt die alte Kopie; die folgende Bewertung bezieht sich ausdrücklich auf die aktuelle Git-Basis.

| Audit-ID | Zustand in 0.9.18 | Ergebnis 0.9.19 und Nachweis |
|---|---|---|
| HKM-REL-01 | Bereits behoben hinsichtlich aktueller Quell-/Archivabweichung; historische 1.0.1-Abweichung bleibt historische Tatsache | Vollständige Manifestprüfung und deterministischer Builder, scripts/build_release.py:18,56; tests/test_release.py |
| HKM-UI-01 | Bereits behoben | Python und JavaScript registrieren `homekit-manager-panel`; C/panel.py:13; echter Browser verwendet Backend-Registrierung |
| HKM-UI-02 | Bereits behoben | Alle UI-Kommandos haben Backend-Handler; 28 registrierte Befehle, C/websocket.py; reale authentifizierte E2E-Prüfung |
| HKM-UI-03 | Bereits behoben | API verwendet include/exclude; UI-intern included/excluded werden serialisiert, C/www/homekit-manager.js:79 |
| HKM-HK-01 | Weiterhin vorhanden | Bridges, Accessories und unbekannte Modi getrennt; C/coordinator.py:166; test_remediation.py:39 |
| HKM-HK-02 | Weiterhin vorhanden | Modus-/Feature-abhängige Core-Projektion, C/compatibility.py:33; Kamera, Schloss, TV und Activity-Remote gegen native Core-Regel geprüft |
| HKM-API-01 | Weiterhin vorhanden | Status-Typprüfung vor Set-Zugriff; C/yaml_store.py:85; sechs fehlerhafte Statusvarianten kontrolliert abgewiesen |
| HKM-LIFE-01 | Weiterhin vorhanden | Eigene Handler werden beim Unload entfernt; Setup-Fehler räumen auf; statische Route wird nicht doppelt registriert |
| HKM-UX-01 | Teilweise behoben: Rückmeldungen vorhanden, Fokus-/Darstellungsprobleme verblieben | Fokus und Cursor erhalten; globale Lade-/Fehler-/Erfolgsmeldungen; Suche und Fehlerfälle in beiden Browsern geprüft |
| HKM-PERF-01 | Teilweise behoben: Teile der Dateioperationen bereits ausgelagert | Quellenprüfung vollständig im Executor; konsistenter Snapshot, Burst-Koaleszierung, begrenzte Render-Seiten und echte Messwerte |
| HKM-GATE-01 | Nicht überprüfbar bezüglich installierter Produktion; Nachweislücke weiterhin vorhanden | Lokale Nachweise erweitert; produktive Version/Hashes und Apple-Home-Abnahme bleiben offen |
| HKM-MAINT-01 | Teilweise behoben: Git-Historie existiert im richtigen Repository, alte Kopien bestehen weiter | Autoritative Basis festgelegt, genaue Testwerkzeug-Versionen und Lockfile; alte Kopien nicht weiterentwickelt |

### Anforderungs- und Funktionsmatrix des Sanierungsauftrags

| Funktion | Erwartung / tatsächliche Umsetzung | Prüfstatus |
|---|---|---|
| Einrichtung und Panel | Ein Admin-Panel, identischer Custom-Element-Name in Python/JS | BESTÄTIGT isoliert, echter Browser-/Backend-Test |
| Inventar und Status | Alle Registry-/State-Entitäten, eindeutige Bridge-/Accessory-Trennung | BESTÄTIGT isoliert; Produktivbestand NICHT BESTÄTIGT |
| Quelle und Verwaltung | Native Quelle lesend, bestätigte separate Verwaltungsmetadaten | BESTÄTIGT isoliert; kein Quellenwechsel |
| Suche und Filter | Name/ID/Gerät/Bereich, sieben kombinierbare Filter, Fokus stabil | BESTÄTIGT in Chromium/WebKit |
| Auswahl | Entität, mehrere Entitäten, Gerät und Bereich; Bulk-Dialog | BESTÄTIGT in Browser-Fixtures |
| Entwurf und Vorschau | include/exclude, Bridge-Bezug, Konfliktnachweis, keine Anwendung | BESTÄTIGT über echte HA-WebSockets |
| Speichern und Historie | Atomare Datei, Version/Backup, Erhalt anderer Bridges, Restore nur als Entwurf | BESTÄTIGT isoliert, einschließlich Fehlerfällen |
| Export | Validiertes Dokument als Dateidownload | BESTÄTIGT Backend und Browser |
| Aktivierung | In dieser Sanierung sichtbar und serverseitig gesperrt | BESTÄTIGT; reale Anwendung bewusst NICHT GETESTET |
| Unknown und Recovery | Neutral, persistent soweit Nachweise vorhanden, kein automatischer Retry | BESTÄTIGT isoliert; alter Produktivvorgang NICHT BESTÄTIGT |
| Einstellungen | Sechs vorhandene Abschnitte und echte Backend-Daten | BESTÄTIGT isoliert |
| Setup/Unload/Reload | Keine liegen gebliebenen eigenen Handler/Tasks | BESTÄTIGT isoliert |
| Mobile/Desktop/Themes | Vier Seiten ab 320 Pixeln, Light/Dark, zwei Engines | BESTÄTIGT in Testbrowsern; Original-iPhone-Abnahme NICHT GETESTET |
| Release | Version 0.9.19, vollständiges Manifest, identische Build-Bytes | BESTÄTIGT lokal; Veröffentlichung nicht beauftragt |

## D. Behobene technische Fehler und Befundregister

Prioritäten: P0 schützt Daten/Pairings; P1 beeinträchtigt wesentliche Funktionen oder die Freigabe; P2 betrifft relevante Qualität; P3 betrifft Optimierung. Sicherheitsgrade sind von Funktionsprioritäten getrennt. Die P0-Schreibsperre ist eine verbindliche Schutzmaßnahme, kein Beweis einer früheren Beschädigung.

| ID / Priorität / Komponente | Ursache und reproduzierbarer Nachweis | Auswirkung und Korrektur | Änderungsrisiko / Regression |
|---|---|---|---|
| HKM-019-01 / P0 / Schreibschutz | 0.9.18 hatte einen ausführbaren produktiven Optionspfad. In 0.9.19 Apply über echten Admin-WebSocket wiederholt anfordern: stets write_blocked; native Optionen unverändert | Backend sperrt vor Validierung, Statusänderung und nativem Zugriff. Writer weist allow_production unabhängig ab. C/coordinator.py:546; C/homekit_writer.py | Niedrig für Daten, bewusster Funktionsentzug. test_remediation.py:94; Writer-Gatetests |
| HKM-019-02 / P1 / Aktivierungsstatus | Früherer Vorgangsstatus lag nur im Speicher. Isolierten Vorgang als activating speichern, Manager entladen/laden: unknown, ohne Retry | Neuer begrenzter Store für Vorgangsnachweise; aktuelle Beobachtung getrennt vom historischen Ergebnis. C/activation_store.py:12; C/coordinator.py:267 | Mittel; neue Manager-Metadaten. test_remediation.py:74; unbekannte Request-ID und wiederholte Apply-Anfragen |
| HKM-019-03 / P2 / Inventar | Fehler mitten im Refresh konnte unvollständige Daten sichtbar machen. Aggregation absichtlich fehlschlagen lassen | Snapshot wird erst vollständig veröffentlicht; alter vollständiger Stand bleibt als veraltet markiert. Eine gebündelte API-Antwort enthält einen Bridge-Kontext. C/coordinator.py:166; C/websocket.py:37 | Mittel; Ereignis-/Nebenläufigkeitsänderung. Tests :51,176,214 |
| HKM-019-04 / P2 / Verwaltung | Persistierter Verwaltungsstatus verlor die native Quelle; Wiederladen konnte die Zuordnung als unbekannt ausweisen | Quelle wird gespeichert, Änderungen serialisiert, erwartete Bridge geprüft; Refresh-Fehler bestätigen keinen Erfolg. C/coordinator.py:396 | Mittel; nur Manager-Store. Test :147; beide Verwaltungsrichtungen im Browser |
| HKM-019-05 / P1 / Mehrfach-Bridge-Entwürfe | Speichern eines einzelnen Bridge-Dokuments ersetzte den gesamten Entwurfsinhalt. A und B nacheinander speichern | Neue Speicherung führt ausgewählte Bridge mit anderen Entwürfen zusammen; Historie lädt nur die aufgezeichnete Bridge. C/coordinator.py:507 | Mittel; Datei-Merge. Test :129 mit A/B, falschem Kontext und Historie |
| HKM-019-06 / P2 / Historie und Rückmeldung | Speicherung und UI-Historie konnten auseinanderlaufen; Historienfehler nach Dateischreiben waren nicht differenziert | Historie nach Speichern nachladen; bei Historienfehler wahrheitsgemäß „Entwurf gespeichert, Historie fehlgeschlagen“. C/coordinator.py:527; JS:142 | Niedrig; Fehlerzustand sichtbar. Test :202 und echte Browser-/Backend-Speicherung |
| HKM-019-07 / P2 / Regel-API | Nicht-Mappings/Listen als Aktion führten zu Typfehlern; Präfixregel las falsches Feld | Regeln kontrolliert validiert, entity_id_prefix liest entity_id. C/rules.py; Tests :190,196 | Niedrig; strengere Eingaben. Fehlertypen und echte Präfixentscheidung getestet |
| HKM-019-08 / P1 / Entwicklungswerkzeug | npm-Audit meldete Playwright <1.55.1 als betroffen von CVE-2025-59288 | Lokale Testabhängigkeiten auf 1.55.1 gepinnt, eigener node_modules-Baum; abschließendes npm-Audit ohne Treffer. package.json und package-lock.json | Niedrig für Produkt; Testbrowser muss zur Version passen. Alle Browserfälle erneut ausführen |
| HKM-019-09 / P1, OFFEN / Laufzeitabhängigkeit | pip-audit prüfte 112 Pakete der isolierten HA/HomeKit-Laufzeit: 37 Advisory-Treffer für Pillow 12.3.0, keine übersprungenen Pakete | Versionsbetroffenheit bestätigt; Erreichbarkeit der betroffenen Bild-/PDF-Pfade aus Manager nicht bestätigt. Keine eigenmächtige Core-/Produktionsänderung. E/python-advisories.json | Runtime-Update mittel bis hoch; Core-Abhängigkeiten gemeinsam validieren. Risikoentscheidung und erneutes Audit erforderlich |
| HKM-019-10 / P2 / Beschädigte Metadaten | Migrationszeit ohne Zeitzone konnte beim Vergleich TypeError auslösen; ungültige/zukünftige Zeit ist kein Nachweis | Ungültiger, naiver oder zukünftiger Zeitbezug wird unknown/stale. C/migration_store.py:16 | Niedrig; ausschließlich Manager-Metadaten. Vier Zeitvarianten, Test :235 |
| HKM-019-11 / P2 / Konfigurationsschutz | Entwurfsdateiname kann zugleich als native HomeKit-YAML-Quelle eingebunden sein; dies darf nicht überschrieben werden | Speichern bei erkanntem manager_include explizit gesperrt. Kein tatsächliches Überschreiben behauptet. C/coordinator.py:510 | Niedrig; absichtliche Schutzsperre. Test :224 prüft, dass keine Datei entsteht |

Zusätzlich wurden Fehler während der Sanierung durch Tests entdeckt und vor Abschluss korrigiert: null als erwartete Dateiversion beim ersten Speichern, veraltetes Prüfmanifest im temporären ZIP-Prüfordner und fehlende Chromium-Dateien nach Werkzeugupdate. Dies sind keine nachträglich behaupteten 0.9.18-Produktfehler. Endgültige Prüfergebnisse stehen in L/M.

## E. Architekturänderungen

Die vorhandene Python-/Webcomponent-Architektur bleibt erhalten; kein Neubau, keine zusätzliche Frontend-Laufzeitbibliothek, keine Mushroom-Abhängigkeit.

Datenfluss: Home-Assistant-Registries und States → reiner Inventaraufbau → native HomeKit-Metadaten und Core-basierte Filter-/Kompatibilitätsbewertung → gesperrter, atomarer Coordinator-Snapshot → adminpflichtiger WebSocket → JavaScript-Webkomponente.

Persistenz: atomare, versionsgeschützte Entwurfs-YAML mit Backup und Dateisperre; separate HA-Stores für Modus, Verwaltung, Historie, Migration und Aktivierungsnachweis. Die Historie bleibt auf 50 Einträge begrenzt, der Aktivierungsstore auf 100 Bridge-Datensätze. Es werden keine nativen Pairing-Dateien migriert.

Lifecycle: Setup rollt eigene Registrierungen bei Fehlern zurück; Unload beendet die eigene Refresh-Aufgabe, entfernt Listener, Panel und eigene WebSocket-Handler; Reload registriert diese erneut. Dateioperationen laufen über HA-Executor-Jobs. Ereignisse während eines Refresh gehen nicht stillschweigend verloren. Hintergrundaktualisierung wird koalesziert und auf ungefähr eine vollständige Aktualisierung pro Sekunde begrenzt. Das ist weiterhin ein Vollinventaraufbau, keine inkrementelle Datenbank.

Nachweise: C/__init__.py:19,55; C/coordinator.py:145,166,561; C/panel.py:16; C/websocket.py; C/yaml_store.py:232.

## F. Neues Designsystem

Einheitliche Karten, Buttons, Eingaben, Dialoge, Status-Badges, leere Zustände und Rückmeldungen. Gemeinsame Abstände, 16-Pixel-Kartenradius und Theme-Variablen für Hintergrund, Text, Trennlinien und Akzente. Primäre Buttons haben mindestens 44 Pixel Höhe. Kompakte segmentierte Umschalter und technische Aufklappbereiche ergänzen dies; eine pauschale WCAG-Konformität wird nicht behauptet.

Grün steht für bestätigte Einzelaktionen oder einen aus dem Backend gelesenen geladenen Bridge-Zustand; Gelb für Warnungen, Rot für Fehler, Blau für Navigation/Information, Neutral für unbekannte Ergebnisse. „Bridge geladen“ ist keine Behauptung einer erfolgreichen HAP-Verbindung oder Apple-Home-Veröffentlichung.

Die Aktionsleiste bleibt im Dokumentfluss, damit sie auf schmalen Bildschirmen keine Sicherheitshinweise überdeckt. Nachweis: C/www/homekit-manager.js:337 und Browseraufnahmen unter E/screenshots.

## G. HomeKit-Seite

Vier kompakte Kennzahlen: Bridge-Zustand, Konfigurationsquelle, Verwaltung und offene lokale Änderungen. Darunter Bridge-Auswahl und Details, verständliche Erklärung der Quelle, getrennte Verwaltungszuordnung und Inventar-/Entwurfsinformationen. SOURCE_USER bleibt ein technisches Detail.

Eine optische Quellkarte löst keine Migration aus. Übernahme/Rückstellung erfordern einen Dialog, Backend-Prüfung und eine bestätigte Antwort. Die Zuordnung verschiebt keine native Konfiguration und schaltet HomeKit-Anwendungen nicht frei. Accessories werden separat gezählt und sind keine Bridge-Ziele.

Nachweise: JS:245,259; C/coordinator.py:345,396; test_config_flow.py:277; Browser-Verwaltungstest.

## H. Geräte- und Entitätenverwaltung

Bereiche als kompakte Karten; Geräte und einzelne Entitäten als getrennte Ansichten. Namen, Entity-IDs, Geräte, Bereiche, Verfügbarkeit und Kompatibilität werden getrennt gezeigt. Suche berücksichtigt alle vier Namenstypen und erhält Fokus/Cursor. Filter: Domain, Bereich, Gerät, HomeKit-Konfiguration, Kompatibilität, Verfügbarkeit und Integration.

Einzelne Entitäten, Geräte und Bereiche können ausgewählt werden. Mehrfachänderungen zeigen Anzahl, Bridge, geplanten Status und übersprungene nicht bearbeitbare Entitäten in einem Dialog. Diese Aktionen erzeugen ausschließlich Entwürfe. Unbekannte Zuordnungen bleiben gesperrt; nicht unterstützte Entitäten können sicher ausgeschlossen, aber nicht eingeschlossen werden.

Kennzahlen sind ausdrücklich wie folgt definiert:

| Kennzahl | Definition |
|---|---|
| Entitäten | Eindeutige Entity-IDs aus Registry und State Machine; Registry-Einträge ohne Zustand bleiben sichtbar |
| Geräte | Unterschiedliche vorhandene device_id; Entitäten ohne Gerät werden separat ausgewiesen |
| Bereich | Entity-Bereich, sonst Gerätebereich; ohne Zuordnung eigener Bereich |
| Eingeschlossen | Effektiver nativer Bridge-Filter trifft zu; kein Veröffentlichungsnachweis |
| Ausgeschlossen | Effektiver Filter trifft nicht zu |
| Unbekannt | Keine eindeutig bewertbare Bridge-/Filterzuordnung |
| Unterstützt | Core-Projektion ergibt supported; bedingt und unbekannt werden nicht hinzugerechnet |
| Nicht verfügbar | Kein Zustand oder State unknown/unavailable |
| Kartenwerte nach Filterung | Nur aktuelle Such-/Filtertreffer; dies wird in der Oberfläche genannt |

Diese Mengen überlappen: „eingeschlossen“, „unterstützt“ und „nicht verfügbar“ sind nicht zu einer Gesamtsumme zu addieren. Ein physisches Gerät mit Entitäten in mehreren Bereichen kann in mehreren Bereichskarten vorkommen, während die globale Gerätezahl eindeutig bleibt. Entity-Seiten sind auf 80 Zeilen begrenzt; Bereichslisten paginieren Gerätegruppen.

Nachweise: C/inventory.py:58; C/grouping.py; JS:189,190,230; Frontend-Filter- und 5.000-Entitäten-Test.

## I. Änderungsverwaltung

Jede Änderung zeigt Namen, eigene Entity-ID-Zeile, bisherige/geplante Zuordnung, Bridge und verfügbare Vorschauwarnungen. Entwurf speichern, Vorschau und Export sind getrennte Aktionen mit Lade-/Fehler-/Erfolgsmeldungen. Export erzeugt einen tatsächlichen Dateidownload. Historische Entwürfe werden ausdrücklich nur als neue Entwürfe geladen.

Zustände werden getrennt beschrieben: lokaler Entwurf, validierter Entwurf/Vorschau, vorbereiteter Diff, laufender Vorgang, historisch bestätigter Vorgang, fehlgeschlagen und unbekannt. 0.9.19 startet keinen produktiven Anwendungsvorgang. Unterbrochene gespeicherte Zustände activating/saved werden nach Wiederanlauf unknown; aus unknown folgt weder Erfolg noch Fehler noch Retry.

**Zur ursprünglichen Unterbrechungsmeldung:** 0.9.18 konnte einen Verbindungsfehler beim Warten auf den Apply-Aufruf als unknown anzeigen. Das beweist weder, dass der Backend-Aufruf vor der Unterbrechung ausgeführt wurde, noch dass er nicht ausgeführt wurde. Der damals flüchtige Status kann nach Prozessverlust nicht rekonstruiert werden. In dieser Sitzung liegen keine produktiven Logs oder persistenten alten Request-Nachweise vor. Read-only lassen sich künftig aktueller Bridge-Zustand, Optionen und vorhandene Manager-Nachweise beobachten; eine Übereinstimmung allein beweist keinen historischen Aktivierungserfolg.

Apply ist sichtbar deaktiviert und backendseitig gesperrt, auch bei neuer Request-ID, aktivierter Verwaltungszuordnung oder direktem WebSocket-Aufruf. Nachweise: C/activation_store.py; C/coordinator.py:267,546; JS:142,155,266; Test :74,94.

## J. Einstellungen

Sechs tatsächlich implementierte Abschnitte: Allgemein, Konfiguration, Diagnose, Regeln, Historie und Performance. Allgemein zeigt Backend-Version, Core-Version, Bridge-/Accessory-Zahlen. Konfiguration trennt native Quelle und Entwürfe. Diagnose zeigt Abrufzeit, letzten vollständigen Backend-Stand und gruppierte Befunde. Regeln zeigt native Include-/Exclude-Filter lesend. Historie ermöglicht bestätigtes Laden als Entwurf. Performance zeigt tatsächliche Refresh-Dauer, Anzahl und Aktualisierungszeit statt roher JSON-Ausgabe.

Keine funktionsfähige Migration oder produktive Aktivierung wird durch ein scheinbar verfügbares Menü vorgetäuscht. Nachweise: JS:273; C/websocket.py und bestehende Backend-Tests für Regeln, Diagnose, Historie und Performance.

## K. Mobile Optimierung

Getestete Viewports: 320×740, 430×932, 768×1024 und 1440×900, jeweils Light/Dark in Chromium und WebKit. Vier erreichbare Hauptbereiche, eindeutige aktive Navigation, Tastatur-Pfeile/Home/End, getrennte Entity-IDs und klare Kennzahlen. Browserprüfungen messen Seiten-/Navigationsüberläufe und Kartenränder; keine festgestellten horizontalen Überläufe in den endgültigen Fällen.

64 reguläre Aufnahmen: vier Seiten × vier Viewports × zwei Themes × zwei Engines. Zusätzlich ein nichtleerer validierter Entwurf auf Smartphone und Desktop. Sichtprüfung repräsentativer mobiler und Desktop-Aufnahmen bestätigt die verbesserte Hierarchie; kein Ersatz für einen echten iPhone-/VoiceOver-Test. Die vorhandene 0.9.18-Aufnahme zeigte unter anderem abgeschnittene Navigation und rohe Performance-Daten. Die separat angekündigten ursprünglichen Bilder wurden nicht sichtbar empfangen und konnten nicht verglichen werden.

## L. Backend-Tests

**107 bestanden, 0 fehlgeschlagen, 0 übersprungen** in der endgültigen ZIP-Prüfung. Reale HA-Laufzeit: Core 2026.10.4, Python 3.14.9, pytest 9.0.3, Custom-Component-Testplugin 0.13.375. Jedes Integrationstest-Dateisystem ist separat temporär; native Test-Entries sind keine produktiven Bridges.

Gemessene Python-Anweisungsabdeckung: **1.673/1.932 = 86,59 %**, gerundet 87 %. Dies ist keine Funktionsvollständigkeit oder Branch-Coverage. Nicht ausgeführte Zeilen und einzelne Fehlerpfade bleiben in E/coverage.json sichtbar.

| Prüfgruppe | Tatsächlicher Nachweis |
|---|---|
| Einrichtung/Lifecycle | Config Flow, Singleton, Setup, Unload/Reload, Fehler beim Panel-Setup und Handlerbereinigung |
| API | Reale HA-WebSocket-Antworten; sämtliche 28 registrierten Kommandos verweigern Nicht-Admins |
| Inventar/Modell | Reale Registries, State-only-Entitäten, Bereiche, Bridge/Accessory-Trennung und vollständiger Snapshot bei Fehlern |
| HomeKit/Core | Filtersemantik und ausgewählte Modusregeln gegen installierten Core; Writer standardmäßig und produktiv gesperrt |
| Entwürfe | Schema, ungültige Typen, Vorschau, Export, atomare Dateiersetzung, Backup, konkurrierende Versionen, Mehrfach-Bridge-Erhalt |
| Persistenz/Recovery | Verwaltungsquelle nach Wiederladen; Vorgangsunterbrechung unknown ohne Retry; beschädigte Zeitangaben; Historienfehler |
| Ereignisse | 100 schnelle State-Änderungen werden koalesziert, letzter Zustand 99 bleibt im Inventar |
| Browser ↔ Backend | Chromium und WebKit laden den aus Python registrierten echten Modul-/Elementnamen, authentisieren sich am echten HA-WebSocket und speichern einen Entwurf; native Optionen bleiben unverändert |
| Release | Vollständige Dateiliste, Hash-/Quellvergleich, gleiche ZIP-Bytes und Abweisung veralteter Manifeste/unzulässiger Dateien |

Nachweise: E/release-tests.xml; E/coverage.json; tests/integration/test_browser_backend.py; tests/integration/test_remediation.py; tests/test_release.py. Ein früherer gemeinsamer Testinterpreter hatte pytest 9.1.1 statt der Plugin-Vorgabe; für die endgültige Prüfung wurde 9.0.3 separat installiert. `pip check` mit dieser isolierten Auswahl meldet keine gebrochenen Anforderungen.

## M. Frontend-Tests

JavaScript-Syntaxprüfung und Node-Verhaltenstest bestanden gegen den extrahierten Release. Browser-Abschlussstatus: **32 bestanden, 0 fehlgeschlagen, 0 übersprungen, 0 flaky**. Ausgeführt wurden 30 responsive/funktionale Fälle plus zwei fünfminütige Beobachtungen in Chromium/WebKit.

Fälle: alle Hauptseiten, alle Einstellungsbereiche, Navigation/Tastatur, Suchfokus, sieben Filter, Paging, Entwurf/Vorschau/Speichern, Datei-Export, gespeicherter Entwurf, Verwerfen, Mehrfachauswahl, Verwaltungsdialoge, unbekannter Status, sichtbare Transportfehler und begrenztes Rendern von 5.000 Entitäten. Im finalen Lauf benötigte die 80-Zeilen-Darstellung isoliert rund 27 ms in Chromium und 44 ms in WebKit; dies ist keine Produktionslatenz. Die meisten visuellen Fälle verwenden klar bezeichnete Fixtures; sie sind keine produktiven Funktionsnachweise. Die zwei zusätzlichen Browser-/HA-Tests in L verwenden den echten Backend-Transport und tatsächliche isolierte Persistenz.

Der frühere fünfminütige Lauf bestand in beiden Engines: je 300 irrelevante hass-Zuweisungen, Renderzähler 3 → 3 und 12 Fixture-Kommandos ohne weitere Abfragen. Der finale Lauf gegen das Release bestätigt dies ebenfalls; E/release-browser.json weist 32 erwartete Erfolge aus, Gesamtdauer 301,7 Sekunden. Eine solche Beobachtung beweist weder mehrtägige Stabilität noch die Abwesenheit von Memory Leaks.

## N. Sicherheitsprüfung

BESTÄTIGT: Admin-Prüfung aller registrierten Manager-Kommandos; HTML-Escaping benutzer-/backendgelieferter Texte; kontrollierte YAML- und Regelvalidierung; Include-Pfade werden auf den Konfigurationsbereich beschränkt; keine frei eingebbaren Prozessaufrufe im Manager. Native Schlüssel/Pairings werden nicht in Manager-Stores übernommen; der Reader entfernt sensible verschachtelte Felder. C/homekit_reader.py:32; C/config_source.py; C/www/homekit-manager.js:75; E/release-tests.xml.

BESTÄTIGT: Keine produktiven Apply-, Options-, Reload-, Pairing-Reset-, Bridge-Erstellungs- oder Migrationsoperationen wurden ausgeführt. Keine produktiven Dateien wurden beschrieben. Die isolierten Tests prüfen unveränderte native Testoptionen. Ein kryptografischer Vorher/Nachher-Vergleich produktiver Pairing-Dateien war mangels Zugriff NICHT GETESTET; „Pairing-Erhalt praktisch nachgewiesen“ wird nicht behauptet.

Behobener Entwicklungsbefund: Playwright 1.55.0 war vom Installer-Problem CVE-2025-59288 betroffen; Version 1.55.1 ist als korrigiert ausgewiesen. Das Problem betrifft bestimmte Browser-Installationsskripte und ist keine nachgewiesene Manager-WebSocket-Lücke. Quelle: [GitHub-Advisory](https://github.com/advisories/GHSA-7mvr-c777-76hp). E/npm-advisories.json meldet nach Update null bekannte npm-Treffer.

OFFEN: Der Python-Abgleich der 112 ermittelten Laufzeitpakete findet 37 bekannte Schwachstellen in Pillow 12.3.0; keine Pakete wurden übersprungen. Mindestens ein Hersteller-Advisory klassifiziert einen betroffenen PDF-Parser-Pfad als HOCH und nennt 13.0.0 als Korrektur. Quelle: [Pillow GHSA-p4wg-p73j-c528](https://github.com/python-pillow/Pillow/security/advisories/GHSA-p4wg-p73j-c528). Die 37 Treffer sind Versionsabgleiche, keine 37 durch den Manager reproduzierten Angriffe. Produktive Version und Erreichbarkeit der Bild-/PDF-Pfade sind NICHT BESTÄTIGT. Ein isoliertes Pillow-Upgrade gegen die HA-Pins wäre kein ausreichender Integrationsnachweis und wurde nicht als Produktionslösung ausgegeben.

Keine destruktiven PoCs wurden ausgeführt. Statische Prüfung, Tests und Advisory-Abgleich sind keine umfassende Penetrationsprüfung des gesamten Home Assistant oder des LAN.

## O. Release-Artefakt

Datei: E/homekit-manager-0.9.19.zip. **37 Integrationsdateien plus eingebettetes RELEASE_MANIFEST.json**, feste ZIP-Zeitstempel/Rechte/Reihenfolge. Versionsnummern in Manifest, Python-Konstante und Entwicklungspaket stimmen überein.

SHA-256: `cc3db29ff394ed063e9f67b6483a5d7167829f99da8cb4c4a057766e93e3bb71`.

Zwei unabhängig erzeugte Builds sind bytegleich. Jede Integrationsdatei ist im Manifest mit SHA-256 und Größe aufgeführt; unbekannte Dateien und Hashabweichungen werden abgewiesen. Tests werden im temporären Prüfordner mit den aus genau diesem ZIP extrahierten Integrationsdateien ausgeführt. Python-Syntax wird lokal kompiliert, JavaScript mit node --check geprüft. Die Quellhistorie bleibt im Git-Branch erhalten; das ZIP wird nicht als neue Entwicklungsbasis verwendet.

Die Reproduzierbarkeit ist lokal für die verwendete Python-/zlib-Laufzeit nachgewiesen; bytegleiche Kompression über beliebige andere Toolchain-Versionen ist NICHT GETESTET. CI wurde angepasst und Testwerkzeuge gepinnt; eine neue entfernte GitHub-Actions-/HACS-/hassfest-Ausführung wurde ohne Push nicht ausgelöst. Kein GitHub-Release veröffentlicht.

## P. Qualitätsbewertung

Punkte sind begründete technische Einschätzungen des untersuchten Kandidaten, keine Erfolgswahrscheinlichkeiten. Fehlende Produktionsnachweise begrenzen die Aussage.

| Kategorie | Punkte | Ergebnis, Nachweis und verbleibende Grenze |
|---|---:|---|
| Funktionale Korrektheit | 90 | Entwurfs-/Inventarabläufe isoliert geprüft; produktive Aktivierung ausdrücklich gesperrt |
| HomeKit-Sicherheit | 90 | Doppelte Schreibsperre, neutrale unknown-Behandlung, keine nativen Datenoperationen; kein realer Pairing-Vergleich |
| Backend-Stabilität | 88 | Lifecycle, atomare Snapshots, Fehlersimulation und Persistenztests; kein mehrtägiger Betrieb |
| Frontend-Funktionalität | 90 | Verhaltens-, Browser- und echte Backend-E2E-Prüfungen; HA-App-Shell produktiv nicht abgenommen |
| Mobile UX | 88 | Vier Seiten ab 320 Pixeln in zwei Engines; echtes iPhone und Originalbilder fehlen |
| Desktop UX | 88 | Klare Hierarchie und gleiche Arbeitsabläufe; keine moderierte Nutzerstudie |
| Designkonsistenz | 90 | Gemeinsame Theme-/Komponentenregeln, Light/Dark-Screenshots; beliebige Dritt-Themes nicht getestet |
| Wartbarkeit | 84 | Bestehende Module erhalten, weniger doppelte Verwaltungslogik, autoritative Git-Basis; große JS-Templates bleiben |
| Testabdeckung | 88 | 107 Python-Fälle, 86,59 % Anweisungen, echte WebSocket-/Browserpfade; keine vollständige Branch-/HAP-/Apple-Abdeckung |
| Release-Reproduzierbarkeit | 95 | Zwei bytegleiche Builds und vollständige Dateiprüfung; andere Plattform-/zlib-Versionen und entfernte CI offen |

Arithmetischer Mittelwert: **89,1/100** für diese zehn technischen Kategorien. Separater Sicherheitsvorbehalt: offene Pillow-Laufzeitbefunde und unbekannte produktive Abhängigkeiten verhindern eine pauschale Sicherheitsfreigabe. Der Mittelwert überstimmt kein Release-Gate.

## Q. Release-Entscheidung

**C – NOT RELEASE READY für eine uneingeschränkte produktive Freigabe.** Lokale Sanierung und prüfbares Artefakt liegen vor; die Gesamt-Abschlussbedingung ist wegen offener Nachweise und Laufzeit-Sicherheitsbewertung nicht vollständig erfüllt.

Erfüllt: konsistente UI-/Backend-Verträge, vier überarbeitete Hauptseiten, mobile Layoutverbesserung, nachvollziehbare Entwurfsaktionen, explizite Apply-Sperre, sichere unknown-Behandlung, keine produktiven HomeKit-Eingriffe und reproduzierbares Artefakt.

Vor Freigabe erforderlich: produktiven Installationsstand und Core-/Pillow-Version lesend belegen; Pillow-Treffer durch passende Core-Laufzeitkorrektur oder belastbare dokumentierte Risikobewertung behandeln; relevante Pairing-/Identitäts- und Apple-Home-Abnahme in einer getrennt autorisierten Umgebung durchführen; originale mobile Darstellung bzw. physisches iPhone prüfen. Das ist keine Aufforderung, während dieser Sanierung produktive HomeKit-Dienste neu zu starten.

Eine spätere Freigabe zum reinen Lesen/Planen kann separat bewertet werden. Die Wiederfreigabe produktiver Anwendungen benötigt einen eigenen geprüften Auftrag; sie ist kein kleiner Schalter in 0.9.19.

## R. Verbleibende Risiken und nicht geprüfte Bereiche

- Aktive produktive Version, Quellhashes, Frontend-Cache, Core-Version, Pairings, Bridge-Identität, AID/IID und frühere Request-Logs: NICHT BESTÄTIGT.
- Apple Home, reale Pairing-Verbindung, System-/HomeKit-Neustart, Netzunterbrechungen mit echten Geräten und Updates einer real gepairten Bridge: NICHT GETESTET. Produktive Pairings wurden nicht zurückgesetzt.
- Historischer unknown-Vorgang ohne persistierte Beweise: nicht nachträglich sicher entscheidbar; keine Wiederholung.
- Pillow-Advisories: Versionsbetroffenheit in Testlaufzeit BESTÄTIGT; produktive Exposition und Manager-Erreichbarkeit NICHT BESTÄTIGT.
- Mehrtägige Speicher-/CPU-Stabilität, Ressourcengrenzen auf dem Zielhost, Rediscovery im echten LAN und Last mit realen Geräten: NICHT GETESTET.
- Physisches iPhone, VoiceOver, vollständige WCAG-Prüfung, Browserzoom/Textvergrößerung über alle Kombinationen und beliebige Themes: NICHT GETESTET.
- GitHub Actions, HACS und hassfest auf dem neuen Commit: noch nicht entfernt ausgeführt. Python-Transitivabhängigkeiten besitzen keinen vollständigen Hash-Lock; die untersuchte Laufzeit ist in E/python-runtime-requirements.txt aufgezeichnet.
- Snapshot-Aufbau bleibt bei hoher Zustandsrate vollständige Arbeit im Event-Loop für die reinen Berechnungen; Koaleszierung begrenzt die Häufigkeit. Laufzeitwerte aus kleinen isolierten Systemen sind keine Produktions-SLA.

## S. Empfohlene nächste Schritte und Maßnahmenplan

| Paket / Befunde / Priorität | Konkreter Umfang und Zweck | Überprüfbare Akzeptanz / Tests | Produktionsauswirkung |
|---|---|---|---|
| AP1 – Installationsnachweis / HKM-GATE-01 / P1 | Version, Code-Hashes, HA-Version und relevante Metadaten lesend erfassen; Abweichung zum Kandidaten dokumentieren | Vollständige Dateiliste und eindeutige Zuordnung von Backend/Frontend; keine geheimen Inhalte im Bericht | Nur lesend, keine Reloads oder Änderungen |
| AP2 – Runtime-Sicherheit / HKM-019-09 / P1 | Alle Pillow-Treffer nach erreichbaren Pfaden bewerten; geeigneten korrigierten HA-/Pillow-Verbund isoliert auswählen und erneut prüfen | Keine unbehandelten relevanten HOCH/KRITISCH-Befunde; pip check, Advisory-Abgleich und vollständige Manager-Regression auf tatsächlich freizugebendem Core | Produktivupdate separat genehmigen; keine eigenständige Paketüberschreibung gegen Core-Pins |
| AP3 – Pairing-/Update-Abnahme / HKM-GATE-01, HKM-019-02 / P1 | Isolierte gepairte Testbridge mit Backup, Identitäts-/Mapping-Vergleich und realem Apple-Home-Client nutzen; Manager-Update und Recovery prüfen | Identität, Schlüssel- und AID/IID-Zuordnungen bleiben erhalten; Verbindung nach kontrolliertem Testneustart; keine automatische Wiederholung unbekannter Vorgänge | Ausschließlich Testbridge; Produktion unverändert |
| AP4 – Finale mobile Abnahme / HKM-UX-01 / P2 | Ursprüngliche Bilder nachreichen/zuordnen; vier Seiten auf physischem iPhone sowie mit Tastatur/VoiceOver prüfen | Keine abgeschnittenen Aktionen/IDs; Fokus, Statusansagen, Dialogabbruch und Textvergrößerung bedienbar | Zunächst isolierte Oberfläche; keine Apply-Freigabe |
| AP5 – Release-Nachweise / HKM-REL-01 / P2 | Branch reviewen, entfernte CI/HACS/hassfest autorisiert ausführen; ZIP und Manifest unverändert zuordnen | Alle erforderlichen Jobs am tatsächlich freizugebenden Commit grün; ZIP-Hash bestätigt; keine Test-Skips im Release-Gate | Veröffentlichung/Deployment separat, kein automatischer Neustart |
| AP6 – Langzeitprofil / HKM-PERF-01 / P3 | 24-Stunden-Test mit repräsentativen Registry-/State-Ereignissen, Heap/RSS/CPU und Refresh-Latenzen | Vorher definierte Ressourcenbudgets eingehalten, letzter Zustand korrekt, keine wachsenden Listener/Tasks | Nur isoliert; erst bei gemessenem Engpass inkrementelle Berechnung einführen |

Kein Komplettumbau empfohlen. Eine spätere Aufteilung großer JS-Templates und die Pinning-Strategie für CI-Actions können nach konkretem Wartungsbedarf erfolgen. Vorhandene Produktivkonfigurationen oder Pairings sind kein Testmittel.
