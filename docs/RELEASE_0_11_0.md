# HomeKit Manager 0.11.0

## Native Apply

HomeKit Manager 0.11.0 verbindet den ausdrücklich bestätigten Auswahlentwurf mit der bestehenden Native-Apply- und Operations-Engine. Der Workflow ist:

1. Auswahl speichern.
2. Nicht mutierende Vorschau prüfen.
3. Einen bridge-, Snapshot-, Revisions- und Identitätsgebundenen Native-Apply-Plan erzeugen.
4. Den konkreten Diff ausdrücklich bestätigen.
5. Die bestehende Operation-Engine mit Locking, Journal, Write-Grant und Nachverifikation verwenden.

Der neue Pfad implementiert keinen zweiten Writer und schreibt nicht direkt aus dem Frontend. `REVIEW`, ungeklärte Identitäten, breite oder leere Filter, nicht verifizierte Nachfolger und ungeklärte stale Includes blockieren den Apply. Die letzte verbleibende Include-Entity darf nicht in einen unbeabsichtigten breiten Filter entfernt werden.

## Sicherheitsgrenzen

- Entwurfsspeicherung erzeugt keinen Write-Grant.
- Native Apply erfordert Administratorrechte, einen konkreten Plan, eine neue Bestätigung, einen gültigen planbezogenen Write-Grant und eine frische Zustandsprüfung.
- Produktions-Write-Grants werden nach einer begonnenen oder abgeschlossenen Operation nicht erneut als Apply-Freigabe akzeptiert.
- Ein expliziter Rollback benötigt eine neue unabhängige Produktionsfreigabe.
- Unbekannte Operationsergebnisse werden nicht automatisch wiederholt.
- Die bestehende Journal-, Locking-, Recovery- und Writer-Architektur bleibt maßgeblich.

## Identität und HomeKit

Native Apply aktualisiert ausschließlich die freigegebene HomeKit-Config-Entry-Option `filter`. Config-Entry-Identität, Bridge-Identität, Pairing-Persistenz und HAP-Persistenz werden nicht neu erzeugt. Eine tatsächliche Apple-Home-Clientbestätigung ist nicht Bestandteil lokaler Core-/HAP-Tests und bleibt entsprechend separat zu bewerten.

## Einschränkungen

- UI↔YAML-Migration bleibt außerhalb dieses Releases.
- Ein Apply ist nur für die bereits verifizierten Core-/Quellpfade freigegeben.
- Pairing-Erhalt in einem realen Apple-Home-Client wird nicht behauptet, wenn nur isolierte HAP- oder Core-Evidenz vorliegt.
- Ein vollständiger produktiver Apply wurde nicht ausgeführt.
