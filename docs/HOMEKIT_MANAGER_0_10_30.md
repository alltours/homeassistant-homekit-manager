# HomeKit Manager 0.10.30 – Read-only Reconciliation Export

## Datenpfad-Audit

Die Auswahlabweichungen werden im bestehenden Coordinator-Snapshot durch
`selection_reconciliation.reconcile_selection()` berechnet. Der Snapshot
enthielt bereits `deviations`, aber jede Zeile enthielt nur Klassifikation,
Entity-ID, Ursache, Severity und Quelle. Die zugehörigen Inventardaten,
Manager-Entscheidung und Runtime-Diagnose wurden nicht in die Zeile projiziert.

Der bestehende `inventory_export` exportierte nur Inventarzeilen und die
Runtime-Zusammenfassung. Er enthielt weder die vollständige
Reconciliation-Liste noch technische Befunde als separaten Bereich noch die
HAP-Identitäts-Baseline.

Der Frontend-Code zeigte in der HomeKit-Warnung nur Kategorie, Entity-ID und
Ursache. Ein dedizierter Reconciliation-Export war nicht vorhanden.

## Umfang

0.10.30 erweitert die vorhandene Snapshot-Struktur und fügt keinen parallelen
Reconciliation-Datenbestand ein. Der neue authentifizierte, read-only WebSocket
`homekit_manager/reconciliation_export` liefert:

- JSON mit Snapshot-, Bridge-, Reconciliation-, Diagnose- und Runtime-Daten,
- CSV mit einer Zeile pro Auswahlabweichung,
- separaten CSV-Dateien für technische Befunde und Runtime-HAP-Zuordnungen,
- Vollständigkeits- und Verifikationskennzeichen,
- Bridge-MAC, Port und Pairing-Status nur als nicht sensitive Statuswerte,
- AIDs und IID-Signaturen, sofern Core sie sicher offenlegt.

Keine Pairing-Schlüssel, PINs, Tokens, privaten Schlüssel oder Attribute werden
exportiert. Keine Config Entry, Filter-, Pairing- oder HAP-Persistenzoperation
wurde ergänzt.

## Frontend

Die Einstellungen enthalten eine eigene Reconciliation-Ansicht mit:

- vollständigen Einzelzeilen,
- Suche und Kategorienfilter,
- Native-/Manager-/Runtime-Auswahl,
- HAP-Publikationsstatus, AID, IID-Signatur und Evidenzquelle,
- separater Darstellung technischer Befunde,
- JSON- und CSV-Export,
- sichtbarem `NOT_VERIFIED`-Status.

## Sicherheitsgrenze

Die vorhandenen Apply-, Write-Grant-, Revision-, Migrations- und HAP-
Persistenzpfade wurden nicht geändert. Der neue Endpunkt ist admin-geschützt
und liest ausschließlich den bereits aufgebauten Coordinator-Snapshot.
