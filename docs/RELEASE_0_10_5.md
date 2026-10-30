# HomeKit Manager 0.10.5

## Umfang

Diese Version setzt die konservative Geräteverwaltung des UX-Audits um.
Bereiche und reale Geräte besitzen getrennte Aktionen „Alle einschließen“ und
„Alle ausschließen“. Der Server löst den vollständigen Knoten unabhängig von
Suche, Ansichtsfiltern und Pagination auf. Die Vorschau nennt Gesamtzahl,
tatsächlich zu ändernde und bereits passende Entitäten sowie übersprungene
Entitäten mit Gründen. Eine Bestätigung speichert nur den Manager-Entwurf;
ein produktiver Apply ist ein eigener Vorgang mit eigenem Diff und eigener
Bestätigung. Ohne effektive Änderung entsteht kein neuer Entwurf.

Automatische Sammelaktionen lassen deaktivierte, ausgeblendete, Diagnose- und
Konfigurationsentitäten sowie Einträge mit fehlender Registry oder State,
unsicherer Gerätezuordnung oder nicht nachgewiesener HomeKit-Kompatibilität aus.
Die gleiche Schranke verhindert neue Includes über manipulierte Entwürfe.
Eine Sammelvorschau ist auf 10.000 Entitäten begrenzt; größere Knoten werden
mit einer konkreten Erklärung blockiert, statt eine unbeschränkte
WebSocket-Antwort zu erzeugen.
Eine ausdrücklich gewählte Einzeländerung ist nur im Rahmen der serverseitigen
Plan- und Schreibprüfung möglich. Ausgeblendete Einträge bleiben lesbar über
die Anzeigeoptionen; die Anzeigeoptionen ändern den HomeKit-Filter nicht.

Entitäten ohne Home-Assistant-Gerät erscheinen direkt unter ihrem Bereich und
nicht als künstliche Geräte. Namen folgen Benutzername, Registry-/State-Name
und Originalname; technische IDs und rohe Filterfakten stehen in Details.
Die Anzeigeoptionen verwenden auf Smartphones kompakte Checkboxen mit
komfortabel großen Touch-Flächen.
Status der regulär verwaltbaren Entitäten, aller Filtertreffer und des Entwurfs
sind getrennt. Die Filterbegründung verwendet nun denselben Wire-Wert in
Backend und Oberfläche.

## Kompatibilität und Sicherheitsgrenzen

Die Kompatibilitätsprojektion ist auf Home Assistant Core 2026.10.4 und
2026.11.0b0 begrenzt. Für die Beta wurden die HomeKit-Filter-/Registry-Gates,
Accessory-Zuordnung und neu hinzugekommenen Ozon-/Schwefeldioxid-Sensoren
gegen den versionierten Core-Code und isolierte Proben geprüft. Eine neue
Core-Version wird zunächst als nicht verifiziert behandelt. Der native
SOURCE_USER-Filter-Writer hat eigene Versionsgates für beide Versionen. Der
YAML-Schreibpfad bleibt auf 2026.10.4 beschränkt; komplexe YAML-Quellen
bleiben read-only. Die Positivlistenmigration breiter Filter bleibt auf den
gesondert isoliert verifizierten Fall Core 2026.10.4 begrenzt.

Der produktive Filter-Apply verlangt Adminrechte, eine vorhandene Bridge im
Modus `bridge`, Quelle, vollständige aktuelle Revision, Core-Schema,
serverseitig validierten Filter-Diff und Bestätigung der konkreten Operation.
Ein bestätigter Operationsplan allein ist keine Schreibfreigabe: Ohne aktiven,
befristeten Bridge-Testmodus oder gültige lokale Grant-Datei bleibt Apply
serverseitig gesperrt.
Vor der Mutation wird die Autorität erneut geprüft. Snapshot, Journal,
Nachverifikation und lesender Reconcile bleiben bestehen. Eine unbekannte
Ausgangslage wird niemals automatisch erneut geschrieben. Die alte direkte
Apply-Route bleibt gesperrt. Der befristete lokale Testmodus und die
Bridge-gebundene Grant-Datei bleiben als bestehende Wege erhalten.

Filterauswahl und erwarteter Accessory-Typ sind keine Belege für eine
HAP-Veröffentlichung oder Sichtbarkeit in Apple Home. Isolierte HAP-Tests
sind kein Test mit echter Apple-Home-Hardware. Dieses Release installiert
keine Dateien auf einer produktiven HA-Instanz, startet sie nicht neu,
aktiviert keinen Testmodus und verändert keine bestehende Bridge oder
Pairing-Datei.

## Installation und Rückkehr

Vor einer getrennt freigegebenen Installation ein wiederherstellbares
Home-Assistant-Backup prüfen. Das ZIP enthält nur die Integration.
Integrationsdateien austauschen und Home Assistant nur mit separater
produktiver Freigabe neu starten. Danach Version, Quelle, Bridge-ID,
Filter und Entwurf zunächst lesend vergleichen. Ein späterer Filter-Apply
benötigt erneut die konkrete Diff-Bestätigung und eine gesonderte produktive
Freigabe des Betreibers.

Für einen Code-Rollback die verifizierten Integrationsdateien von 0.10.4
mit separater Freigabe wiederherstellen und Core erst nach separater Freigabe
neu starten. Ein Code-Rollback macht angewendete Filter nicht rückgängig.
Unklare Operationen zuerst lesend über das Journal abgleichen; keine
automatische Wiederholung. `.storage/homekit.*` und Pairings nicht manuell
bearbeiten. Die allgemeinen Schritte stehen in
[Upgrade/Recovery](UPGRADE_0_10_0.md) und
[Write Authorization](WRITE_AUTHORIZATION_0_10_0.md).

## Bekannte Grenzen

- Keine echte Apple-Home-Hardwareverifikation und keine Zusage zum Pairing-Erhalt auf fremder Hardware.
- Keine YAML↔UI-Quellenmigration; keine Bridge-Neuanlage oder Pairing-Reset.
- Keine automatische Sammelaktion für unbekannte, bedingt unterstützte oder ohne State vorliegende Entitäten.
- Die produktive Version und der produktive Filter sind erst nach einer gesondert erlaubten Installation prüfbar.
