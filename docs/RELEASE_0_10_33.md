# HomeKit Manager 0.10.33

## Bestehende HomeKit-Auswahl vorbereiten

0.10.33 ergänzt einen ausdrücklich nicht mutierenden Entscheidungsworkflow für die spätere Übernahme einer bestehenden nativen HomeKit-Auswahl.

- Aktuelle native Auswahlen und die tatsächliche Runtime-Veröffentlichung werden getrennt angezeigt.
- Jede aktuelle Entität startet als `REVIEW`; keine Entität wird automatisch als `KEEP` übernommen.
- Historische Manager-Entscheidungen werden als Tombstones mit expliziten Optionen dargestellt.
- Veraltete native Include-Referenzen bleiben sichtbar und werden nicht automatisch entfernt oder ersetzt.
- Entscheidungen werden als bridge-gebundener, versionierter Manager-Entwurf gespeichert.
- Ein abweichender semantischer Snapshot-Fingerprint blockiert die Speicherung. Eine
  reine Revisionsfortschreibung ohne relevante Inhaltsänderung wird auf die aktuelle
  Revision normalisiert; vor jeder späteren Mutation bleibt eine frische vollständige
  Zustandsprüfung zwingend.
- Die Vorschau berechnet deterministisch einen hypothetischen Zielzustand und führt keine HomeKit-Änderung aus.

## Sicherheitsgrenzen

Das Speichern eines Entscheidungsentwurfs erzeugt keinen Write-Grant und autorisiert kein Apply. Der neue Workflow schreibt keine nativen Filter, lädt keine HomeKit-Bridge neu und verändert keine Pairings oder HAP-Persistenz. Native Apply- und Rollback-Gates bleiben unverändert gesperrt; UI↔YAML-Migration bleibt deaktiviert.

Die fachliche Übernahme der 23 bestehenden Entities sowie die Behandlung der sechs historischen Tombstones und der zwei stale Includes benötigen weiterhin ausdrückliche Benutzerentscheidungen und einen separaten, späteren Freigabeauftrag.
