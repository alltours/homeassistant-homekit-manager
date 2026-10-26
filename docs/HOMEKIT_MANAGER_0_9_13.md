# HomeKit Manager 0.9.13 – Configuration Apply

## Entwicklungsstatus

0.9.13 ist ein Entwicklungsstand auf dem Branch
`feature/homekit-manager-0.9.13-configuration-apply` und kein Release.
Die produktive Home-Assistant-Installation bleibt unverändert.

## Core-Befund

Home Assistant Core 2026.10.4 aktualisiert HomeKit-Config-Entries intern über
`ConfigEntries.async_update_entry()` und lässt den registrierten HomeKit-
Update-Listener anschließend die Entry neu laden. Die HomeKit-OptionsFlow ist
ein interaktiver UI-Flow und stellt keinen stabil dokumentierten externen
Submit-Vertrag für Custom Integrations dar.

## Implementierter Adapter

`HomeKitWriter` enthält einen versionsgebundenen Adapter für Core 2026.10.4.
Der Produktivpfad ist ausschließlich über den administrativ geschützten
WebSocket-Befehl `homekit_manager/apply_options_diff` erreichbar und wird
serverseitig auf `SOURCE_USER` begrenzt. Der Adapter:

- akzeptiert nur einen geprüften `OptionsDiff`;
- prüft die konkrete HomeKit-Config-Entry;
- prüft, dass sich die Entry seit der Vorschau nicht verändert hat;
- ändert ausschließlich erlaubte Optionsschlüssel;
- verwendet den Core-Update-Listener zur Aktivierung;
- wartet auf den Core-Lifecycle und meldet nur `active`, wenn der Entry danach
  tatsächlich `loaded` ist;
- serialisiert Anwendungen pro Bridge mit einer Bridge-ID-Sperre.

Der direkte Standardaufruf bleibt weiterhin gesperrt. Der explizite Backend-
Pfad verwendet keine Frontend-Freigabe, keine `.storage`-Manipulation und
keine Pairing- oder Bridge-Identitätsänderung.

## Nicht freigeschaltete Wege

- `SOURCE_USER`-Config-Entries werden über den geprüften Core-
  `async_update_entry`-/Update-Listener-Vertrag angewendet; der Vertrag ist
  auf Core `2026.10.4` versionsgebunden.
- Direkte Änderungen an `configuration.yaml` bleiben gesperrt, weil eine
  verlustfreie Bearbeitung von Kommentaren, Tags, Includes und unbekannten
  Schlüsseln nicht garantiert ist.
- `homekit_manager.yaml` bleibt ein validierter Manager-Entwurf und wird nicht
  automatisch als native HomeKit-Core-Konfiguration aktiviert.
- YAML-importierte HomeKit-Entries werden zusätzlich blockiert: Core 2026.10.4
  überspringt bei `SOURCE_IMPORT` den normalen Options-Update-Listener. Ein
  Options-Write wäre dort sonst irreführend als aktivierte Änderung meldbar.
- Der isolierte End-to-End-Nachweis ist deshalb auf `SOURCE_USER`-Entries
  begrenzt; YAML-Import bleibt ein ausdrücklich nicht unterstützter Schreibpfad.
- YAML-importierte Bridges bleiben gesperrt.

## Sicherheitsstatus

`apply_enabled = False` bleibt der Status des serialisierten Diffs und des
direkten Standard-Writers. Der produktive Backend-Pfad ist nur für die
definierte `SOURCE_USER`-Variante erreichbar. Es gibt keine automatische
Migration, keine Bridge-Neuanlage und keine Pairing-Manipulation.

## Freigabe

Der SOURCE_USER-Adapter ist durch Unit-, Integration- und echte isolierte
HomeKit-End-to-End-Tests abgesichert. Ein stabiler 0.9.13-Release bleibt
gesperrt, bis die vollständige Release-Pipeline einschließlich HACS, Hassfest,
GitHub Actions und der vorgesehenen Browsermatrix erfolgreich durchlaufen ist.

## E2E-Nachweis vom 2026-10-26

In einer vollständig getrennten HA-Core-2026.10.4-Instanz wurde eine echte
HAP-Bridge auf Port `22124` mit `aiohomekit` als Controller gekoppelt. Der
Controller speicherte den Pairingzustand lokal und las die veröffentlichten
Accessories über die verschlüsselte HAP-Verbindung.

| Prüfschritt | Ergebnis |
|---|---|
| Ausgangszustand | `input_boolean.test_a` und `input_boolean.test_b` veröffentlicht; `test_c` ausgeschlossen |
| Entry-Typ | `SOURCE_USER`, isolierte Entry-ID `01M5WRDRZ9GZZXTRE55GA69MQX` |
| Bridge-Identität | `B9:C9:24:A8:73:3A` vor/nach den Änderungen unverändert |
| Hinzufügen | `test_c` über den Manager-Adapter ergänzt; Controller-Reconnect erfolgreich |
| Entfernen | `test_b` über den Manager-Adapter entfernt; `test_a` und `test_c` blieben erreichbar |
| Neustart | Isolierter Core-Neustart; Pairing blieb gültig, kein erneutes Pairing erforderlich |
| YAML-Import | Bewusst blockiert: Core überspringt bei `SOURCE_IMPORT` den Update-Listener |

Der YAML-Import-Fall ist damit kein erfolgreicher Schreibpfad und bleibt
gesperrt. Der positive E2E-Nachweis gilt ausschließlich für `SOURCE_USER`.
