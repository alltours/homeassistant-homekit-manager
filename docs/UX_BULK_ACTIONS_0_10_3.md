# UX-Zielkonzept: Sammelaktionen für Geräte und Bereiche

Stand: 29. Oktober 2026. Dieses Dokument beschreibt eine verbindliche UX-Anforderung
und die anschließende Prüfarbeit. Es aktiviert keinen Writer und ändert keine
HomeKit-Konfiguration.

## Ausgangspunkt und Ziel

Der veröffentlichte Stand 0.10.3 zeigt auf jeder Gerätezeile bereits zwei direkt
erreichbare Schaltflächen, derzeit „Alles einschließen“ und „Alles ausschließen“.
Auch Bereichszeilen besitzen diese beiden Aktionen. Der aggregierte Status wird
separat angezeigt; die Bestätigung erstellt ausschließlich einen Manager-Entwurf.
Ein einzelner Ein/Aus/Gemischt-Umschalter ist für Geräte und Bereiche ausgeschlossen.

Die endgültigen sichtbaren Beschriftungen lauten **„Alle einschließen“** und
**„Alle ausschließen“**. Beide bleiben bei geschlossenem Gerät sichtbar. Der
Status „Eingeschlossen“, „Ausgeschlossen“ oder „Gemischt“ ist eine Anzeige und
keine Schaltfläche. Eine wirklich leere Gruppe heißt „Keine Entitäten“; eine
Gruppe mit ausschließlich unbekanntem Filterstatus heißt „Keine auswertbaren
Entitäten“. Aktueller und geplanter
Filterstatus bleiben unterscheidbar. Filterauswahl bedeutet weder HAP-Publikation
noch Sichtbarkeit in Apple Home.

## Umfang und Standardregel

Eine Geräteaktion verwendet alle eindeutig zugeordneten Entitäten des Geräts
aus dem vollständigen Inventarsnapshot. Suche, Ansichtsfilter und Pagination
verändern diesen Umfang nicht. Bereichsaktionen verwenden entsprechend alle
Entitäten aller zugeordneten Geräte sowie die Entitäten ohne Gerät im Bereich.
Entitäten außerhalb des gewählten Knotens dürfen keine Entwurfsänderung erhalten.

Die folgende konservative Standardregel ist als Ziel festgelegt und vor einer
Codeänderung gegen die unterstützten Core-Versionen zu testen:

| Eigenschaft | „Alle einschließen“ | „Alle ausschließen“ | Anzeige im Dialog |
| --- | --- | --- | --- |
| Technisch unterstützt oder bedingt unterstützt, Registry aktiv, nicht ausgeblendet | Vormerken, falls der geplante Status abweicht | Vormerken, falls der geplante Status abweicht | Bearbeitbar; „bedingt“ gesondert markieren |
| Technisch nicht unterstützt oder Kompatibilität unbekannt | Standardmäßig ausnehmen | Standardmäßig ausnehmen; gezielte Bereinigung nur als Einzelentscheidung | Grund und Anzahl getrennt ausweisen |
| `hidden_by` oder `entity_category` gesetzt | Standardmäßig ausnehmen; explizite Core-Aufnahme nicht als Massen-Nebenwirkung erzeugen | Standardmäßig ausnehmen; vorhandene explizite Auswahl nicht beiläufig entfernen | `hidden_by` und Kategorie getrennt ausweisen |
| Entity oder Gerät mit `disabled_by` | Standardmäßig ausnehmen | Standardmäßig ausnehmen | Deaktivierungsgrund und Anzahl ausweisen |
| Aktueller Filterstatus unbekannt | Ausnehmen | Ausnehmen | Grund für unbekannte Selektion ausweisen |

Ein fehlender State ist **kein** Nachweis für „verwaist“ und kein Synonym für
`disabled_by`. Er wird separat angezeigt. Ob eine solche Entität für eine
Sammelaktion bearbeitbar ist, hängt von nachgewiesener Registry- und Core-
Filtersemantik ab; sie darf nicht allein wegen fehlenden States pauschal als
„nicht kompatibel“ klassifiziert werden. Umgekehrt darf ein Entwurf keine
aktuelle HAP-Publikation behaupten.

