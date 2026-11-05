# HomeKit Manager 1.0.1 – Release Candidate

## Ziel

1.0.1 behebt die Core-Kompatibilitätsfreigabe für Home Assistant Core 2026.11.0
und macht die dadurch blockierte Native-Apply-Funktion wieder nachvollziehbar
prüfbar. Die produktive HomeKit-Konfiguration wird durch diese Version nicht
automatisch geändert.

## Behobene Blocker

- Native Filter-Apply ist für den offiziell getesteten Core 2026.11.0
  freigegeben. Nicht verifizierte Folgeversionen bleiben gesperrt.
- Die HomeKit-Kompatibilitätsprojektion erkennt Core 2026.11.0 als verifiziert;
  unbekannte Core-Versionen bleiben `unknown` und werden nicht angewendet.
- Gespeicherte Manager-Entwürfe können für die aktuell ausgewählte Bridge nach
  ausdrücklicher Bestätigung verworfen werden. Dieser Vorgang entfernt nur den
  Manager-internen Entwurf.
- Ein lesender Alignment-Preview stellt native Includes, Manager-Metadaten,
  stale Entscheidungen und mögliche Metadaten-Schritte getrennt dar.
- Der Alignment-Abgleich kann nach Admin-Bestätigung native Includes als
  Manager-Metadaten übernehmen oder nachgewiesene stale Entscheidungen aus den
  Manager-Metadaten entfernen. Beide Vorgänge sind bridge-, Snapshot- und
  Dateiversionsgebunden und führen niemals Native Apply aus.
- Die Oberfläche bietet für eine geladene native Bridge auf Core 2026.11.0 die
  vorhandene kurzlebige, bridge-gebundene Schreibfreigabe verständlich an.
- Blockierte Änderungspläne nennen die betroffenen Entitäten und die konkrete
  Sicherheitsursache.

## Sicherheitsgrenzen

- Kein Apply durch Entwurfsspeicherung, Reconciliation oder Alignment-Preview.
- Ein Metadatenabgleich verändert ausschließlich die Manager-YAML-Metadaten;
  native Filter, Pairings und HAP-Persistenz bleiben unverändert.
- Die UI-Freigabe ist auf Administratoren, eine konkrete Bridge, 60 Minuten,
  einen neuen validierten Plan und eine eigene Apply-Bestätigung begrenzt.
- Write-Grants, Admin-Prüfung, Bridge-Bindung, Planbindung, Locking, Journal,
  Recovery und Rollback bleiben unverändert aktiv.
- Die Freigabe der Core-Version ersetzt weder eine lokale Schreibfreigabe noch
  eine explizite Benutzerbestätigung.
- Es werden keine Pairings, HAP-Persistenzdaten oder Config Entries verändert.

## Nachweis

Isolierte Tests wurden gegen Home Assistant Core 2026.11.0 ausgeführt,
einschließlich zweier HAP-Bridges, echter WebSocket-Planung, Apply,
Neustart/Reconnect und Recovery/Rollback. Ein vollständiger produktiver Apply
wurde nicht ausgeführt.

## Bekannte Einschränkung

Die lokale Core-Testumgebung meldet weiterhin eine optionale fehlende
`libturbojpeg`-Bibliothek. HomeKit- und Apply-Szenarien laufen dennoch; die
Bibliothek betrifft Kamera-Snapshot-Performance und ist kein Apply-Pfad.
