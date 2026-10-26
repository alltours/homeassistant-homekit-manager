# HomeKit Manager 0.9.17 – Stabilisierung und Funktionsreparatur

## Ziel

0.9.17 konsolidiert die native Verwaltungsoberfläche nach dem 0.9.16-Audit. Die
Änderung konzentriert sich auf Wiederherstellung bereits vorhandener Funktionen und
auf die korrekte Darstellung des Istzustands; sie ist kein neues Designsystem.

## Oberfläche

Die einzige Hauptnavigation besteht aus:

- **HomeKit** – Bridge-Auswahl, Konfigurationsquelle, Warnungen und Zusammenfassung.
- **Geräte** – bereichsgruppierte Geräte, Entitätenansicht, Suche, Auswahlmodus und
  kombinierbare Filter.
- **Änderungen** – ausschließlich geplante Abweichungen mit Vorschau, Validierung,
  Entwurfsspeicherung, Export und explizit gesperrter Anwendung.
- **Einstellungen** – Konfiguration, Diagnose, Regeln, Historie, Restore-as-Draft,
  Geräte-Service-Vorschau und Performance.

Der aktuelle HomeKit-Konfigurationsstatus wird von geplanten Änderungen getrennt. Ein
unbekannter Status wird nicht als Ein oder Aus dargestellt. Die Oberfläche behauptet
nicht, dass eine konfigurierte Entität tatsächlich in Apple Home sichtbar ist.

## Sicherheitsgrenzen

Der bestehende SOURCE_USER-/Core-gebundene Anwendungspfad bleibt unverändert. Der
Default-Writer verweigert Anwendungen; `apply_enabled` bleibt `False`. YAML-importierte
Konfigurationen, Pairing-Daten, `.storage`, Bridge-Identitäten sowie automatische
Reloads oder Migrationen werden nicht manipuliert. Restore aus der Historie erzeugt
ausschließlich einen neuen Entwurf.

## Technische Korrektur

Der Coordinator lädt den aktuellen YAML-Snapshot vor der Diagnoseauswertung. Dadurch
werden neue oder ungültige Snapshot-Zustände im selben Refresh-Zyklus diagnostiziert,
statt den vorherigen Snapshot zu verwenden.

## Korrekturrunde nach produktiver Funktionsprüfung

Die 0.9.17-Stabilisierung ergänzt die zuvor fehlenden Bedien- und Zustandsnachweise:

- Bridge-Karten lassen sich unabhängig auf- und zuklappen; der Zustand bleibt bei
  erneuten Renderings erhalten und wird nicht zwischen Bridges vermischt.
- Die Konfigurationsquellen zeigen die tatsächlich aktive Quelle und eine separat
  vorgemerkte Quelle. Eine Auswahl wird nicht als abgeschlossene Migration dargestellt.
- Entwürfe werden über den vorhandenen persistierenden Speicherpfad gespeichert, die
  neue Serverversion/Fingerprint-Antwort wird übernommen und ein anschließendes Laden
  liest den gespeicherten Zustand erneut ein.
- Der Bereich „Änderungen“ besitzt eine sticky Aktionsleiste mit sicherem Abstand für
  mobile Safari-Ansichten. „Anwenden“ bleibt bei deaktiviertem Schreibpfad gesperrt.
- Eine unterbrochene Aktivierung bleibt ausdrücklich `unknown`; es erfolgt keine
  automatische Wiederholung und der Benutzer erhält eine klare Statusmeldung.

Die Korrekturen ändern weder produktive Home-Assistant-Dateien noch HomeKit-Config-Entries,
Pairings, `.storage` oder Bridge-Identitäten.

## Verifikation

Die Phase wird gegen Home Assistant Core 2026.10.4 mit Python-Integrationstests sowie
Chromium- und WebKit-Browserprüfungen validiert. Die lokale Abnahme umfasst 63
Python-Tests, den Node-Paneltest, je 10 Chromium- und WebKit-Tests einschließlich
5.000-Entitäten-Rendering und die fünfminütige Chromium-Stabilitätsbeobachtung.
Produktive Installation, Merge, Tag und GitHub-Release sind nicht Bestandteil dieser Phase.
