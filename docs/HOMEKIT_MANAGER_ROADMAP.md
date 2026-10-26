# HomeKit Manager Roadmap

## Phase 0.9.2 – Umbau und zentrale Modusverwaltung

In Arbeit auf `feature/homekit-manager-0.9.2`. Die neue Oberfläche und die konservative
Modusverwaltung sind lokal implementiert. Die drei Verwaltungsmodi werden erkannt und
pro Bridge als gewünschter Zustand gespeichert; Cross-Mode-Aktivierung bleibt bewusst
gesperrt, bis Bridge-Identität, Pairings, Accessory-IDs und Instance-IDs nachweislich
erhalten werden können. Die Versionierung verwendet ab diesem Stand die Reihe `0.9.x`.
Die ehemaligen `1.0.x`-GitHub-Releases und Tags wurden am 26.10.2026 aus der
öffentlichen Release-Oberfläche entfernt, weil ihre höheren Versionsnummern HACS ein
veraltetes Update anbieten ließen. Die zugehörigen Commits bleiben in der Git-Historie
erhalten. Zukünftige Releases müssen die Reihe `0.9.x` verwenden; `1.0.x` oder `2.0.x`
dürfen ohne separate Versionsentscheidung nicht erzeugt werden.

## Phase 0.9.3 – Geräte- und Bereichsverwaltung

Auf `feature/homekit-manager-0.9.3` lokal implementiert. Die Entity-Registry wird
read-only zu stabilen Geräte- und Bereichsansichten aggregiert. Neue authentifizierte
WebSocket-Endpunkte liefern diese Ansichten; das Frontend erhält eigene Geräte- und
Bereiche-Tabs. Sammelaktionen verändern weiterhin ausschließlich lokale Entwürfe.

Die lokale Abnahme ist bestanden. Veröffentlichung, HACS-Update und produktive
Installation bleiben bis zur vollständigen 0.9.2-Produktivabnahme zurückgestellt.

## Phase 0.9.4 – Kompatibilitätsprüfung und Diagnose

Auf `feature/homekit-manager-0.9.4` lokal implementiert. Die Diagnose erstellt aus
Inventar, Bridge-Filtern und YAML-Status reproduzierbare Befunde für nicht unterstützte
oder unklare Entitäten, nicht verfügbare Entitäten, veraltete Filterreferenzen,
Mehrfachzuordnungen und ungültige YAML. Die WebSocket-Schnittstelle ist read-only;
Korrekturen werden nicht automatisch ausgeführt.

Die lokale Abnahme ist bestanden. Veröffentlichung und produktive Installation bleiben
bis zur vollständigen Abnahme der produktiven 0.9.2-Kette zurückgestellt.

## Phase 0.9.5 – Erweiterte Gerätekonfiguration und Vorschau

Auf `feature/homekit-manager-0.9.5` lokal implementiert. Der neue read-only-Endpunkt
`homekit_manager/device_preview` erzeugt eine explizit als Simulation markierte
HomeKit-Service-Vorschau aus einer Inventar-Entität. Zulässige Vorschauoptionen sind
auf Anzeigename und Service-Typ begrenzt; Pairing- und Identitätsdaten werden weder
angenommen noch gespeichert. Die Detailansicht kann die Simulation anfordern.

Eine echte HomeKit-Übernahme bleibt durch den gesperrten Writer ausgeschlossen.
Veröffentlichung und produktive Installation bleiben bis zur vollständigen Abnahme der
produktiven 0.9.2-Kette zurückgestellt.

## Phase 0.9.6 – Multi-Bridge-Management

Auf `feature/homekit-manager-0.9.6` lokal erweitert. Mehrere Bridges werden vollständig
erkannt und in der Konfigurationsansicht angezeigt. Bei mehrdeutiger Auswahl wird keine
Bridge implizit verwendet; Moduswechsel und Änderungsplanung bleiben gesperrt, bis eine
eindeutige Bridge-Zuordnung vorliegt. Bridge-Neuanlage, Löschung und Verschiebung sind
nicht implementiert und werden nicht automatisch ausgeführt.

## Phase 0.9.7 – Regelbasierte Entitätsfreigabe

