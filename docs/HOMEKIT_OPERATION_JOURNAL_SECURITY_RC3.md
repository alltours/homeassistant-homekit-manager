# Operationsjournal – Sicherheitssemantik RC3

## Speicherort und Vertrauensgrenze

Das Operationsjournal wird über Home Assistants `Store` unter dem Schlüssel
`homekit_manager.operations` im Home-Assistant-Konfigurationsspeicher geführt.
Die Integration schreibt keine eigene Persistenzdatei und verändert den
Home-Assistant-Store nicht direkt.

Der Journalinhalt ist für Neustart-Recovery und lesende Zustandsklassifikation
erforderlich. Er ist nicht selbst eine Schreibfreigabe.

## Integritätssemantik

Jeder Journal-Eintrag enthält einen SHA-256-Digest über seine serialisierten
Felder, ausgenommen das Digest-Feld selbst. Der Digest dient zur Erkennung von:

- zufälliger Beschädigung,
- unvollständigen oder widersprüchlichen Records,
- Änderungen ohne anschließende Digest-Aktualisierung.

Der Digest ist unkeyed. Er bietet keine kryptografische Authentizität gegen
einen Angreifer, der den Journalinhalt und den Digest gemeinsam ändern kann.
Eine erfolgreiche Digest-Prüfung bedeutet daher nur, dass der Record
strukturell konsistent mit seinem angegebenen Digest ist.

## Unabhängige Autorisierung vor nativen Writes

Ein nativer Write oder Rollback benötigt zusätzlich:

- eine authentifizierte Administratoraktion,
- eine Bestätigung der konkreten Operation,
- eine passende Config-Entry-ID,
- eine aktuelle Revision und einen aktuellen Fingerprint,
- einen frisch gelesenen nativen Filterzustand,
- den exklusiven Operations-Lock,
- einen gültigen, aktuellen Write-Grant,
- eine erfolgreiche Nachverifikation.

Journaldaten lösen keine automatische Mutation aus. Ein unbekannter oder
widersprüchlicher Zustand bleibt gesperrt. Nach einem Neustart werden alte
Bestätigungen und alte Write-Grants nicht wiederverwendet.

## Bedrohungsmodell

Die Integration schützt gegen:

- zufällige Journalbeschädigung,
- unvollständige Persistenz,
- veraltete oder widersprüchliche Zustände,
- nicht authentifizierte oder nicht administrative WebSocket-Aufrufe,
- fehlende, abgelaufene oder nicht passende Write-Grants,
- falsche Operationen, Config Entries und Revisionen.

Ein Angreifer mit Schreibzugriff auf den Home-Assistant-Konfigurationsspeicher
kann einen unkeyed Digest neu berechnen. Dieser Angreifer befindet sich damit
außerhalb der Dateisystem-Vertrauensgrenze der Integration. Der Digest darf in
diesem Szenario nicht als kryptografischer Manipulationsschutz bezeichnet
werden. Ein vollständiger Home-Assistant-Prozess- oder Konfigurationsbesitz
liegt ebenfalls außerhalb der Integrationsgrenze.

## Recovery und Rollback

Startup-Recovery ist ausschließlich lesend. Ein expliziter Rollback nach einem
Neustart benötigt eine neue Recovery-Bestätigung und einen neuen Write-Grant.
Der aktuelle Filter muss exakt dem zulässigen Zielzustand entsprechen. Bei
fehlender oder widersprüchlicher Evidenz wird der Vorgang blockiert.

## HMAC-Entscheidung

Für die definierte Home-Assistant-Integrationsgrenze wird kein eigener HMAC-
Schlüssel eingeführt. Home Assistant stellt für diese Integration keine
stabile, getrennte, gegen den Konfigurationsspeicher abgesicherte
Schlüsselverwaltung bereit. Ein neben dem Journal gespeicherter Schlüssel
würde dieselbe Dateisystem-Vertrauensgrenze teilen und keine belastbare
zusätzliche Sicherheit schaffen.

Falls künftig Schutz gegen einen Angreifer mit Schreibzugriff auf den gesamten
Home-Assistant-Konfigurationsspeicher gefordert wird, ist dafür eine
Core-seitig verwaltete Schlüssel- oder Secure-Storage-Schnittstelle nötig.
Diese ist nicht Bestandteil von RC3.
