# HomeKit Manager 0.10.27 – Backup und Rollback

Status: `CODE VERIFIED` für die dokumentierte Sicherheitsgrenze. `NOT VERIFIED` für eine produktive Wiederherstellung, da keine produktive Instanz verändert wurde.

## Backup vor der Erstinstallation

Vor Installation oder Upgrade:

1. Ein vollständiges Home-Assistant-Backup über den regulären Home-Assistant-Weg erstellen.
2. Das Backup extern oder auf einem anderen sicheren Speicher ablegen.
3. Vorhandene Backup-Datei öffnen beziehungsweise den vom System angebotenen Integritäts-/Verfügbarkeitsnachweis prüfen.
4. Home-Assistant-Core-Version, Add-ons, Integrationen und Zeitpunkt dokumentieren.
5. Für jede HomeKit-Bridge Config-Entry-ID, Quelle, Name, MAC, Port und Filter dokumentieren.
6. Festhalten, dass Pairings und HAP-Persistenz ausschließlich über das reguläre Backup gesichert werden; keine manuellen Änderungen an `.storage` oder HAP-Dateien durchführen.
7. Den Manager-Stand und die ZIP-SHA-256 dokumentieren.

Das Backup ist nur dann ein verwendbarer Rückfallpunkt, wenn es außerhalb der laufenden Konfiguration verfügbar ist und sich einer konkreten Instanz beziehungsweise einem konkreten Zeitpunkt zuordnen lässt.

## Erwarteter Installationsumfang

Der Manager soll beim Read-only-Erststart ausschließlich seine eigene Integration und ihre Manager-Metadaten laden. Er darf keine HomeKit-Config-Entry-Quelle ändern, keine Pairing-Daten lesen oder ersetzen, keine HAP-Persistenz schreiben und keine Bridge neu erzeugen.

## Stufenweiser Rückfall

### Manager lädt nicht

1. Home Assistant-Logs sichern.
2. Home Assistant kontrolliert anhalten.
3. Nur die Manager-Dateien aus `custom_components/homekit_manager/` entfernen oder auf den vorherigen Manager-Stand zurücksetzen.
4. Home Assistant ohne Manager starten.
5. HomeKit-Config-Entries, Bridge-Erreichbarkeit und Pairings prüfen.

Dabei keine HomeKit-Config-Entry löschen und kein Pairing neu anlegen.

### Panel oder WebSocket funktioniert nicht

Der Manager bleibt installiert, aber es werden keine Schreibberechtigungen eingerichtet. Logs und Browser-/WebSocket-Fehler sichern; anschließend auf den letzten bekannten Manager-Stand zurückgehen. Die native HomeKit-Integration wird nicht neu eingerichtet.

### Bridge-Inventar ist unklar oder falsch

Installation stoppen und den Manager nicht autorisieren. Die native Config-Entry-ID und die tatsächliche Bridge werden unabhängig prüfen. Keine automatische Korrektur, kein Reload und kein Apply.

### HomeKit-Geräte fehlen oder Pairing ist nicht erreichbar

Dies ist kein zulässiger Erfolg des Managers. Zuerst unterscheiden, ob das Problem bereits vor der Installation bestand. Wenn die Ursache nicht eindeutig ausgeschlossen werden kann, vollständige Wiederherstellung des vorher geprüften Home-Assistant-Backups nach dem dokumentierten Home-Assistant-Verfahren erwägen. Kein Neu-Pairing als Reparaturmaßnahme.

### Unerwartete Filteränderung oder neue Bridge

Home Assistant anhalten, keinen weiteren Manager-Aufruf ausführen, Logs und Konfigurationsstand sichern und die Änderung als Sicherheitsvorfall behandeln. Nicht durch erneutes Apply, Löschen der Bridge oder Neu-Pairing kaschieren. Bei nicht sicher isolierbarer Ursache vollständige Wiederherstellung aus dem Backup durchführen.

## Grenzen

Eine bloße Deinstallation des Managers stellt keine bereits außerhalb des Managers verursachte HomeKit-Änderung zurück. Umgekehrt soll die Deinstallation im vorgesehenen Read-only-Erststart keine native HomeKit-Konfiguration verändern. Diese Eigenschaft wird durch die Codepfade und Stable-Tests belegt, nicht durch einen produktiven Restore.

Ein vollständiger Home-Assistant-Restore ist ein größerer Eingriff als die Entfernung der Custom-Integration und darf nur nach gesichertem Backup und nach den offiziellen Home-Assistant-Anweisungen erfolgen.