Auf `feature/homekit-manager-0.9.7` lokal implementiert. Der Endpunkt
`homekit_manager/rules_preview` wertet deterministische Regeln nach Priorität aus.
Manuelle Entscheidungen haben Vorrang; widersprüchliche Regeln werden als Konflikt
gemeldet. Die Auswertung ist ausschließlich Vorschlag und setzt niemals automatisch
HomeKit-Optionen oder YAML.

## Phase 0.9.8 – Konfigurationshistorie und Wiederherstellung

Auf `feature/homekit-manager-0.9.8` lokal implementiert. Während der laufenden Manager-
Instanz werden gespeicherte Desired-State-Entwürfe als begrenzte, redigierte
Historieneinträge geführt. Vergleiche zeigen
hinzugefügte, entfernte und geänderte Entitäten. Eine Wiederherstellung liefert nur
einen neuen Entwurf; `applied` bleibt immer `False`.

## Phase 0.9.9 – Performance, Stabilität und Produktreife

Auf `feature/homekit-manager-0.9.9` lokal implementiert. Der read-only-Endpunkt
`homekit_manager/performance` liefert deterministische Größen-, Domain- und
Verfügbarkeitsmetriken sowie eine begrenzte Empfehlung zur Seitengröße. Das Frontend
verwendet weiterhin Pagination und lädt das Inventar nicht bei normalen State-Updates
neu. Vollständige Lasttests mit 2.500 und 5.000 realen Entitäten sowie eine vollständige
mobile/Screenreader-Abnahme bleiben vor einer Produktreife-Freigabe offen.

## Release-Strategie nach 0.9.9

Der aktuelle öffentliche Release ist `v0.9.9`. Die geplante Fortsetzung lautet:

- `0.9.10`
- `0.9.11`
- `0.9.12`
- `0.9.13`

Jeder Release benötigt eine passende `manifest.json`-Version, einen `v0.9.x`-Tag,
erfolgreiche CI-, HACS- und Hassfest-Prüfungen sowie einen Release-Abnahmenachweis.
Bestehende Git-Commits werden im Rahmen der Release-Bereinigung weder umgeschrieben
noch gelöscht.

## Status

Stand: 26.10.2026. Die lokale 0.9.9-Entwicklung ist implementiert, dokumentiert und mit
42 Tests sowie einer frischen Browser-Liveprüfung validiert. Das Panel rendert, das
Inventar wird geladen und `mode_status` antwortet nach vollständigem Home-Assistant-Start.

Der produktive Home Assistant läuft weiterhin auf 0.9.2. Die lokalen Versionen 0.9.3 bis
0.9.9 sind noch nicht nach `main` integriert, nicht als Releases veröffentlicht und nicht
über HACS aktualisiert. Vor einer Veröffentlichung fehlen insbesondere die formale
Releaseabnahme, die Ausführung der CI auf dem neuen Stand sowie die Entscheidung über die
noch offenen Last-, Mobile- und Screenreader-Prüfungen.

## Reihenfolge

1. **Phase 5B.4 – Aktivierungsfehler beheben**  
   Die Umbenennung von `HomeKitManagerConfigFlow` nach `ConfigFlow` wurde übertragen und
   geladen. Sie war jedoch nicht als Root Cause nachgewiesen und hat das Laufzeitverhalten
   nicht behoben. Home Assistant registriert Config-Flow-Klassen über
   `ConfigFlow.__init_subclass__(domain=...)`; ein bestimmter Python-Klassenname ist dafür
   nicht erforderlich.
2. **Phase 5B.5 – Korrigierten Flow produktiv laden**  
   Abgeschlossen: produktive Datei übertragen, Core-Neustart freigegeben und durchgeführt.
   Der Domain-Pfad ist sichtbar, der Flow-Handler bleibt beim Start nicht verfügbar.
3. **Phase 5B.6 – Config-Flow-Tiefendiagnose**  
   Abgeschlossen mit **NO-GO für Aktivierung**: Manifest und Quellstruktur sind plausibel,
   aber der konkrete produktive Import-/Registrierungsfehler ist über den autorisierten
   Logzugang nicht sichtbar. Kein weiterer produktiver Eingriff wurde vorgenommen.
