# HomeKit Manager 1.0.0

## Produktumfang

HomeKit Manager 1.0.0 ist die produktive Verwaltungsschicht für bereits
vorhandene Home Assistant HomeKit-Bridges. Bridges, Geräte und Entitäten werden
bridge-gebunden angezeigt. Die Geräteansicht unterstützt Suche, Filter sowie
Gruppierung nach Bereich, Etage, Gerät und Entität. Etagen werden nur angezeigt,
wenn Home Assistant entsprechende Floor-Zuordnungen liefert.

Änderungen werden zunächst als Selection Draft gespeichert. Der Native-Apply-
Pfad erzeugt eine serverseitig geprüfte Vorschau und verlangt eine explizite
Bestätigung, einen planbezogenen Single-use-Write-Grant, Locking, Journalisierung
und eine Ergebnisprüfung. Native HomeKit-Filter sind die einzige produktive
Konfigurationsmutation dieses Workflows.

## Sicherheitsgrenzen

- Bridge-Wechsel werden vollständig neu geladen; Entwürfe bleiben an ihre Bridge
  gebunden.
- Sammelaktionen werden auf dem Server gegen den aktuellen Snapshot geprüft und
  können keine unbekannten, deaktivierten oder nicht unterstützten Entitäten
  stillschweigend einschließen.
- Veraltete Snapshots, unklare Identitäten, parallele Vorgänge und unbestätigte
  Ergebnisse blockieren fail-closed.
- Die experimentelle UI↔YAML-Source-Migration ist nicht Bestandteil des Produkts.
- YAML-Bridges werden erkannt und im unterstützten Umfang angezeigt; ein Wechsel
  zwischen UI- und YAML-Quelle wird nicht angeboten.

## Kompatibilität und Einschränkungen

Die automatisierte Abnahme deckt die im Repository festgelegten Stable- und
Beta-Core-Teststände, Real-Core-/HAP-Loopback, Browser-Regressionen und
Multi-Bridge-Isolation ab. Ein vollständiger Test mit einem echten Apple-Home-
Client ist eine separate manuelle Abnahme und wird durch die automatisierten
Tests nicht ersetzt.

Vor produktivem Apply müssen Benutzer die Bridge, die konkrete Vorschau und die
möglichen Auswirkungen auf bestehende Apple-Home-Szenen und Automationen prüfen.
