# HomeKit Manager 0.10.7 – Entwicklungsnachweis

## Ausgangspunkt und Sicherheitsgrenze

Der Branch basiert auf `v0.10.6`. Produktive Config Entries, Filter, Pairings,
Bridge-Identitäten und Home-Assistant-Reloads wurden in diesem Entwicklungsauftrag
nicht verändert.

## Ursachenanalyse

Der bestätigte Fehler ist eine Zustandsgrenze: `explicit_overrides` wird in
`homekit_manager.yaml` als Manager-Entwurf gespeichert. Diese Datei ist keine
native HomeKit-Konfigurationsquelle. In 0.10.6 bleibt der Legacy-Entwurf daher
wirkungslos, solange kein gesonderter Native-Apply ausgeführt wird. Ein
gesperrter oder nie eindeutig rekonstruierter Apply kann die 60 Ausschlüsse
nicht in `exclude_entities` übertragen. Die Oberfläche zählte zuvor nur lokale
ungespeicherte Vormerkungen; deshalb konnte sie bei einem vorhandenen gespeicherten
Entwurf und abweichendem nativen Filter „keine Änderungen“ zeigen.

Nicht aus dem Quellcode allein beweisbar sind die Ursache des konkreten
produktiven Zustands, der genaue Zeitpunkt eines früheren Apply-Versuchs und die
Apple-Home-Sichtbarkeit. 0.10.7 zeigt diese Zustände deshalb getrennt als
Manager-Wunsch, native Core-Auswahl und lesbare Laufzeitveröffentlichung.

## 0.10.7-Verhalten

- Neue Pläne verwenden eine ausdrückliche Positivlistenmigration; breite
  Domain-/Glob-Regeln werden nicht stillschweigend weitergeführt.
- Eine kanonische Positivliste schreibt alle sechs Home-Assistant-Filterfelder
  explizit; nur `include_entities` enthält Werte.
- Eine leere Positivliste wird blockiert, weil Core einen leeren Filter als
  „alles einschließen“ interpretiert.
- Gespeicherte Manager-Ausschlüsse werden nicht automatisch als vollständige
  Benutzerabsicht interpretiert. Die Migrationsvorschau zeigt sie separat und
  verlangt Bestätigung.
- Native Options-Verifikation und Laufzeitverifikation sind getrennte Status.
  Bei nicht lesbarer HAP-Zuordnung wird `verification_incomplete` gemeldet;
  es gibt keinen automatischen Retry.
- Der bestehende Testmodus und die lokale Schreibfreigabe bleiben ausdrücklich
  abgeschaltet, bis ein Benutzer sie außerhalb dieses Entwicklungsauftrags
  separat bestätigt.

## Regressionen

Die Regressionstests decken die bestätigte Legacy-Lücke, kanonische Filterfelder,
leere Positivlisten, Abweichungen zwischen gespeicherten Ausschlüssen und dem
nativen Filter, Laufzeit-Verifikationsgrenzen sowie die bestehende Chromium- und
WebKit-Oberfläche ab. Die 5.000-Entitäten-Pfade bleiben gebunden und event-loop-
freundlich; eine Performanceverbesserung wird nicht behauptet.

Die isolierte Reconciliation-Regression modelliert sieben eingeschlossene
Domänen, 60 gespeicherte Ausschlüsse und eine nachträglich auftauchende
Entität. Sie wird nicht automatisch in die Positivliste aufgenommen. Die
isolierten Core/HAP-Tests prüfen zusätzlich, dass ein autorisierter Apply nur
mit unverändertem Inventar-/HAP-Evidenzfingerabdruck erfolgt und ein
isolierter Rollback native Filter sowie die erhaltene Bridge-/AID-/IID-Identität
wiederherstellt.

## Offene Freigabegates

Eine vollständige Python-Integrationstest-Ausführung benötigt Python 3.14.x und
die gepinnten Home-Assistant-Abhängigkeiten. Der auf diesem Mac vorhandene
3.9-Interpreter kann diese Suite nicht ausführen. Vor einem Release müssen daher
die vollständige Python-Suite, Core 2026.11.0b0, Sicherheits-Audit, Browser-Suite,
Release-Archiv, CI und ein unabhängiger Read-only-Produktivvergleich erneut
bestätigt werden. Ein produktiver Apply ist kein Bestandteil dieses Nachweises.