4. **Phase 5B.7 – Root-Cause-Analyse und echter Integrationstest**  
   Der vollständige native Logzugang liefert `Failed to load integration for translation:
   Integration 'homekit_manager' not found.`. Das belegt eine fehlende Integrationserkennung
   im Loader als unmittelbare Ursache des UI-/`UnknownHandler`-Fehlers; ein konkreter Grund,
   warum der produktive Custom-Component-Scan die Integration nicht liefert, ist ohne
   vollständige Core-Datei bzw. echte Core-Testumgebung noch offen. Die isolierte Umgebung
   wurde angelegt, Core 2026.10.4 ist wegen Host-Python 3.9.6 und fehlender verfügbarer
   Paketdistribution nicht installierbar. Keine produktiven Änderungen oder Neustarts.
5. **Phase 5B.8 – Custom-Component-Discovery und echte Integrationstests**  
   Der Core-Log bestätigt `Integration 'homekit_manager' not found`. Die unmittelbare
   Loader-Ursache ist damit reproduzierbar belegt, die konkrete Ursache im produktiven
   Mount-/Scanzustand aber weiterhin offen. Eine isolierte Testumgebung wurde angelegt;
   Core 2026.10.4 verlangt Python `>=3.14.2`, lokal ist nur Python 3.9.6 verfügbar und
   keine passende Ersatzinfrastruktur vorhanden. Die echten Integrationstests konnten
   deshalb nicht ausgeführt werden. Keine produktiven Änderungen oder Neustarts.
6. **Phase 5B.9 – Core-Sichtbarkeit und Testinfrastruktur**  
   Die produktiven Read-only-Oberflächen liefern weiterhin keinen Core-internen
   `custom_components.__path__`, keinen effektiven Core-Mount und keine Rechte-/Eigentümer-
   sicht aus dem Core-Container. Die isolierte Laufzeitdiagnose wurde in 5B.10 fortgeführt.
7. **Phase 5B.10 – Produktiven Core-Pfad verifizieren und echte Integrationstests**  
   Die autorisierte isolierte Python-3.14.9-Laufzeit wurde eingerichtet; Home Assistant Core
   2026.10.4, das passende Frontend und die Custom-Component-Testumgebung wurden installiert.
   Die echten Tests für Discovery/Registration, Config Flow, Entry-Setup und Writer-Sperre
   bestehen mit **3/3**, zusätzlich bestehen die vorhandenen Unit-Tests mit **18/18**.
   Der lokale Core-Log bestätigt `Loaded homekit_manager from custom_components.homekit_manager`.
   Der produktive Core-interne Pfad konnte trotz Freigabe A mangels tatsächlich vorhandener
   Terminal-/SSH-/Container-Schnittstelle nicht gelesen werden. Daher bleibt die Ursache der
   produktiven `Integration 'homekit_manager' not found`-Meldung offen. Status:
   **CONDITIONAL-GO für weitere Diagnose, NO-GO für produktive Korrektur**.
8. **Phase 5B.11 – Lokale 1.0-Implementierungsrunde**  
   Die lokale Architektur wurde an die HA-Referenzmuster angeglichen: Lifecycle-Unload,
   rekursive Geheimnis-Redaktion, Inventarstatistiken, serverseitiger Export und echte
   WebSocket-Registrierung und Singleton-Schutz wurden ergänzt. Die Testbilanz beträgt
   **20/20 Unit-Tests**, **8/8 Core-Integrationstests** und ein bestandener Node-Frontend-
   Verhaltenstest. Frontend-Browserabnahme und produktive Live-Abnahme
   stehen weiterhin aus; der HomeKit-Schreibpfad bleibt deaktiviert.
9. **Phase 5C – Live-Funktionstests**  
   **Blockiert**, solange der HomeKit Manager nicht erfolgreich aktiviert und als Config Entry angelegt wurde.
10. **Phase 5B.12 – Produktivsetzung vorbereiten**  
   Lokaler Release-Satz mit 23 Dateien und SHA-256-Prüfsummen dokumentiert. Deployment-,
   Sicherungs-, Rückbau-, Neustart- und Live-Abnahmeplan erstellt. Keine Produktivänderung.
   Status: **NO-GO für Übertragung**, **CONDITIONAL-GO nach Core-Pfadprüfung und Freigaben**.
