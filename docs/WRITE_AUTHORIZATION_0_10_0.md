# HomeKit Manager 0.10.0: Schreibfreigabe und Recovery

**Entwicklungsstand, NO-GO.** Dieses Verfahren beschreibt den implementierten
Grant-Vertrag für einen späteren, gesondert genehmigten Test. Es autorisiert
keine Installation und aktiviert nichts auf der vorhandenen HomeKit-Bridge.

## Server-seitige Autorisierung

Ohne lokale Datei `<HA-Konfigurationsverzeichnis>/.homekit_manager_write_grant.json`
ist der neue Operation-Apply-Pfad gesperrt. Ein Home-Assistant-Admin kann über
WebSocket nur Entwürfe und validierte Pläne erstellen. Der alte direkte
`apply_options_diff`-Pfad bleibt unabhängig vom Grant gesperrt.

Ein für **genau eine** Bridge und Quelle erstellter Grant enthält ausschließlich:

```json
{
  "version": 1,
  "grant_id": "HIER_32_ZUFÄLLIGE_KLEINE_HEXZEICHEN_EINSETZEN",
  "entry_id": "ENTRY_ID_DER_FREIGEGEBENEN_TESTBRIDGE",
  "source": "user",
  "core_version": "2026.10.4",
  "allowed_fields": ["filter"],
  "issued_at": "2026-10-28T12:00:00+00:00",
  "expires_at": "2026-10-28T13:00:00+00:00"
}
```

`grant_id` muss für jede Freigabe frisch zufällig und 128 Bit lang sein;
`source` ist exakt `user` oder `import`. Die Zeitstempel benötigen eine
Zeitzone; die Laufzeit darf 24 Stunden nicht überschreiten. Die Datei muss
regulär, nicht verlinkt, allein dem HA-Prozessbenutzer gehören und Modus `0600`
haben. Das Konfigurationsverzeichnis muss demselben Benutzer gehören und darf
nicht für Gruppe oder andere Benutzer schreibbar oder selbst ein Symlink sein.
Unbekannte oder doppelte JSON-Felder, falsche Core-Version, falscher
Entry, falsche Quelle und breitere Feldlisten werden abgewiesen. Der Grant wird
vor jedem Apply erneut gelesen; Löschen oder Ersetzen widerruft künftige
Applies, auch wenn die Ersatzdatei inhaltlich gleich ist. Der Native-Writer
prüft ihn nach dem Warten auf die Bridge-Sperre unmittelbar vor dem Core-Update;
der YAML-Writer prüft ihn beim Executor-Eintritt und erneut synchron direkt
vor dem atomaren Quellersatz. Ein Widerruf während Backup oder Validierung
blockiert damit die Quelländerung. Der Native-Writer vergleicht unter der
Bridge-Sperre zusätzlich die vollständige erwartete Config-Entry-Revision
einschließlich unbekannter Optionen direkt vor dem Core-Update.
Ein bereits vollzogener Core- oder Dateischreibvorgang kann durch Widerruf nicht
zurückgenommen werden.

Der Manager bietet absichtlich keinen UI- oder WebSocket-Endpunkt zum Erstellen
der Freigabedatei. Die separate Administrationshandlung und der spätere
Produktivtest erfordern ausdrückliche Benutzerfreigabe. Die Berechtigung gilt
nur für Filterlisten und nur für den durch Core 2026.10.4 geprüften Quelltyp.
Bei YAML wird zusätzlich jede gemischte Installation mit nativen HomeKit-Entries
gesperrt, da `homekit.reload` alle HomeKit-Entries betrifft.

## Apply-Ablauf und Grenzen

Der Admin wählt eine Bridge, erstellt einen Entwurf und erhält einen
serverseitig gehaltenen Plan mit Entry-ID, Quelle, Revision und Operation-ID.
Die UI verlangt eine Bestätigung mit exakt dieser Operation-ID. Backend und
Adapter prüfen Grant, Core-Version, Quelle, Revision, Schema und Scope erneut;
ein begonnenes Operation-ID kann nicht ein zweites Mal ausgeführt werden.
Native Options werden vor der Änderung im Journal gespeichert; bei YAML wird
ein dateibasierter Backup im HA-Konfigurationsverzeichnis erstellt. Nach der
Änderung werden Options beziehungsweise geladene YAML-Core-Werte geprüft.
Diese Prüfung beweist keinen Apple-Home-Zustand.

Bei Verbindungsverlust oder unklarem Ausgang: **nicht erneut anwenden**.
`operation_status` und `operation_reconcile` lesen Journal und aktuellen
Quellzustand, ohne eine Änderung zu wiederholen. `unknown_outcome` bedeutet,
dass eine manuelle Prüfung von Core-Entry, YAML-Quellbytes, Backup und HAP-Status
nötig ist. Ein YAML-Restore ist nur bei passender Revision, intaktem Backup und
unverändertem Inode zulässig. Auch ein technisch erfolgreicher Restore kann
Apple-Home-Pairings nicht garantieren. Die produktive Rücknahme ist derzeit
nicht als UI-Operation freigegeben.

Isolierte Tests belegen native und YAML-Filteränderungen mit Core-Reload sowie
lokaler HAP-Testcontroller-Kopplung und stabilen MAC/AID/IIDs. Ein zweiter
frischer Core-Harness-Prozess lud den Config Entry aus temporärem Core-Storage
und der Testcontroller verband sich erneut. Ein weiterer isolierter Test
führte zwei vollständige HA-Bootstrap-Prozesse mit automatisch geladenem
Test-Config-Entry und stabiler HAP-Identität aus. Diese Tests belegen weder
die Sichtbarkeit noch den Pairing-Erhalt in einem echten Apple Home. Bis zum
GO der Gesamtversion ist
dieser Grant-Mechanismus ein geprüfter Entwicklungsstand, keine
Produktivfreigabe.
