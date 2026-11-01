# HomeKit Manager 0.10.27 – Installationsbereitschaft

## Entscheidung

**CONDITIONAL GO – manuelle Read-only-Erstinstallation nach Benutzerfreigabe.**

Diese Entscheidung autorisiert keine produktive Installation, keinen Filter-Apply und keine native UI↔YAML-Migration. Sie bedeutet nur, dass eine kontrollierte Erstinstallation auf einer zuvor gesicherten produktiven Instanz vorbereitet ist, sofern die Vorbedingungen und Abbruchbedingungen aus den Installationsunterlagen erfüllt sind.

## Gate-Matrix

| Gate | Status | Nachweis / Einschränkung |
|---|---|---|
| Repository und Remote | `CODE VERIFIED` | `https://github.com/alltours/homeassistant-homekit-manager`; der frühere abweichende Repository-Name ist nicht autoritativ. |
| 0.10.27-RC | `CODE VERIFIED` | Ausgangscommit `089069ddc7ad840a751274871edf31893349dc8e`; Vorbereitungsbranch enthält nur diese Dokumentation bis zum neuen Commit. |
| Release-Paket | `TEST VERIFIED` | Reproduzierbarer Build mit 58 Integrationsdateien und `RELEASE_MANIFEST.json`. |
| Release-SHA-256 | `TEST VERIFIED` | `3efbe92a3207034d09dd345ee7ceb1b01864fd504291aa98fa30462cc46b87e9`; stimmt mit dem geprüften RC überein. |
| Stable-CI | `CI VERIFIED` | Run `41312670084`; Quality, Browser und Official Core HAP Acceptance erfolgreich. |
| HACS/Hassfest | `CI VERIFIED` | Run `41312670143` erfolgreich. Ein HACS-UI-Installationsnachweis dieses Auftrags liegt nicht vor. |
| Official Core | `TEST VERIFIED` | Full-Core-HAP-Nachweis auf Core 2026.10.4 ohne experimentellen Patch. Andere Versionen bleiben separat zu prüfen. |
| Read-only-Erststart | `CODE VERIFIED` / `TEST VERIFIED` | `async_setup` lädt Inventar, Diagnose, Panel und WebSocket; ohne Grant/Testmodus bleibt Apply gesperrt. Stable-Tests und Real-Core-Test belegen die Grenze. |
| Pairing-/HAP-Schutz bei Installation | `TEST VERIFIED` | Der geprüfte Installations-/Restartpfad erzeugt keine Pairings und keine Bridge; kein produktiver Nachweis. |
| Backup und Rollback | `CODE VERIFIED` | Verfahren dokumentiert; produktive Wiederherstellung wurde nicht ausgeführt. |
| Erster Filter-Apply | `NOT VERIFIED` | Absichtlich nicht ausgeführt. Ablauf ist in `HOMEKIT_FIRST_APPLY_PLAN_027.md` vorbereitet. |
| Native Migration | `CODE VERIFIED` | Im Stable-Pfad deaktiviert; keine produktive Quellenmigration. |

## Geprüfter Umfang

Der stabile Umfang umfasst Erkennung, Inventar, Diagnose, Planung, Vorschau, Export, authentifizierte WebSocket-Kommunikation und den separat autorisierten Filter-Apply für bestehende Bridges. Der Apply ist nicht durch die Installation aktiviert; er benötigt weiterhin die explizite Bridge-bound Schreibberechtigung und aktuelle Revision.

Nicht Bestandteil des Stable-Umfangs sind UI↔YAML-Quellenmigration, Config-Entry-Quellenwechsel, neue Bridge-Erzeugung, Pairing-Reset und direkte HAP-Persistenzverwaltung.

## Offene Einschränkungen

- Die HACS-UI-Installation auf einer produktiven Home-Assistant-Instanz wurde nicht automatisiert und ist `NOT VERIFIED`; der manuelle Custom-Integration-Weg ist der kontrollierte Erstinstallationsweg.
- Die tatsächliche Produktivumgebung, Core-Version und vorhandenen Bridges sind unbekannt und müssen unmittelbar vor der Installation neu aufgenommen werden.
- Ein produktiver Backup-Restore wurde nicht getestet; das ist ein Betreiber- und Home-Assistant-Recovery-Prozess.
- Der erste Apply bleibt eine separate, ausdrücklich zu genehmigende Aktion und wurde in diesem Auftrag nicht ausgeführt.

## Benutzer-Checkliste vor Installation

1. Aktuelle Core-Version und HomeKit-Config-Entries aufnehmen.
2. Vollständiges Backup erstellen, extern sichern und Verfügbarkeit prüfen.
3. Prüfsumme des ZIP vergleichen.
4. Sicherstellen, dass kein experimenteller Core-Patch installiert ist.
5. Manager ohne Write-Grant installieren.
6. Read-only-Inventar prüfen und mit der nativen HomeKit-Konfiguration vergleichen.
7. Bei jeder Unklarheit stoppen; keine Bridge löschen, kein Pairing neu erzeugen und keinen Apply ausführen.
8. Erst nach separater Benutzerfreigabe und neuem Backup den kontrollierten ersten Apply nach dem dokumentierten Plan durchführen.

## Abschlussbewertung

Für die **manuelle Read-only-Erstinstallation**: `CONDITIONAL GO`.

Für eine **produktive native UI↔YAML-Migration**: `NO-GO` – die Funktion bleibt deaktiviert.

Für einen **unmittelbaren produktiven Filter-Apply ohne vorherige Read-only-Bestandsaufnahme und Benutzerfreigabe**: `NO-GO`.
