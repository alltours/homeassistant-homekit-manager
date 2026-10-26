# HomeKit Manager 0.9.12 – Funktionale Neugestaltung

## Entwicklungsstatus

0.9.12 ist ein Entwicklungsstand auf dem Branch
`feature/homekit-manager-0.9.12-functional-redesign`. Es ist noch kein
stabiler Release und wurde nicht produktiv installiert.

## Änderungen

- zentrale HomeKit-Startseite mit Konfigurationsmethode, Bridge-Karten und Änderungsübersicht;
- Bridge-Kontext bleibt an der tatsächlichen Config-Entry-ID gebunden;
- Geräteansicht ergänzt um `Gerätetypen` und `Zonen` neben Bereichen, Geräten und Entitäten;
- Entwürfe werden ausdrücklich von produktiv aktivierten Änderungen getrennt;
- konservative Erkennung von Config-Entry-, direkter YAML- und Include-Quellen;
- Misch- und Mehrdeutigkeiten werden als solche angezeigt und nicht automatisch migriert;
- bestehende HomeKit-Write-Sperre bleibt unverändert.

## Sicherheitsstatus

`apply_enabled = False` bleibt verbindlich. `HomeKitWriter.async_apply()`
verweigert weiterhin jede produktive Anwendung. Speichern erzeugt nur einen
validierten HomeKit-Manager-Entwurf; es führt keinen HomeKit-Reload und keine
Config-Entry-Änderung aus.

## Tests

- 49 Python-/Home-Assistant-Tests erfolgreich;
- JavaScript-Syntax- und Verhaltenstest erfolgreich;
- Chromium-Responsive-/Theme-/Interaktionsmatrix 9/9 erfolgreich;
- Performance-Fixture für 1.000, 2.500 und 5.000 Entitäten erfolgreich.

WebKit/Safari und produktive Migrationen sind für diesen Entwicklungsstand
nicht als bestanden behauptet.