Core 2026.10.4 iteriert beim Erstellen der HomeKit-Accessories über vorhandene
States. Danach überspringt er Entitäten mit `hidden_by` oder Entity-Kategorie,
wenn der Filter sie nicht ausdrücklich enthält. Dies ist ein anderer Mechanismus
als die Konfigurationsauswahl; `disabled_by` wird im Manager als eigener
Registry-/Verfügbarkeitsstatus geführt. Referenzen: [HomeKit-
Runtime](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/homekit/__init__.py)
und [HomeKit-Options-Flow](https://github.com/home-assistant/core/blob/2026.10.4/homeassistant/components/homekit/config_flow.py).

## Bestätigung und Entwurf

Vor **jeder** Geräte- oder Bereichsaktion erscheint ein Dialog mit Knotenname,
Aktion, vollständiger Anzahl der Geräte und Entitäten, Anzahl der neu im Entwurf
umzustellenden Entitäten, bereits passend vorgemerkten Entitäten sowie einer
disjunkten Aufschlüsselung der ausgenommenen Entitäten nach Grund. Bei
vorhandenen Einzelentwürfen muss der Dialog zusätzlich zwischen aufgehobenen
Entwurfsentscheidungen und neuen Änderungen gegenüber dem aktiven Filter
unterscheiden. Eine Nulländerung erzeugt keine neue Operation.

Der Dialog sagt ausdrücklich, dass die Bestätigung **nur den Entwurf** ändert.
Aktiver Filter, HAP-Identität und Pairings bleiben bis zum gesonderten,
serverseitig geprüften Apply unverändert. Der vorhandene Preview-/Apply-Pfad,
Bridge- und Quellenbindung, Adminprüfung, Revision, Backup und Reconcile bleiben
maßgeblich; die Hierarchie erhält keinen eigenen Schreibpfad.

## Darstellung und Bedienung

Auf Desktop stehen Status-Badge, die beiden kurzen Textschaltflächen und
„Entitäten“ in der kompakten Gerätezeile. Die Aktionen bekommen gleiches
visuelles Gewicht; der Status bleibt eine passive Anzeige. In schmalen
Smartphone-Ansichten stehen die zwei Aktionen als gleich breite, gegebenenfalls
zweizeilige Schaltflächen unter dem Gerätenamen. Die Beschriftung bleibt
ausgeschrieben; jedes Ziel ist mindestens 44 CSS-Pixel hoch. Der Aufklappknopf
ist davon getrennt. Tastaturfokus, Screenreader-Namen und Bestätigungsdialog
bleiben nachvollziehbar. Passive Datenaktualisierungen schließen weder
Dropdowns noch aufgeklappte Bereiche/Geräte unbeabsichtigt.

Die gleichen zwei Aktionen sind auf Bereichsebene sinnvoll, weil sie das
Interaktionsmuster konsistent halten. Die größere Reichweite muss im Dialog
besonders deutlich werden: vollständiger Bereichsname, Geräte-/Entity-Zahlen
und Anzahl der Ausnahmen. Sie bleiben auch bei zugeklapptem Bereich sichtbar,
werden visuell jedoch nicht prominenter als Geräteaktionen dargestellt.

## Priorisierte Roadmap und Abnahme

| Priorität | Arbeitspaket | Abnahmenachweis |
| --- | --- | --- |
| P0 | Bestehende 0.10.3-Aktionen und Dialogzahlen gegen diese Regel prüfen; konkrete Ausnahmen für nicht unterstützte, ausgeblendete, kategorisierte und deaktivierte Entitäten festlegen und serverseitig absichern | Tabellengetriebene Core-Vertragstests für 2026.10.4 und die freigegebene Beta; keine Entität außerhalb des Knotens oder aus einer Ausnahmegruppe wird unbemerkt vorgemerkt |
| P0 | Dialogzahlen aus vollständigem Snapshot und vorhandenen Einzelentwürfen berechnen; „Entwurfsänderung“ und „aktive Filteränderung“ getrennt benennen | Tests für Suche, Filter, mehrere Seiten, gemischte Zustände, No-op und widerrufene Einzelentwürfe bei 5.000 Entitäten |
| P1 | Exakte Beschriftung „Alle …“, neutralen Status für unbekannte Gruppen, kompakte Desktop- und Smartphone-Anordnung sowie Bereichsaktion mit deutlicher Reichweite prüfen | Chromium und WebKit bei Desktop und 320-/390-Pixel-Ansicht; Touch, Tastatur, Fokus und Screenreader-Namen; keine abgeschnittenen Bedienelemente oder irreführenden Statuslabels |
| P1 | Zustand bei passivem Refresh prüfen | Offene Menüs und Baumknoten bleiben offen; Entwurf und Auswahl bleiben konsistent |
| P2 | Verständlichkeit der Ausnahmegründe mit Nutzern prüfen und Text bei Bedarf verkürzen | Keine Verwechslung zwischen Filterauswahl, Entwurf, HAP-Publikation und Apply |

**Status:** Zielkonzept dokumentiert; diese Nacharbeiten sind noch nicht
implementiert oder als vollständig bestanden bewertet. Insbesondere nimmt die
0.10.3-Sammelaktion derzeit `hidden_by` und `disabled_by` nicht standardmäßig
aus. Der aktuelle neutrale Status „Keine Entitäten“ unterscheidet eine leere
Gruppe noch nicht von einer Gruppe mit unbekannter Selektion. Keine produktive
Installation oder Filteränderung ist Teil dieses Dokuments.
