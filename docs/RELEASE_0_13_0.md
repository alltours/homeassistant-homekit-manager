# HomeKit Manager 0.13.0

## UX-Finalisierung und Produktqualität

HomeKit Manager 0.13.0 verbessert die Bedienung der bestehenden HomeKit-Verwaltung, ohne die native HomeKit-Konfiguration automatisch zu verändern.

### Änderungen

- Direkte Auswahl der aktiven Bridge bei mehreren Bridges.
- Klare Kennzeichnung der Konfigurationsquelle und des Geltungsbereichs von Entwürfen und Aktionen.
- Zugänglicher Sprunglink zum Hauptinhalt.
- Bestätigungsdialoge mit Dialogrolle, beschreibendem Text, Fokusübernahme und verlässlicher Rückkehr zum auslösenden Bedienelement.
- Browser-Regressionstests für Chromium und WebKit einschließlich mobiler Viewports und großer Inventare.

### Sicherheit und Kompatibilität

- Native Apply, Write-Grants, Bridge-Bindung, Locking, Journaling, Recovery und Rollback bleiben unverändert.
- Die UX-Änderungen führen keine versteckten Schreiboperationen aus und verändern keine HomeKit-Bridge.
- UI↔YAML-Source-Migration wird weiterhin nicht angeboten.
- YAML-konfigurierte Bridges bleiben lesbar und werden als solche angezeigt.
- Die tatsächliche Apple-Home-Kompatibilität und produktive Anwendung wurden nicht durch diesen Release Candidate verändert.

Der Release Candidate ist ausschließlich für isolierte Prüfung bestimmt; ein Stable-Release und eine produktive Installation sind nicht Bestandteil dieses Entwicklungsstands.
