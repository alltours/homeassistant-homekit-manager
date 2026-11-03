# HomeKit Manager 0.10.32-rc.3

## Scope

RC3 finalisiert die Sicherheitssemantik des persistierten Operationsjournals
für Native Write/Apply und Rollback. Die UI↔YAML-Migration bleibt außerhalb des
Scopes und produktiv deaktiviert.

## Journal-Sicherheit

- Die Journalprüfung verwendet einen unkeyed SHA-256-Digest zur Erkennung von
  Korruption und widersprüchlichen Records.
- Der Digest wird nicht als kryptografische Authentizität oder als
  Autorisierung bezeichnet.
- Journaldaten autorisieren niemals selbst einen nativen Write.
- Native Apply- und Rollback-Vorgänge benötigen weiterhin Administratorstatus,
  konkrete Bestätigung, aktuelle Revisionen, Live-Zustandsprüfung, exklusives
  Locking und einen gültigen Write-Grant.
- Nach einem Neustart werden Bestätigungen und Write-Grants nicht wiederverwendet.
- Unbekannte oder widersprüchliche Zustände bleiben fail-closed.

## Sicherheitsgrenze

Ein Angreifer mit Schreibzugriff auf den gesamten Home-Assistant-
Konfigurationsspeicher kann einen unkeyed Digest neu berechnen. RC3 behauptet
nicht, diesen Angreifer durch kryptografische Journal-Authentizität abzuwehren.
Ein HMAC wird nicht eingeführt, weil Home Assistant für diese Integration keine
getrennte, gegen denselben Konfigurationsspeicher abgesicherte
Schlüsselverwaltung bereitstellt.

## Kompatibilität

Geprüfte Core-Versionen:

- Home Assistant Core 2026.10.4
- Home Assistant Core 2026.11.0b0

Produktive Home-Assistant-Instanzen, Pairings und Filter wurden nicht verändert.
