# HomeKit Manager – Deployment- und Rückbauplan

Verbindliche Detailfassung: `HOMEKIT_MANAGER_PHASE5B12_DEPLOYMENT_PREPARATION.md`.
Die dauerhaft geltende Abschlussbericht-Struktur steht in
`HOMEKIT_MANAGER_REPORTING_RULE.md`; der lokale Dateisatz mit Prüfsummen steht in
`HOMEKIT_MANAGER_RELEASE_MANIFEST_2026-10-26.md`.

## Aktueller Status

Der Release-Kandidat `1.0.0-rc1` ist lokal geprüft. Die produktive Installation darf nicht
ohne separate Freigabe verändert werden. `apply_enabled = False` bleibt verbindlich. Der
aktuelle Produktiv-Dateisatz ist nicht vollständig aus dem Core-Kontext hash-verifiziert.

Die Übertragung umfasst ausschließlich die 22 Dateien aus
`HOMEKIT_MANAGER_RELEASE_MANIFEST_1_0_RC1.json` in den tatsächlich nachgewiesenen Core-Pfad.

## Vorbedingungen vor einer Installation

1. Core-internen Konfigurationspfad mit dem autorisierten Read-only-Zugang nachweisen.
2. Dateiliste und Hashes des produktiven und lokalen Stands vergleichen.
3. Sicherung des aktuellen produktiven Custom-Component-Stands erstellen.
4. Prüfen, dass keine produktive Datei außerhalb des freigegebenen Zielpfads betroffen ist.
5. Separat freigeben: Übertragung, Home-Assistant-Neustart und Live-Test.

## Geplante Übertragung

Ziel wäre ausschließlich:

```text
/config/custom_components/homekit_manager/
```

einschließlich `manifest.json`, Python-Modulen, Übersetzungen und `www/homekit-manager.js`.
Es werden keine `.storage`-Dateien und keine HomeKit-Pairing-Dateien übertragen.

## Aktivierung

Nach einer ausdrücklich freigegebenen Übertragung wäre ein Core-Neustart erforderlich,
falls der Loader die Custom Integration nicht automatisch neu einliest. Danach folgen
nur lesende Prüfungen: Integrationserkennung, Config Flow, Panel, WebSocket-Responses,
Bridge-Lesung und Writer-Sicherheitsstatus.

## Rückbau

Bei Fehlern wird ausschließlich der zuvor gesicherte Manager-Dateistand zurückübertragen.
HomeKit-Config-Entries, Pairing-Daten und `.storage` bleiben unverändert. Ein Rückbau darf
ebenfalls nur nach ausdrücklicher Freigabe erfolgen.