11. **Phase 5B.13 – Release-Kandidat 1.0.0-rc1**  
   Lokaler Release-Satz auf 22 Dateien begrenzt, Manifestversion auf `1.0.0` gesetzt,
   maschinenlesbares SHA-256-Manifest erstellt und Release-/Rollback-/Acceptance-Dokumente
   ergänzt. Lokale Kern- und Integrationstests bestehen. Browser-Fixture wurde geladen; eine
   interaktive Wiederholung war in dieser Ausführung nicht zuverlässig automatisierbar und
   wird nicht als neuer bestandener Test gewertet. Status: **CONDITIONAL-GO**, produktive
   Voraussetzungen weiterhin offen.
12. **Phase 5B.14 – Produktive Bestandsaufnahme**  
   Der File Editor weist `/homeassistant/custom_components/homekit_manager/` nach. Die
   laufende Integrationsseite erkennt den Manager aktuell. Der produktive Stand ist jedoch
   älter als RC1 (`0.1.0`, ungültiges Dokumentationsfeld, `strings.json` nicht sichtbar);
   Eigentümer, Rechte und SHA-256 bleiben ungeklärt. Status: **NO-GO für Übertragung**.
13. **Phase 0.9.3–0.9.9 – Lokale Produktreife-Runde**
   Die lokalen Erweiterungen für Geräte/Bereiche, Diagnose, Vorschau, Multi-Bridge-Schutz,
   Regeln, Historie und Performance sind implementiert. Die lokale Prüfung umfasst
   Python-Kompilierung, JavaScript-Syntax, Frontend-Verhalten und 42 Tests. Die
   synthetischen 2.500-/5.000-Entitätengrößenprüfungen bestehen; echte Live-Lasttests
   gegen eine große Home-Assistant-Instanz bleiben offen.
   Eine frische Browserprüfung gegen die laufende Instanz zeigt ein sichtbares Panel,
   funktionierende Entitäten- und Konfigurationsansichten sowie keine Browser-Warnungen.
   Die produktive Installation bleibt auf 0.9.2; es erfolgte keine Aktualisierung.
14. **Phase 5D – Native UI/UX**
15. **Phase 6A – HomeKit-Statusermittlung**
16. **Phase 6B – Konfigurationsübergabe**
17. **Phase 6C – Kontrollierter HomeKit-Praxistest**
18. **Phase 7 – Stabilität**
19. **Phase 8 – Erweiterte Verwaltungsfunktionen**
20. **Phase 9 – Wartbarkeit**
21. **Phase 10 – Release 1.0**

## Sicherheitsstatus

### Phase 5B.15 – Frontend-Fix 1.0.1-rc1

Der schwarze Panelzustand wurde lokal durch sichtbare Initialisierungs- und Fehlerzustände,
robuste `hass`-/`panel`-/`narrow`-Setter und eine korrigierte Browser-Fixture adressiert.
Der Release-Kandidat `1.0.1-rc1` ist lokal vorbereitet. Die Produktivinstallation bleibt
unverändert und benötigt eine gesonderte Freigabe.

Der HomeKit-Schreibpfad bleibt deaktiviert. `apply_enabled` bleibt `False`; `HomeKitWriter.async_apply()` verweigert weiterhin jede Anwendung. Bestehende HomeKit-Config-Entries und Pairing-Daten werden nicht verändert.

### Phase 5B.16 – Panel-Element-Namensabgleich 1.0.2

Die Live-Diagnose nach dem HACS-Update zeigte, dass Home Assistant das Custom-Panel als
`homekit_manager-panel` erzeugte, während das Frontend `homekit-manager-panel` registrierte.
Der Panelname wird nun aus der Domain mit Bindestrich-Normalisierung abgeleitet. Dadurch
stimmen Loader und Custom-Element überein. Die Änderung ist lokal getestet und als
`1.0.2-rc1` vorgesehen; die bestehende HomeKit-Bridge bleibt unverändert.

### Phase 5B.17 – Nicht blockierende Desired-State-Lesezugriffe 1.0.3

Die Live-Abnahme nach dem Panel-Fix zeigte einen Home-Assistant-Warnhinweis, weil
`homekit_manager.yaml` synchron aus dem Event-Loop gelesen wurde. Die Initialisierung,
Aktualisierung, YAML-Statusabfrage und Entwurfsspeicherung verwenden nun den Home-
Assistant-Executor für Datei-I/O. Die fachliche Sicherheitsgrenze bleibt unverändert:
Es gibt keine automatische HomeKit-Anwendung, keine Reloads und keine Config-Entry-
Änderungen. Die Änderung ist lokal getestet und als `1.0.3-rc1` vorgesehen.

