# Python-Abhängigkeiten: Release-Entscheidung für 0.10.0

Stand: 2026-10-28. Diese Bewertung gilt **nur** für HomeKit Manager 0.10.0 auf Home Assistant Core 2026.10.4 und dessen geprüfte Filter-Writer für Bridges. Eine Änderung an Core, an Pillow oder am Manager-Pfad erfordert eine neue Bewertung.

## Ursache und Befund

Core 2026.10.4 verlangt laut Paketmetadaten exakt `Pillow==12.3.0`. Die isolierte Python-3.14.9-Testlaufzeit enthält exakt diese Version. `pip-audit 2.10.1 --local --format json` meldete 39 Advisory-IDs in **einem** Paket, Pillow; alle übrigen geprüften Pakete hatten in diesem Lauf keinen Treffer. Die IDs sind einzeln in [`scripts/python_audit_policy.json`](../scripts/python_audit_policy.json) festgehalten. Alle 39 nennen 13.0.0 als Korrekturversion. Pillow 13.0.0 beseitigt laut [Hersteller-Release-Notes](https://github.com/python-pillow/Pillow/blob/main/docs/releasenotes/13.0.0.rst) mehrere Speicher- und Parserfehler. Die [kritische Hersteller-Advisory GHSA-v9pv-5gc8-w2m6](https://github.com/python-pillow/Pillow/security/advisories/GHSA-v9pv-5gc8-w2m6) setzt eine Pillow-Bildverarbeitung mit präparierten Eingabedaten voraus. Die 39 IDs sind Paketversionsbefunde; sie belegen nicht 39 über HomeKit Manager ausnutzbare Pfade.

Die [offizielle Liste der Core-Releases](https://github.com/home-assistant/core/releases) zeigte am Auditdatum 2026.10.4 als jüngstes stabiles Release. Dieses Release pinnt weiterhin Pillow 12.3.0. Eine eigenmächtige Aktualisierung auf Pillow 13.0.0 entgegen dem Core-Pin wäre keine getestete, unterstützte Lösung. Core 2026.11 oder ein Core-Entwicklungsstand wird durch dieses Release nicht freigegeben.

## Erreichbarkeit und Verantwortlichkeit

Der Manager deklariert als eigene Python-Anforderung ausschließlich `ruamel.yaml==0.18.17`. Sein Python-Code importiert weder `PIL` noch Pillow und verarbeitet keine Bild- oder PDF-Dateien, Frames, Fonts oder JPEG2000-Daten. Der geprüfte Core-HomeKit-Pfad (`homeassistant/components/homekit`), `pyhap`, `aiohomekit` und `homekit_audio_proxy` importieren Pillow nicht. Core HomeKit Camera nutzt FFmpeg/haffmpeg für den Stream. Manager-Writer ändern ausschließlich HomeKit-**Filterlisten**; Accessory-Mode-Entries sind nun an Planungs-, Capability- und Mutationsgrenzen read-only. Eine durch den Filter ausgewählte Kamera wird im Bridge-Modus nach Core-Regeln nicht als Kamera-Accessory veröffentlicht. Ein Manager-Apply nimmt keine Bilddatei entgegen und ruft keinen der in den Advisories beschriebenen Pillow-Decoder, -Encoder, -Parser oder -Filter auf.

**Bewertung: Für den freigegebenen Bridge-Filter-Apply ist keine Erreichbarkeit dieser Pillow-Pfade nachgewiesen.** Die vorhandene Pillow-Installation bleibt dennoch ein reales Risiko der Home-Assistant-Plattform: Andere Core-Komponenten, etwa Bildverarbeitung und Bild-Uploads, können Pillow verwenden. Eine Drittanbieter-Kamera kann eigene Bildpfade besitzen. Diese Bewertung erklärt Pillow **nicht** allgemein für ungefährlich und behebt die Plattformlücke nicht. Die produktive Core-/Pillow-Version ist mangels umfassendem lesendem Zugang nicht bestätigt.

## CI-Regel

Die CI führt weiterhin einen vollständigen `pip-audit --local` der isolierten Core-Laufzeit aus und veröffentlicht den unveränderten JSON-Bericht als Actions-Artefakt `python-runtime-audit`. [`scripts/audit_python_dependencies.py`](../scripts/audit_python_dependencies.py) akzeptiert nur die **39 konkret untersuchten IDs** für **Pillow 12.3.0**, wenn Core **2026.10.4** exakt diese Version pinnt und der Manager weder Pillow deklariert noch importiert. Jede neue Advisory, jeder Befund in einem anderen Paket, jede Versions-/Pin-Änderung und ein neuer Manager-Pillow-Import lassen den Check fehlschlagen. Ein Toolfehler oder unlesbarer Bericht schlägt ebenfalls fehl. Es gibt kein `--ignore-vuln` und keine generelle Abschaltung des Audits. Der vollständige Plattformbefund bleibt in jedem CI-Lauf sichtbar.

Die Entscheidung ist eine **eng begrenzte Risikobehandlung für ein vom Manager nicht ausgelöstes Core-Plattformrisiko**, keine Behauptung, dass die 39 Advisories behoben seien. Ein späterer passender Core-Stand mit gepatchtem Pillow sollte isoliert erneut getestet und die Regel dann entfernt werden. Sollte ein Manager- oder HomeKit-Codepfad zu einer betroffenen Pillow-Funktion nachgewiesen werden, ist dies sofort ein Release-Blocker.

## Release-Blocker-Matrix

| Problem | Schwere | Ursache/Pfad | Maßnahme | Nachweis | Status |
|---|---|---|---|---|---|
| Pillow 12.3.0, 39 IDs | Kritisch/hoch auf Plattform; keine Manager-Erreichbarkeit belegt | Core-Pin, Bildverarbeitung anderer Komponenten möglich | Exakte, sichtbare CI-Risikobehandlung; Core nicht überschreiben | Full-runtime-JSON, Core-Metadaten, Codepfadsuche, Hersteller-Advisories | Begrenzt behandelt; Plattformrisiko offen |
| Accessory-Mode konnte bei direkten Adapteraufrufen einen Filterplan erreichen | Hoch für zugesagten Bridge-Scope | Servergrenze verließ sich auf UI-Bridge-Auswahl | Bridge-Modus an Quelle, Plan und Mutation erzwingen | Negative Native-/YAML- und Capability-Tests | Behoben |
| Neuer Advisory oder Abhängigkeitsdrift | Potenziell hoch | Künftige Sicherheitsdaten oder Core-Änderung | CI scheitert geschlossen | Policy-Negativtests | Gate aktiv |
| Produktive Core-/Pillow-Version unbekannt | Mittel für spätere Installation | Lesender Live-Zugang unvollständig | Vor produktiver Installation Version und Updatepfad separat prüfen | Live-Audit noch offen | Nicht bestätigt |

## Entscheidung

**Für die 0.10.0-Releasebewertung ist Pillow 12.3.0 ein offen ausgewiesenes Core-Plattformrisiko, kein nachgewiesener erreichbarer Fehler des eingeschränkten Bridge-Filter-Writers.** Dieses Risiko allein sperrt die Veröffentlichung des Managers unter den hier festgelegten Grenzen nicht. Alle anderen Release-Gates, insbesondere Tests, CI, HAP-Persistenz und vorgeschriebene Reviews, bleiben verbindlich. Release, Installation und produktive Writer-Freigabe sind getrennte Entscheidungen.
