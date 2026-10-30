# HomeKit Manager 0.10.6

## Umfang

Diese Version verdichtet die Oberfläche. Geschlossene Bereichs- und
Gerätekarten zeigen Namen, Anzahl der sichtbaren Entitäten, den Status der
regulär verwaltbaren Entitäten und die beiden getrennten Sammelaktionen.
Erweiterte Kennzahlen und der Filterstatus aller Entitäten bleiben in den
geöffneten Karten zugänglich. Die vier Anzeigeoptionen stehen eingeklappt im
Filterpanel. Aktive Abweichungen vom Standard werden am Filterpanel angezeigt.

Die HomeKit-Übersicht zeigt die ausgewählte Bridge, ihren aktuellen Ladestatus,
die vom Filter ausgewählten Entitäten und offene Änderungen. Die Auswahl durch
den Filter ist kein Nachweis der HAP-Veröffentlichung oder Apple-Home-Sichtbarkeit.
Sicherheitsrelevante Hinweise zur Positivliste, zum aktiven Testmodus und zu
unklaren Anwendungsvorgängen bleiben sichtbar. Quell- und Schreibdetails stehen
in den aufklappbaren technischen Details und in Einstellungen. Ohne Entwurf
zeigt die Änderungenansicht eine kurze Erklärung und den Weg zu Geräte.

Status unbekannter Filterauswahl wird weiterhin als „Nicht verifiziert“
gekennzeichnet, auch wenn keine Entität für automatische Sammelaktionen
geeignet ist. Die fachlichen Sammelaktionsregeln und der serverseitige
Filter-Apply sind gegenüber 0.10.5 unverändert.

## Sicherheits- und Kompatibilitätsgrenzen

Die freigegebenen Core-Versionen, Schreibquellen und Bedingungen bleiben wie
in [0.10.5](RELEASE_0_10_5.md): Native Bridge-Filter auf Core 2026.10.4 und
2026.11.0b0, sicher projizierbare YAML-Filter nur auf Core 2026.10.4.
Komplexe YAML-Strukturen und nicht verifizierte Core-Versionen bleiben
read-only. Der befristete native Testmodus startet deaktiviert. Jede produktive
Änderung verlangt weiterhin Adminrechte, einen aktuellen serverseitigen Plan,
exakte Revision, Bridge-Bindung und Bestätigung des konkreten Diffs. Der
Manager erzeugt keine Bridge und verändert keine HomeKit-Pairing-Datei.

Ein GitHub-Release installiert diese Version nicht auf Home Assistant. Eine
produktive Installation und jeder nötige Core-Neustart benötigen eine
gesonderte Freigabe. Das gilt ebenso für Testmodus und produktiven Apply.

## Installation und Rückkehr

Vor einer später freigegebenen Installation ein wiederherstellbares HA-Backup
und das veröffentlichte ZIP samt SHA-256 prüfen. Nur die Integrationsdateien
ersetzen; Core und HomeKit bleiben zunächst unverändert. Nach einem getrennt
freigegebenen Neustart Version, Bridge-ID, Quelle und Filter lesend vergleichen.
Für einen Code-Rollback die verifizierten 0.10.5-Integrationsdateien unter dem
gleichen Freigabeverfahren wiederherstellen. Ein Code-Rollback nimmt zuvor
angewendete Filteränderungen nicht zurück. Unklare Anwendungsvorgänge zuerst
lesend abgleichen und nicht automatisch erneut ausführen.

## Bekannte Grenzen

- Die Screenshots und Browsermessungen verwenden eine isolierte Fixture, keine
  produktiven Entitäten. Die produktive Version 0.10.5 wurde wegen eines
  gesperrten Macs in diesem Lauf nicht erneut im Browser vermessen.
- Ein physisches iPhone, VoiceOver und echte Apple-Home-Hardware sind nicht
  durch die automatisierten Chromium-/WebKit-Tests ersetzt.
- Die Positivlistenwarnung kann auf kleinen Bildschirmen viel Platz einnehmen;
  sie bleibt bewusst sichtbar, solange breite Filterregeln aktiv sind.
