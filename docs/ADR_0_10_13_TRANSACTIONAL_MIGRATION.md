# ADR 0.10.13 – Transaktionale native Quellenmigration

## Status

Experimentell, nicht produktiv freigegeben.

## Kontext

Der isolierte HomeKit-POC kann `SOURCE_USER` und `SOURCE_IMPORT` unter
Erhaltung von Config-Entry-ID, HAP-MAC, Pairing, AIDs und IIDs wechseln. Core
stellt jedoch keine atomare Operation über Config-Entry-Store, YAML-Quelle,
Runtime-Unload/Setup und HAP-Persistenz bereit.

Deshalb muss jeder Versuch drei Zustände auseinanderhalten:

1. Der dauerhaft bekannte Journalzustand.
2. Der zuletzt bekannte Home-Assistant-Config-Entry-Zustand.
3. Der tatsächlich erreichbare HAP-Runtime-Zustand.

Eine einzelne Prüfsumme kann diese Zustände nicht ersetzen.

## Entscheidung

0.10.13 implementiert eine isolierte Transaktionsinfrastruktur, aber keinen
produktiven Quellenwechsel-Endpunkt.

Die Engine darf native Operationen nur mit einem expliziten
`experimental_test_permit` ausführen. Die produktive Integration verwendet
diesen Pfad nicht. URL-Parameter, Browser-Konsole oder Debug-Flags können die
Sperre nicht umgehen.

## Zustandsmodell

| Zustand | Bedeutung | Recovery |
|---|---|---|
| `IDLE` | Kein Journal vorhanden | Normaler Zustand |
| `PREFLIGHT` | Transaktion und Baseline angelegt | Vor nativer Änderung abbrechen |
| `LOCKED` | Prozess-/Bridge-Lock dauerhaft belegt | Preflight erneut prüfen |
| `SNAPSHOT_CREATED` | Snapshot und Fingerprints gespeichert | Nur vorbereiten oder abbrechen |
| `PREPARED` | Repräsentation und Revision geprüft | Nur vorbereiten oder abbrechen |
| `QUIESCING` | Runtime wird entladen | Nach Prozessverlust manuell prüfen |
| `SOURCE_SWITCHING` | Native Quelle wird geändert | Immer manuelle Prüfung bei Unklarheit |
| `RELOADING` | Bridge wird neu geladen | HAP- und Core-Zustand extern prüfen |
| `VERIFYING` | HAP-/Konfigurationsinvarianten werden geprüft | Nicht automatisch committen |
| `COMMITTED` | Commit-Operation vollständig bestätigt | Abgeschlossen, falls `commit` protokolliert |
| `ROLLBACK_REQUIRED` | Fehler nach kritischem Schritt | Expliziten Rollback verlangen |
| `ROLLING_BACK` | Rollback läuft | Bei Abbruch manuell wiederherstellen |
| `ROLLED_BACK` | Rollback vollständig bestätigt | Abgeschlossen, falls `rollback_complete` protokolliert |
| `FAILED` | Fehler vor nativer Änderung | Neue Transaktion erst nach Prüfung |
| `MANUAL_RECOVERY_REQUIRED` | Zustand nicht eindeutig | Keine automatische Mutation |

Vor jedem Seiteneffekt wird der neue Zustand persistiert. Danach wird die
Operation als abgeschlossen in einem zweiten Journalbild vermerkt. Ein
Prozessabbruch zwischen beiden Schreibvorgängen bleibt damit sichtbar
mehrdeutig und wird nicht als Erfolg interpretiert.

## Journal- und Dateisicherheit

`migration_journal.py` verwendet:

- eindeutige Transaktions-ID,
- Bridge-ID,
- Quelle und Zielquelle,
- Baseline-Fingerprint,
- Config-Revision,
- Zustandssequenz,
- abgeschlossene Operationen,
- Prüfsummen,
- Recovery-Status,
- redigierte Fehlerdiagnose,
- UTC-Zeitstempel.

Journals und Snapshots werden:

1. in einem restriktiven Verzeichnis angelegt,
2. in eine temporäre Datei im selben Verzeichnis geschrieben,
3. mit `fsync()` auf Dateiebene synchronisiert,
4. per atomarem `os.replace()` ersetzt,
5. mit einem Verzeichnis-`fsync()` abgesichert,
6. auf Modus `0600` gesetzt.

Ein beschädigtes Journal blockiert Recovery und führt zu
`MANUAL_RECOVERY_REQUIRED`.

## Snapshot-Regeln

Snapshots speichern nur:

- logisch vergleichbare Konfiguration,
- Dateigröße und SHA-256,
- HAP-/Pairing-Fingerprints ohne Geheimnisse,
- Bridge- und Transaktionsidentität.

Pairing-Secrets, Private Keys, PINs und Tokens werden weder im Snapshot noch
im Journal abgelegt.

Flüchtige Runtime-Werte werden nicht als bytegleiche Persistenz ausgegeben.

## Exklusive Sperre

`migration_lock.py` kombiniert:

- kernelbasierte Prozesssperre mit `flock`,
- Bridge-spezifische Lock-Datei,
- diagnostische Owner-Metadaten,
- PID, Host, Token und UTC-Zeitpunkt.

Die Metadaten allein autorisieren keine Recovery. Nach einem Prozessabbruch
gibt der Kernel den Lock frei; der Journalzustand entscheidet weiterhin, ob
eine Fortsetzung zulässig ist.

## Recovery-Entscheidung

Automatisches Fortsetzen ist nur für Zustände vor Quiesce denkbar. Nach
Quiesce, Source-Switch, Reload oder Verification ist der externe Runtimezustand
ohne HAP-/Core-Prüfung nicht eindeutig. Die Engine fordert dort manuelle
Recovery und führt keine Wiederholung irreversibler Schritte aus.

Rollback ist eine explizite Operation. Nach einem fehlgeschlagenen Rollback
wird `MANUAL_RECOVERY_REQUIRED` persistiert.

## Testnachweis

Die isolierten Tests decken ab:

- vollständige synchrone und asynchrone State-Machine,
- Journal-Roundtrip und Korruptionsblockade,
- monotone Journal-Sequenz,
- redigierte Snapshots,
- Lock-Konflikte,
- Revision Drift,
- expliziten Rollback,
- echte `SIGKILL`-Abbrüche,
- echte `SIGTERM`-Abbrüche,
- Recoveryklassifizierung nach Prozessverlust,
- reale HAP-Controller-Verifikation im bestehenden UI↔YAML-POC.

Der abschließende lokale Nachweis umfasst 299 Stable-Core-Tests, 182
Beta-Core-Unit-Tests, 117 Beta-Core-Integrationstests, 108 Chromium-/WebKit-
Browserfälle und 13 dedizierte Engine-/Fault-Tests. Der Prozess-Fault-Harness
beendet einen echten Workerprozess mit `SIGKILL`/`SIGTERM`; er ist jedoch kein
vollständiger SIGKILL während eines laufenden Home-Assistant-Core-
Commitfensters.

## Konsequenz

Die Engine ist ein belastbarer Sicherheitsbaustein, aber noch kein Beweis für
eine produktiv verantwortbare native Migration. Für eine Freigabe fehlen
weiterhin ein offizieller oder stabiler Core-Vertrag, Fehler-Injektion in
echten Core-Prozessen während jedes Commit-Fensters, vollständige HAP-
Rollbacktests und Apple-Home-Tests.
