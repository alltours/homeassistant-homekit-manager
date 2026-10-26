# HomeKit Manager 0.9.11 – Stabilisierung

## Umfang

Version 0.9.11 stabilisiert den read-only Verwaltungsworkflow bestehender HomeKit-Konfigurationen. Die Version ergänzt eine getrennte Bridge-Auswahl, persistente und redigierte Entwurfshistorie, zugängliche Regelvorschau sowie strengere Bridge- und Konfliktprüfung.

## Sicherheitsstatus

- `apply_enabled` bleibt `False`.
- `HomeKitWriter.async_apply()` verweigert weiterhin jede produktive Anwendung mit `HomeKitWriteDisabled`.
- Regeln, Vorschauen, Historien-Wiederherstellung und Exporte sind vorbereitende Funktionen; sie ändern keine HomeKit-Config-Entry, Pairing-Daten oder `.storage`-Dateien.
- Beim Wechsel zwischen mehreren Bridges wird ein ungespeicherter Entwurf blockiert, damit er nicht stillschweigend verworfen oder einer anderen Bridge zugeordnet wird.

## Änderungen

### Multi-Bridge-Kontext

Der Coordinator führt eine ausgewählte Config-Entry-ID. Der Kontext wird in Inventar, Übersicht, Vorschau, Modusstatus und Draft-Validierung verwendet. Unbekannte Bridge-IDs werden abgewiesen; eine automatische Neuzuordnung findet nicht statt.

### Historie

Die Historie wird über den Home-Assistant-Storage-Mechanismus unter `homekit_manager.history` gespeichert. Es gilt Schema-Version 1 und eine Obergrenze von 50 Einträgen. Gespeichert werden ausschließlich validierte Draft-Dokumente, Zeitstempel, Fingerprints und Bridge-IDs; Pairingmaterial, Tokens und Secrets werden verworfen. Wiederherstellung erzeugt ausschließlich einen neuen Draft.

### Oberfläche

Die vier Hauptbereiche bleiben `HomeKit`, `Geräte`, `Änderungen` und `Einstellungen`. In den Einstellungen sind Bridge-Auswahl, Diagnose, Regelvorschau und Historie erreichbar. Ein Bridge-Wechsel mit offenem Draft wird mit einer verständlichen Meldung verhindert.

### Kompatibilität

Die konservative Kompatibilitätsreferenz ist auf Home Assistant Core `2026.10.4` versioniert. Nicht eindeutig abbildbare Domains bleiben `unknown` statt als kompatibel behauptet zu werden.

## Tests

Die lokale Suite umfasst Unit-/HA-Integrationstests und JavaScript-Verhaltenstests. Der produktive Home-Assistant-Stand wird durch diese Entwicklung nicht verändert. Echte Browser-Matrix, produktive Live-Abnahme und HACS-/Hassfest-Prüfungen müssen vor einem stabilen Release separat nachgewiesen werden.

## Einschränkungen

Der HomeKit-Schreibpfad bleibt absichtlich deaktiviert. Eine produktive Änderung bestehender Bridges ist daher nicht Bestandteil von 0.9.11. Ohne erfolgreich ausgeführte Chromium/WebKit-Tests und vollständige CI-Freigabe darf kein Release veröffentlicht werden.
