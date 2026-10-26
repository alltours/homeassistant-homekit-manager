# HomeKit Manager 0.9.16 – Entwicklungs- und Freigabestand

## Unterstützte Laufzeit

Version 0.9.16 ist auf Home Assistant Core `2026.10.4` versionsgebunden.
Der kontrollierte Anwendungspfad unterstützt ausschließlich bestehende
HomeKit-Config-Entries mit Quelle `SOURCE_USER`.

## Funktionsumfang

- native Home-Assistant-Panelregistrierung;
- zentrale Darstellung von Konfigurationsmethode, Bridges, Änderungen und
  Speichern;
- Geräte-, Gerätetypen- und Zonenansichten;
- serverseitige HomeKit-Filterauswertung;
- Entwürfe, Vorschau, YAML-Export und Konfliktprüfung;
- administrativ geschützte WebSocket-API;
- kontrollierter Options-Diff für reguläre `SOURCE_USER`-Bridges;
- Aktivierungsprüfung nach dem Core-Update-Listener;
- Bridge-spezifische Sperre gegen parallele Anwendungen;
- Chromium-Regressionstests für Light/Dark Mode und mobile Viewports.

## Sicherer Anwendungspfad

Der Backend-Befehl `homekit_manager/apply_options_diff` prüft erneut:

1. Administratorberechtigung;
2. Core-Version `2026.10.4`;
3. HomeKit-Domain;
4. `SOURCE_USER` als Quelle;
5. eindeutigen Bridge-Kontext;
6. Fingerprint und aktuellen Config-Entry-Zustand;
7. erlaubte Optionsschlüssel;
8. Erhalt nicht betroffener Optionen;
9. erfolgreichen Aktivierungsstatus `loaded`.

Der Frontend-Zustand ist keine Sicherheitsgrenze. YAML-importierte Bridges,
Migrationen, Pairing-Änderungen, Bridge-Neuanlage und direkte `.storage`-
Manipulationen bleiben gesperrt.

## YAML und Manager-Modus

YAML-Dateien und `homekit_manager.yaml` können gelesen, validiert, als Entwurf
gespeichert und exportiert werden. Eine verlustfreie Bearbeitung beliebiger
produktiver YAML-Dateien sowie eine sichere Aktivierung von `SOURCE_IMPORT`
wurde nicht nachgewiesen. Diese Wege werden daher nicht als aktive produktive
Konfiguration beworben und bleiben blockiert.

## Tests

Vor einer Veröffentlichung müssen mindestens folgende Prüfungen erfolgreich
sein:

- Python- und Home-Assistant-Integrationstests;
- echte isolierte HomeKit-E2E-Prüfung mit HAP-Controller;
- authentifizierter WebSocket-E2E-Test;
- Chromium und WebKit;
- HACS-Validierung;
- Hassfest;
- GitHub Actions;
- Release-Dateimanifest und SHA-256-Prüfungen.

Ein stabiler GitHub-Release darf erst nach vollständigem Nachweis aller
Releasekriterien erstellt werden.

## Bekannte Einschränkungen

- `SOURCE_IMPORT` ist kein unterstützter Schreibpfad.
- Eine vollständige authentifizierte WebSocket-Anwendung muss separat gegen
  eine isolierte echte Bridge nachgewiesen werden.
- WebKit-, HACS-, Hassfest- und GitHub-Actions-Nachweise sind für den finalen
  Release-Gate erforderlich.
- Eine produktive Installation ist nicht Bestandteil der Entwicklung.
