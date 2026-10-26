# Historische HomeKit-Manager-Releases 1.0.x

## Sicherungsnachweis vor der Bereinigung

Die folgenden GitHub-Releases und Tags wurden vor der ausdrücklich freigegebenen Löschung geprüft und dokumentiert. Die zugehörigen Git-Commits bleiben erhalten.

| Release | GitHub-Release-ID | Commit-SHA | Veröffentlicht | Release Notes |
|---|---:|---|---|---|
| `v1.0.1` | `423955637` | `1e8d529255972d89c2f128fa1520f3cb41fef068` | 2026-10-26 07:27:51 UTC | Public HACS-ready release; read-only Panel, Integrationsmetadaten, HACS-Validierung, Hassfest und CI |
| `v1.0.2` | `423959146` | `d64e51672f0440c26c1567c7d294406510141947` | 2026-10-26 07:32:53 UTC | Korrektur des Custom-Panel-Elementnamens |
| `v1.0.3` | `423966322` | `cff03a11f77ece28ee2017f5904f44d182208215` | 2026-10-26 07:43:24 UTC | Korrektur des Panel-Elementnamens und Verlagerung von Desired-State-YAML-Datei-I/O vom Event Loop |

Alle drei Releases waren öffentlich, nicht als Draft markiert und nicht als Pre-Release markiert. Sie zielten auf `main`.

## Bereinigungsumfang

Freigegeben sind ausschließlich:

- Löschen der GitHub-Releases `v1.0.1`, `v1.0.2`, `v1.0.3`.
- Löschen der zugehörigen Git-Tags `v1.0.1`, `v1.0.2`, `v1.0.3`.

Nicht freigegeben und daher zu erhalten:

- Git-Commits und Git-Historie.
- `v0.9.2`.
- `v0.9.9`.
- Release-Dateien und produktive Home-Assistant-Daten.

## Ergebnis nach der Bereinigung

Nach der Löschung muss `/releases/latest` `v0.9.9` liefern. Die Commit-SHAs bleiben über die Git-Historie erreichbar, sind aber nicht mehr über die gelöschten 1.0.x-Tags referenziert.
