# Release Notes – HomeKit Manager 0.10.11

## Dual-Mode-Verwaltung

0.10.11 zeigt die beiden sicheren Verwaltungssichten `UI / Bridge` und `YAML` in
einer gemeinsamen Oberfläche. Die native Home-Assistant-Konfigurationsquelle
wird separat ausgewiesen.

## YAML

- deterministische YAML-Projektion
- Vorschau, Export und Core-Schema-Validierung
- Draft-Import ohne produktive Aktivierung
- Revisionen und Konflikterkennung bleiben aktiv

## Sicherheitsgrenze

Eine UI↔YAML-Quellenmigration wird nicht ausgeführt. Config-Entry-ID,
HAP-Persistenz, Pairings, AIDs, IIDs und Apple-Home-Zuordnungen werden nicht
durch Workarounds verschoben. Der Assistent zeigt den Blocker und die sichere
Alternative Vorschau/Export/Validierung.

## Upgrade-Hinweis

Das Update migriert keine bestehende Installation automatisch und verändert
keine produktive HomeKit-Konfiguration. Vor einem späteren produktiven Apply
bleiben die bestehenden 0.10.10-Sicherheitsfreigaben maßgeblich.
