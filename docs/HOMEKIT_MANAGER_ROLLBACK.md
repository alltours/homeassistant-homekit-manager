# HomeKit Manager – Sicherungs- und Rückbauplan

## Sicherung vor Deployment

Vor jeder Übertragung werden ausschließlich diese produktiven Daten gesichert:

- das vorhandene Verzeichnis `/config/custom_components/homekit_manager/`;
- Dateiinhalte, Eigentümer, POSIX-Rechte und Zeitstempel;
- eine lesbare Dateiliste und SHA-256-Prüfsummen.

Nicht gesichert oder verändert werden HomeKit-Pairings, `.storage`, Config-Entries anderer
Integrationen oder Bridge-Daten.

Die Sicherung erhält einen Zeitstempel und wird vor der Übertragung durch Dateiliste und
Prüfsummen verifiziert.

## Rückbau

1. Deployment stoppen und keine weiteren Reloads oder Neustarts auslösen.
2. Fehler und Core-Logs sichern, ohne Geheimnisse zu protokollieren.
3. Nach ausdrücklicher Rückbaufreigabe ausschließlich den Manager-Dateipfad auf den
   gesicherten vorherigen Dateistand zurückführen.
4. Rechte, Eigentümer, Dateiliste und Hashes mit der Sicherung vergleichen.
5. Nur nach separater Neustartfreigabe einen Core-Neustart durchführen.
6. Loader, Config Flow, Setup und Unload erneut prüfen.

Der Rückbau verändert keine HomeKit-Config-Entry, Pairing-Identität, Accessory-ID, IID oder
`.storage`-Datei.

