# HomeKit Manager – Produktive Abnahmeliste 1.0

## Integration

- [ ] Core erkennt `homekit_manager` ohne `Integration not found`.
- [ ] Config Flow startet.
- [ ] Manager-Config-Entry wird nach Freigabe erstellt.
- [ ] Setup erfolgreich.
- [ ] Unload erfolgreich.

## Backend

- [ ] Entity Registry wird gelesen.
- [ ] Device Registry wird gelesen.
- [ ] Area Registry wird gelesen.
- [ ] Bestehende HomeKit-Bridge wird über Entry-ID `example-homekit-entry-id` erkannt.
- [ ] Filter und Statusmodell stimmen mit der Core-Konfiguration überein.
- [ ] Authentifizierte WebSocket-Aufrufe funktionieren.
- [ ] Nicht-Administratoren werden bei Verwaltungsbefehlen abgewiesen.

## Frontend

- [ ] Seitenleisteneintrag erscheint.
- [ ] Panel lädt ohne JavaScript-Fehler.
- [ ] Suche, Filter und Sortierung funktionieren.
- [ ] Mehrfachauswahl funktioniert.
- [ ] Entwurf speichern/laden/verwerfen funktioniert.
- [ ] Vorschau und Export funktionieren.
- [ ] Mobile Darstellung funktioniert.

## HomeKit-Sicherheit

- [ ] Bridge bleibt aktiv.
- [ ] Pairing bleibt erhalten.
- [ ] Bestehender HomeKit-Config-Entry bleibt unverändert.
- [ ] Kein HomeKit-Reload.
- [ ] Keine `.storage`-Änderung.
- [ ] Keine Accessory-ID-/IID-Manipulation.
- [ ] `apply_enabled = False` bleibt aktiv.
- [ ] `HomeKitWriter.async_apply()` verweigert Anwendung.

Nur wenn alle Punkte nachweislich erfüllt sind, ist die produktive Abnahme GO. Lokale Tests
ersetzen keine Live-Abnahme.

