# HomeKit Manager 0.10.4

## Inhalt

Dieses stabile Release veröffentlicht den seit 0.10.3 nach `main` übernommenen
Dokumentationsstand. [PR #16](https://github.com/alltours/homeassistant-homekit-manager/pull/16)
ergänzt das [UX-Zielkonzept für Sammelaktionen](UX_BULK_ACTIONS_0_10_3.md)
und die [priorisierte Roadmap](HOMEKIT_MANAGER_ROADMAP.md). Die Versions- und
Paketmetadaten wurden auf 0.10.4 angehoben.

**Keine neue Funktion:** Bereits 0.10.3 zeigte auf Geräten und Bereichen zwei
separate Aktionen „Alles einschließen“ und „Alles ausschließen“, deren
Bestätigung nur den Manager-Entwurf ändert. Die im Zielkonzept gewünschten
Beschriftungen „Alle einschließen“ und „Alle ausschließen“, die konservative
Standardbehandlung ausgeblendeter und deaktivierter Entitäten sowie die
verfeinerten Dialogzahlen sind noch nicht implementiert. Die Dokumentation
stellt diese Punkte ausdrücklich als nächste Prüf- und Entwicklungsarbeit dar.
Es gibt in 0.10.4 keine Änderung am Frontend-Verhalten, am HomeKit-Filter-Writer,
an Schreibfreigaben, Core-Kompatibilität oder Pairing-Speicher.

## Kompatibilität und Sicherheit

Der freigegebene Funktionsumfang entspricht 0.10.3: Native `SOURCE_USER`-
Bridge-Filteränderungen sind auf isoliert geprüfte Core-Versionen 2026.10.4
und 2026.11.0b0 begrenzt; der unterstützte YAML-Schreibpfad bleibt auf
2026.10.4 begrenzt. Schreiben ist standardmäßig gesperrt und erfordert die
bestehenden serverseitigen Prüfungen und eine gesonderte Bestätigung. Ein
Filtertreffer beweist keine HAP- oder Apple-Home-Sichtbarkeit. Physischer
Apple-Home-Pairing-Erhalt wurde nicht getestet.

Die dokumentierte [Python-Abhängigkeitsentscheidung](SECURITY_PYTHON_DEPENDENCIES_0_10_0.md)
zu den von Core gepinnten Pillow-Advisories gilt unverändert. Das Release
ändert weder Core-Abhängigkeiten noch produktive Einstellungen.

## Installation und Rückkehr zu 0.10.3

Für Nutzer von 0.10.3 ist zur Nutzung der bestehenden Funktionen kein Update
erforderlich. Vor einer Installation von 0.10.4 ein wiederherstellbares
Home-Assistant-Backup prüfen. Das verifizierte ZIP enthält nur die Integration;
die Veröffentlichung installiert nichts und autorisiert keinen Writer.
Eine produktive Installation oder ein Core-Neustart benötigt eine separate
Freigabe. Danach zunächst Version, Bridge-Zuordnung und Entwürfe lesend prüfen.

Für eine Rückkehr die verifizierten Integrationsdateien von 0.10.3 mit
separater Freigabe wiederherstellen und Core nur mit gesonderter Freigabe
neu starten. Ein Code-Rollback macht zuvor angewendete Filteränderungen nicht
rückgängig; solche Vorgänge müssen anhand des Journals abgeglichen werden.
`.storage/homekit.*` darf dafür nicht manuell verändert werden.
