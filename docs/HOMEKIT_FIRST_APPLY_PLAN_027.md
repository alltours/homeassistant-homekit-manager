# HomeKit Manager 0.10.27 – Plan für den ersten kontrollierten Apply

Status: `CODE VERIFIED` als Ablauf- und Sicherheitsplan. `NOT VERIFIED` für die Durchführung: In diesem Auftrag wird kein produktiver oder testproduktionsnaher Apply ausgeführt.

## Voraussetzungen

Der erste Apply darf erst nach einem erfolgreichen Read-only-Erststart und einem neuen vollständigen Backup erfolgen. Native UI↔YAML-Migration, Config-Entry-Quellenwechsel, Pairing-Manipulation und direkte HAP-Persistenzänderungen bleiben ausgeschlossen.

Vor der Freigabe müssen Core-Version, Bridge-Config-Entry-ID, Quelle, MAC, Port, aktueller Filter, Manager-Revision und tatsächliche HAP-Veröffentlichung bekannt sein. Für den Apply ist ein Administrator und eine explizit eingerichtete, kurzlebige Bridge-bound Schreibberechtigung erforderlich. Diese Berechtigung wird nicht als Teil der Erstinstallation angelegt.

## Auswahl der Teständerung

1. Genau eine eindeutig identifizierte Bridge auswählen.
2. Eine unkritische, nicht sicherheitsrelevante Testentität auswählen.
3. Keine Türschlösser, Alarmgeräte, sicherheitsrelevanten Aktoren oder zentralen Automationen als Erstobjekt verwenden.
4. Keine parallele Filteränderung und keine gleichzeitige Änderung außerhalb des Managers zulassen.

## Ablauf

1. Aktuellen Filter und die aktuelle Revision unmittelbar vor dem Planen erneut lesen.
2. Tatsächliche HAP-Baseline mit einem unabhängigen Controller erfassen: MAC, Port, Pairing-Reconnect, Accessories, AIDs, IIDs, Services und Characteristics.
3. Vorschau erzeugen und nur die eine erwartete Entitätsänderung prüfen.
4. Prüfen, dass Bridge-ID, Quelle und Revision exakt zur Baseline passen.
5. Prüfen, dass die effektive Filtermenge keine nicht freigegebenen Entitäten einschließt und eine leere Positivliste nicht als „alles“ interpretiert wird.
6. Einmalig und ausdrücklich bestätigen.
7. Über den regulären autorisierten Apply-Pfad ausführen; keine private Core-API, keine direkte `.storage`-Änderung und kein Neu-Pairing.
8. Auf das Ergebnis und den kontrollierten Reload warten.
9. Mit demselben Controller reconnecten und die erwartete HAP-Änderung unabhängig prüfen.
10. MAC, Pairing-Fingerprint, Bridge-ID und Quelle vergleichen. Eine bewusst geänderte Entitätsmenge darf nur die erwarteten Accessory-Differenzen erzeugen.
11. Bei jedem unerwarteten Ergebnis den Apply als fehlgeschlagen betrachten, keinen zweiten Versuch starten und nach der Backup-/Rollback-Anleitung vorgehen.

## Abbruchbedingungen

Abbruch ohne Apply bei veralteter Revision, unbekannter Bridge-Zuordnung, unklarer YAML-Provenienz, fehlendem Administrator, ungültiger Bestätigung, fehlender HAP-Baseline, unerwarteter Filtererweiterung oder nicht erreichbarem ursprünglichem Pairing.

Der Server muss einen fehlenden Grant, eine unbekannte Operation oder eine veraltete Revision fail-closed ablehnen. Ein erfolgreicher Vorschau-Aufruf ist kein Apply-Nachweis.

## Rücknahme

Eine Rücknahme ist eine neue, separat bestätigte Filteränderung mit neuer Revision und neuer HAP-Verifikation. Sie ist nicht automatisch und nicht durch Quellenmigration zu ersetzen. Wenn der Zielzustand nicht eindeutig bestimmt werden kann, wird nicht zurückgeschrieben; stattdessen wird gestoppt und das Backup-Verfahren verwendet.
