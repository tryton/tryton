
:tocdepth: 2

Client Bedienung
################
Dieses Dokument stellt die Konzepte der grafischen Benutzeroberfläche
(*Tryton Client*) für die Tryton Anwendungs-Plattform dar.


Name
****
tryton - grafische Benutzeroberfläche der Tryton Anwendungs-Plattform


Kurzfassung
***********

::

  tryton [Optionen]

Nach dem Start öffnet sich der `Anmeldedialog`__ und optional
ein `Tippdialog`__.

__ Menu-File-Connect_
__ Menu-Help-Tips_


Optionen
********

--version                            Zeigt die Programm-Version und beendet sich

-h, --help                           Zeigt die Hilfe an und beendet sich

-c FILE, --config=FILE               Angabe einer alternativen `Konfigurations-Datei`__

-v, --verbose                        Einschalten einer einfachen Fehleranzeige

-d LOG_LOGGER, --log=LOG_LOGGER      Angabe des zu protokollierenden Kanals (z. B.: rpc.request, rpc.result, ...)

-l LOG_LEVEL, --log-level=LOG_LEVEL  Angebe der Protokollebene: INFO,
                                     DEBUG, WARNING, ERROR, CRITICAL

-u LOGIN, --user=LOGIN               Angabe des Benutzers zur Anmeldung

-p PORT, --port=PORT                 Angabe des Server-Ports

-s SERVER, --server=SERVER           Angabe des Server-Hostnamens
 
__ Konfigurations-Dateien_


Übersicht
*********
Die folgende schematische Darstellung des Tryton Clients zeigt die Namen
aller wichtigen Elemente der Benutzeroberfläche.

Abbildung: Tryton Client Anwendung::

  Client Fenster    _______________________________________________________
                   |                      Tryton                      _ o x|
                   |-------------------------------------------------------|
  Menüleiste       | Datei Benutzer Formular Einstellungen ... Hilfe       |
                   |_______________________________________________________|
                   |                                                       |
  Werkzeugleiste   | Neu Speichern | Löschen | Suchen Vor Zurück v         |
                   |-------------------------------------------------------|
                   |          ______                                       |
  Tableiste        | [Menü]  |[Tab1]| [Tab2] ...                           |
                   |---------|      | -------------------------------------|
                   | .-------        ------------------------------------. |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
  Sicht            | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |                                                   | |
                   | |___________________________________________________| |
                   |_______________________________________________________|
  Statusleiste     | Benutzername Firma   Wartende Anfragen...   login@... |
                   |_______________________________________________________|


Menüleiste
^^^^^^^^^^^
Die Menüleiste ist das Hauptkontrollfeld. Es stellt den Großteil an Funktionalität
der Client Anwendung zur Verfügung. Die Menü-Leiste ist in Kategorien unterteilt
und kann mit Maus und Tastatur bedient werden. Die `Menüleisten-Elemente`_ werden
später erklärt.


Maus- und Tastaturbedienung
+++++++++++++++++++++++++++
Die meisten Funktionen des Tryton Client können mit Maus oder Tastatur benutzt werden.
Für alle Menüpunkte sind `Schnelltasten`__ verfügbar. Zusätzlich sind alle Schnelltasten
manuell konfigurierbar. Um das Kürzel eines Menüpunkts zu ändern muss man den Mauszeiger
über dem Menüpunkt positionieren und das neue benutzerdefinierte Schnelltaste drücken.
Um diese Möglichkeit nutzen zu können muss man unter Einstellungen > Menüleiste > Kurzbefehle ändern aktivieren.
Nach dem Ändern der Tastaturkürzel sollte man nicht vergessen diese Funktion wieder auszuschalten
um eine versehentliche Änderung von Schnelltasten zu vermeiden während man in den Menüpunkten
navigiert.

Um das Kürzel eines Menüpunkts zu enfernen muss man den Mauszeiger über dem
Menüpunkt positionieren und die Enfernen-Taste drücken.

.. Note:: Üblicherweise werden Schnelltasten mit den Modifikationstasten kombiniert.

__ Menu-Help-Keyboard_Shortcuts_

Zusätzlich sind die Menüpunkte erreichbar mit den *Alt*- und *Options*-Tasten.
Der Benutzer muss die *Alt*- und *Options*-Taste kombiniert mit dem unterstrichenen
Buchstaben des Menüpunkts drücken. Um in weitere Untermenüs zu navigieren, die *Alt*-
oder *Options*-Taste loslassen und den unterstrichenen Buchstaben des gewünschten
Untermenüs drücken. Falls mehrere Menüpunkte mit dem gleichen Schnelltasten existieren,
diese Schnelltaste nochmals benutzen um zum nächsten Menüpunkt zu springen.

Die zweite Maustaste  (normalerweise die rechte Maustaste) stellt ein zusätzliches
Kontextmenü für weitere Sichten und Felder zur Verfügung. In diesem Kontextmenü
findet der Benutzer :term:`Aktionen` um Inhalte zu kopieren oder einzufügen, Vorgabewerte
zu setzen oder um Auswahlen für verschiedene Felder zu erhalten.


Werkzeugleiste
^^^^^^^^^^^^^^
Die Werkzeugleiste enthält Symbole für oft benutzte Menüfunktionen.
Zusätzlich zur Menüleiste beinhaltet die Werkzeugleiste den Knopf
Dateianhang.

Anhänge
+++++++
Das Dateianhang-Element stellt das Dokumenten Management System von Tryton
bereit. Es ist in der Lage Dateien an jedes beliebige :term:`Modell`
anzuhängen. Der Knopf zeigt wie viele Anhänge mit der aktuellen Sicht
verknüpft sind. Beim Mausklick öffnet sich der :term:`Dialog` Anhang.
Der Standard-Dialog zeigt eine Liste der angehängten Dateien und Verknüpfungen.

Der einzelne Anhang hat folgende Optionen:

* Name Anhang: Der Name des Anhangs.
* Daten: Die angehängte Datei. Die Dateigröße wird im Textfeld dargestellt.
* Verknüpfung: Verknüpfung zu einer externen Seite als URL.
* Vorschau Tab: Zeigt ein Vorschaubild des ausgewählten Anhangs.
* Beschreibung Tab: Ermöglicht Anzeige und Bearbeitung einer Beschreibung
  des ausgewählten Anhangs.
* Aktionen:

  - OK: Schliesst den Dialog und speichert den/die Anhänge.


Hauptfenster mit Tabs
^^^^^^^^^^^^^^^^^^^^^
Dieser Teil des Tryton Client beinhaltet alle Inhalte und Funktionen
die durch die :term:`Tryton Server`-:term:`Module` bereitgestellt werden.
Alles innerhalb des *Hauptfensters* hängt von den individuell
installierten Modulen ab.

Das Hauptfenster stellt `Tabs`__ bereit um verschiedene
Sichten nebeneinander anzuordnen. Neue :term:`Tabs` werden durch spezielle
:term:`Aktionen` wie zum Beispiel das Auswählen eines Menüpunkts oder durch
klicken von Aktionsknöpfen geöffnet. Alle Tabs haben einen Titel, der den Namen der
verwendeten Sicht zeigt.

:term:`Tabs` können mit Drag and Drop verschoben werden.

__ TDI_

.. _TDI: http://de.wikipedia.org/wiki/Registerkarte

.. Note:: Innerhalb einer :term:`Sicht` kann es auch Tabs geben.

Hauptmenü
+++++++++
Das erste Tab beinhaltet das *Hauptmenü* (... nicht zu
verwechseln mit der Menüleiste!). Das *Hauptmenü* beinhaltet keine
festen Menüpunkte. Diese werden dynamisch von den installierten
:term:`Modulen <Module>` und abhängig von den Zugriffsrechten des aktuellen
Benutzers bereitgestellt. Sobald ein Menüpunkt gedrückt wird öffnet sich
durch die hinterlegte Aktion eine neuer Tab. Wie das Schaubild
zeigt ist das *Hauptmenü* in drei Bereiche unterteilt.

Der obere linke Bereich beinhaltet die obersten bzw. Haupt-Menüpunkte des
*Hauptmenüs*. Standard Haupt-Menüpunkte sind 'Systemverwaltung' und 'Tryton'.

.. note:: Das *Systemverwaltung*-Menü wird in der Moduldokumentation
   des 'IR' Moduls ('information repository' - Informations-Ablage)
   dokumentiert. 

Der Haupt-Menüpunkt 'Tryton' ruft die Webseite des Tryton Projekts auf.

Der rechte Bereich zeigt eine :term:`Baumansicht` der Haupt- und Unter-Punkte
des gewählten Moduls. Mit den Pfeiltasten kann man sich innerhalb diese Menüs
bewegen. Durch drücken der "Enter"-Taste oder mit einem Doppelklick öffnet sich
das dazugehörige Menü. Mit den Pfeiltasten Links und Rechts kann man die
verschiedenen Ebenen der Baumansicht aus- und einklappen.

Schaubild: Hauptmenü Tab::

       ________________________________________________________
      |                      Tryton                       _ o x|
      |--------------------------------------------------------|
      | Datei Benutzer Formular Einstellungen ... Hilfe        |
      |________________________________________________________|
      |                                                        |
      | Neu Speichern | Löschen | Suchen Vor Zurück v          |
      |________________________________________________________|
      |   ______                                               |
      |  |[Menü]|   [Tab1]   [Tab2] ...                        |
      |--|      | ---------------------------------------------|
      |  |       -------------.------------------------------. |
      |  | Hauptmenü-Punkt 1  | Menü                |        | |
      |  | Hauptmenü-Punkt 2  |---------------------+--------| |
      |  | ...                |   Item 1            |        | |
      |  | Administration     |   Item 2            |        | |
      |  | Tryton             | > Überschrift       |        | |
      |  |____________________|     Unterpunkt 1    |        | |
      |  | Favoriten    [+][-]|     Unterpunkt 2    |        | |
      |  |--------------------|     > Unterüberschrift       | |
      |  | Unterpunkt 2       |         weitere     |        | |
      |  |                    |          Unterpunkte|        | |
      |  |                    |          ...        |        | |
      |  |____________________|_____________________|________| |
      |________________________________________________________|
      | Benutzername Firma   Wartende Anfragen...    login@... |
      |________________________________________________________|


Der linke untere Bereich zeigt ein *Favoriten* Menü, welches durch den Benutzer
selbst angepasst werden kann. Durch einen Doppelklick auf den entsprechenden Eintrag
wird die dazu passende Sicht aufgerufen. Die aktuelle Sicht wird als Favorit durch
Klick des Plus-Knopfes [+] dem Menü hinzugefügt. Der Minus-Knopf [-] löscht den
ausgewählten Favoriten aus dieser Liste.

Startseite
++++++++++
Eine weiterer Tab öffnet sich während des Startens des Tryton Client:
Die Startseite. Für gewöhnlich ist es ein Punkt des `Hauptmenü`__, der
geöffnet wird sobald der Benutzer die *Startseite* ausführt. Diese Standardaktion
wird in den `Einstellungen`__ definiert.

__ Menu-Form-Home_

__ Menu-User-Preferences_


Statusleiste
+++++++++++++
Die *Statusleiste* stellt generelle Informationen über den Status
des Tryton Client bereit. Sie ist in drei Abschnitte unterteilt.

* Auf der linken Seite befindet sich der Name und der Firmenname des aktuellen Benutzers.
* In der Mitte der Statusleiste wird die Anzahl der offene Anfragen
  des aktuellen Benutzers bereitgestellt.
* Auf der rechten Seite werden Details zur Server Verbindung gezeigt mit Informationen zum
  Benutzer und zur Datenbank sobald man verbunden ist. Hier wird auch angezeigt falls
  es keine Verbindung zu einem Tryton Server besteht. Dieser Bereich wird nach folgendem
  Muster erzeugt::

    <Benutzer-Name>@<Tryton-Server-Adresse>:<Port>/<Datenbank-Name>

  Sobald der Client mit einer SSL-verschlüsselten Verbindung zum Server verbunden
  hat erscheint ein zusätzliches Vorhängeschloss-Symbol mit weiteren Zertifikats-
  Details sobald sich der Mauszeiger auf diesem Symbol befindet.

Die Statusleiste kann aus- und eingeschalten werden über
die Menüleiste Einstellungen > Formular > Statusleiste


Menüleisten-Elemente
********************
Das folgende Kapitel beschreibt die Funktionen jedes Menüleisten-Eintrags
im Detail. Als Faustregel gilt: Jeder Menüpunkt, welcher mit drei Punkten
endet [...] öffnet direkt den :term:`Dialog` der zugewiesenen Menüaktion.
Die meisten Dialoge stellen einen *Abbrechen* Knopf bereit um den kompletten
Vorgang abzubrechen.


Datei
^^^^^
Das *Datei* Menü stellt Funktionen des Tryton Servers wie
Anmelden, Datenbankpflege und zum schließen der Client Anwendung.

.. _Menu-File-Connect:

Verbinden...
  Bei Auswahl dieses Menüeintrags verbindet sich der Client zu einem
  verfügbaren Tryton Server. Ein :term:`Dialog` öffnet sich zur Eingabe
  des Benutzernamens und Passwortes.

  * `Serververbindung`__
  * Datenbank: Datenbank auf Serverseite, zu der die Verbindung aufgebaut werden soll
  * Benutzername: Tryton Benutzername um sich anzumelden
  * Passwort: Tryton Passwort um sich anzumelden
  * Aktionen:

    - Verbinden: Verbindet zum Server mit Hilfe der eingegebenen Daten
    - Abbrechen: Bricht den Dialog ab

.. note:: Abhängig von den Servereinstellungen wird der Benutzer nach einer
   gewissen Zeitspanne von der aktuellen Verbindung abgemeldet und muss sich
   wieder anmelden. Die voreingestellte Zeitspanne des automatischen Abmeldens
   beträgt 6 Minuten.

__ File-Server-Connection_


.. _Menu-File-Disconnect:

Verbindung trennen...
  Trennt den Client von einer aktiven Server Verbindung. Falls nicht gespeicherte
  Änderungen in einem offenen Tab existieren, fordert der Tryton Client zum
  Speichern der Änderungen auf.

Datenbank
+++++++++
Dieses Untermenü stellt Werkzeuge zur Wartung der Tryton Datenbank bereit.
Für alle Datenbankoperationen benötigt der Benutzer das Tryton Server-Passwort.

.. warning:: Falls Sicherheitsbedenken bestehen sollten Sie diese serverbasierten
             Werkzeuge nicht nutzen. Da es in einer Mehrbenutzer-Umgebung immer
             Sicherheitsbedenken gibt, ist es besser diese Funktionen auf
             Datenbank-Ebene zu verbieten.

.. note:: Datenbank-Namen sind durch folgende Regeln eingeschränkt:

          * Erlaubte Zeichen sind alpha-numerisch [A-Za-z0-9] und
            das Zeichen - Unterstrich [_].
          * Das erste Zeichen muss ein alphabetischer Buchstabe sein.
          * Die maximale Länge eines Datenbank-Namens beträgt 64 Zeichen.

          Tryton überprüft automatisch ob der angegebene Namen diesen
          Regeln entspricht.

.. _Menu-File-New_Database:

Neue Datenbank
  Öffnet einen :term:`Dialog` um eine neue Tryton Datenbank mit einem ersten
  Benutzer "admin" zu erstellen.

  * Tryton Server Einstellungen:

    - `Serververbindung`__
    - Tryton Server Passwort: Das in der Tryton Server-Konfiguration
      hinterlegte Server Passwort.

  * Datenbank Einstellungen:

    - Name: Der Name der neuen Datenbank
    - Standard Sprache: Die standard Sprache der neuen Datenbank
    - Administrator Passwort: Das *admin*-Benutzer Passwort der neuen Datenbank
    - Passwort Wiederholung: Erneute Passwort-Eingabe des neuen 'admin'-Benutzers

  * Aktionen:

    - Erstellen: Erstellt die neue Datenbank mit dem ersten Benutzer *admin*
      und dem angegebenen Passwort
    - Abbrechen: Bricht den Dialog ab ohne zu speichern.

__ File-Server-Connection_

.. note:: Der entsprechende Tryton Datenbankbenutzer (definiert in der Tryton
   Server Konfiguration) muss autorisiert werden um die Datenbank zu erstellen.

.. _Menu-File-Restore_Database:

Datenbank wiederherstellen
  Öffnet einen :term:`Dialog` um eine vorher erstelltes Datenbankbackup
  aus einer Datei wiederherzustellen.

  * *Backup Datei für Wiederherstellung öffnen...* Dialog

    - Aus dem Dateisystem eine Datenbankbackup-Datei auswählen
    - Aktionen:

      + Öffnen: Öffnet die ausgewählte Backup-Datei
      + Abbrechen: Bricht den Vorgang ab.

  * *Datenbank wiederherstellen* Dialog:

    - `Serververbindung`__
    - Tryton Server Passwort: Das in der Tryton Server-Konfiguration
      hinterlegte Server Passwort.
    - File to Restore: Show filename and path.
    - New Database Name: Enter a new name for the database to be restored
    - Actions:

      + Wiederherstellen: Datenbank Wiederherstellung ausführen
      + Abbrechen: Bricht den Vorgang ab.

__ File-Server-Connection_

.. _Menu-File-Backup_Database:

Datenbank sichern
  Öffnet einen :term:`Dialog` um eine existierende Datenbank in eine Datei zu sichern.

  * `Datenbank sichern` Dialog

    - `Serververbindung`__
    - Datenbank: Auswahl der zu sichernden Tryton Datenbank
    - Tryton Server Passwort: Das in der Tryton Server Konfiguration
      hinterlegte Server Passwort.
    - Aktionen:

      + Sichern: Datenbank Sicherung ausführen
      + Abbrechen: Bricht den Vorgang ab.

  * `Speichern unter...` Dialog

    - Auswahl eines Dateinamens und Ort der erstellten Sicherungs-Datei.
    - Speichern der Sicherungs-Datei.

__ File-Server-Connection_

.. _Menu-File-Drop_Database:

Datenbank löschen
  Öffnet einen :term:`Dialog` um eine existierende Tryton Datenbank zu löschen.

  * `Datenbank löschen` dialog

    - `Serververbindung`__
    - Datenbank: Auswahl der zu löschenden Datenbank
    - Tryton Server Passwort: Das in der Tryton Server-Konfiguration
      hinterlegte Server Passwort.

  * Bestätigungs Dialog

    - Ja: Löscht die Datenbank
    - Nein: Keine Löschung der Datenbank
    - Abbrechen: Bricht den Vorgang ab.

__ File-Server-Connection_

.. _File-Server-Connection:

*Serververbindung* Dialog:
  Dieser :term:`Dialog` wird häufig benutzt um die Tryton Serververbindung
  einzustellen. Dieser Dialog zeigt den aktuellen Status der Client/Server
  Kommunikation. Es zeigt zusätzlich an wenn keine Verbindung zum Tryton
  Server besteht. Der *Bearbeiten* Knopf öffnet den Dialog der Verbinungs
  Details:

  * Server: Netzwerkname oder IP-Adresse des Tryton Servers
    (Protokollangaben sind nicht unterstützt)
  * Port: Port auf dem der Tryton Server lauscht.

.. note:: Falls keine Verbindung zum Tryton Server besteht, sind viele Einträge
   des Menüs und der Werkzeugleiste deaktiviert.


Benutzer
^^^^^^^^
Dieser Eintrag der Menüleiste stellt die Eigenschaften des aktuellen Benutzers ein
und stellt die Verbindung mit dem *Anfrage System* von Tryton bereit.

.. _Menu-User-Preferences:

Einstellungen ...
  Ein Einstellungsdialog öffnet sich, in dem der aktuelle Benutzer seine
  persönlichen Einstellungen anzeigen und ändern kann. Alle Benutzereigenschaften
  werden serverseitig gespeichert. Beispielsweise werden beim Anmelden an einem
  anderen Computer diese Einstellungen wiederhergestellt.

  * Name: bürgerlicher Name des Tryton Benutzers.
  * Passwort: Passwort des Tryton Benutzers.
  * E-Mail: E-Mail-Adresse des Tryton Benutzers.
  * Signatur: Signaturblock des Tryton Benutzers.
  * Menüaktion: Definiert die Aktion, welche als `Hauptmenü`__
    ausgeführt wird.
  * Startseite: Definiert die Aktion, welche als
    `Startseite` ausgeführt wird.
  * Sprache: Sprache der Benutzeroberfläche.
  * Zeitzone: Die lokale Zeitzone in der sich der Benutzer befinden.
  * Gruppenzugehörigkeit: Definiert die Mitgliedschaften um Zugriffe zu regeln.

__ Menu-Form-Home_

.. _Menu-user-send-a-request:

Anfrage senden
  Öffnet einen Tab als :term:`Formularansicht` der dem Benutzer
  erlaubt anderen Benutzern der gleichen Datenbank Anfragen zu senden.

.. _Menu-user-read-my-request:

Meine Anfragen lesen:
  Öffnet ein Tab als :term:`Baumansicht` der dem aktuellen Benutzer
  alle zugehörigen Anfragen zeigt. Anfragen haben folgende Felder und Aktionen:

  * Oben

    - Von: Benutzername des Senders
    - An: Benutzername des Empfängers
    - Verweise: Anzahl der angehängten Verweise
    - Betreff: Der Betreff der Anfrage
    - Dringlichkeit: Eine Priorisierung der Anfrage

      + Hoch
      + Niedrig
      + Normal

  * *Anfrage* Tab

    - Anfrage: Der Textteil der Anfrage
    - Bisherige Anfragen: Die Historie der letzten Antworten zu dieser Anfrage

      + Von: Sender der letzten Anfrage
      + An: Empfänger der letzten Anfrage
      + Zusammenfassung: Zusammenfassung des Anfrage-Textes der letzten Anfrage

  * Gültig ab: Definiert Zeit und Datum an dem die Anfrage automatisch
    zugestellt werden soll.
  * Status: Status der Anfrage. Mögliche Stati der Anfrage sind:

    - Entwurf: Die Anfrage ist im System gespeichert, aber nicht abgeschickt
    - Wartend: Die Anfrage wurde abgeschickt ohne bisher eine Antwort erhalten zu haben
    - Schreibt gerade: Die Nachricht ist gerade in Bearbeitung
    - Geschlossen: Die Nachricht wurde geschlossen/erfüllt/beantwortet

  * Aktionen:

    - Senden: Sendet die aktuelle Nachricht
    - Antworten: Erwidert oder beantwortet die aktuelle Nachricht
    - Schließen: Schließt die aktuelle Anfrage

  * *Verweise* Tab

    - Verweise

      + Verweise: Der Verweis Typ
      + (Ziel): Hängt einen Verweis an die Anfrage an.

.. note:: Wenn man von Anfragen spricht, kann man sie sich vorstellen wie
   ein Tryton-internes E-Mail System.


Formular
^^^^^^^^
Das Formular Menü bietet Funktionen zum *aktuellen Formular*, welches gerade
als Tab geöffnet ist. Manche Menüeinträge funktionieren mit einem Datensatz
andere mit mehreren :term:`Datensätzen <Datensatz>`. In der :term:`Formularansicht` ist der
aktuelle Datensatz für diese Operationen ausgewählt. In der :term:`Baumansicht`
werden alle ausgewählten Datensätze benutzt.

.. _Menu-Form-New:

Neu:
  Erstellt einen neuen Datensatz.

.. _Menu-Form-Save:

Speichern:
  Speichert den aktuellen Datensatz

.. _Menu-Form-Duplicate:

Duplizieren:
  Dupliziert den Inhalt des aktuellen Datensatzes in einen neu erstellen Datensatz.

.. _Menu-Form-Delete:

Löschen:
  Löscht den ausgewählten oder aktuellen Datensatz.

.. _Menu-Form-Find:

.. _search_widget:

Suchen...:
  Öffnet einen :term:`Dialog` um :term:`Felder` anhand Suchkriterien und Operatoren
  zu finden.

  * Suchkriterien: Definiert nach den zu suchenden Kriterien
  * Allgemeine Such-Operatoren:

    - ist gleich: Sucht nach Ergebnissen, die exakt dem folgenden Ausdruck entsprechen
    - ist nicht gleich: Sucht nach Ergebnissen, die nicht exakt dem folgenden Ausdruck entsprechen

  * Zusätzliche Such-Operatoren für Nummern, Mengen und Zeichenketten:

    - enthält: Sucht nach Ergebnissen, welche den folgenden Ausdruck enthält
    - enthält nicht: Sucht nach Ergebnissen, welche den folgenden Ausdruck nicht enthält
    - beginnt mit: Sucht nach Ergebnissen, welche mit folgendem Audruck beginnen
    - endet mit: Sucht nach Ergebnissen, welche mit folgendem Ausdruck enden

  * Zusätzliche Such-Operatoren für Nummern und Mengen:

    - ist zwischen: Sucht nach Ergebnissen innerhalb einer Reihe (von - bis)
    - ist nicht zwischen: Sucht nach Ergebnissen außerhalb einer Reihe (von - bis)
    - ist nicht: Gleich wie 'ist unterschiedlich', siehe oben

  * Über *Erweiterte Suche* öffnet man weitere Suchmöglichkeiten.

    - Limit: Schränkt die Anzahl der Suchtreffer ein.
    - Versatz: Überspringt die angegebene Anzahl an Treffern
      und zeigt nur die darauf Folgenden an.

  * Aktionen:

    - Suchen: Sucht nach Ergebnissen, welche den angegebenen Kriterien entsprechen
    - Neu: Erstellt einen neuen Datensatz (wird benutzt wenn durch die Suche nichts
      gefunden wurde und man schnell einen neuen Datensatz anlegen will)
    - OK: Öffnet den ausgewählten Datensatz
    - Abbruch: Bricht den Vorgang ab

.. note:: Um nach inaktiven Datensätzen zu suchen muss das *Aktiv* Suchkriterium auf
        *Nein* gesetzt werden.

.. _Menu-Form-Next:

Nächster:
  Geht zum nächsten Datensatz in der Liste (Reihenfolge)

.. _Menu-Form-Previous:

Vorheriger:
  Geht zum vorherigen Datensatz in der Liste (Reihenfolge).

.. _Menu-Form-Switch_View:

Ansicht wechseln:
  Wechselt die aktuelle Ansicht nach:

  * :term:`Formularansicht`
  * :term:`Baumansicht`
  * :term:`Diagrammansicht`

  Nicht alle Sichten stellen alle Möglichkeiten bereit.

.. _Menu-Form-Menu:

Menü:
  Springt zu oder öffnet den Menü-Tab.

.. _Menu-Form-Home:

Zur Startseite:
  Öffnet einen neuen `Startseite`__ Tab

__ Menu-User-Preferences_

.. _Menu-Form-Close:

Tab schließen:
  Schließt den aktuellen Tab. Ein :term:`Dialog` erscheint bei ungespeicherten Änderungen.

.. _Menu-Form-Previous_Tab:

Vorheriger Tab:
  Zeigt den vorherigen (linken) Tab neben dem aktuellen Tab.

.. _Menu-Form-Next_Tab:

Nächster Tab:
  Zeigt den nächsten (rechten) Tab neben dem aktuellen Tab.

.. _Menu-Form-View_Logs:

Protokoll ansehen...:
  Zeigt generische Informationen des aktuellen Datensatzes.

.. _Menu-Form-Go_to_Record_ID:

Gehe zu Datensatz Nr...:
  Öffnet die angegebene Datensatznummer in der aktuellen Sicht.

.. _Menu-Form-Reload_Undo:

Neu laden/Rückgängig:
  Lädt den Inhalt des aktuellen Tabs neu. Macht Änderungen rückgängig, falls
  das Speichern des aktuellen Datensatzes fehlschlägt.

.. _Menu-Form-Actions:

Aktionen...:
  Zeigt alle Aktionen der aktuellen Sicht, des Modells und Datensatzes.

.. _Menu-Form-Print:

Drucken...:
  Zeigt alle Druckaktionen der aktuellen Sicht, des Modells und Datensatzes.

.. _Menu-Form-Export_Data:

Daten exportieren...:
  Export des aktuellen oder der ausgewählten Datensätze als :term:`CSV`-Datei oder
  öffnet es direkt in Excel.

  * Vordefinierte Exporte

    - Auswahl von vorher abgespeicherten Exporteigenschaften.

  * Alle Felder: Verfügbare Felder des Modells
  * Zu exportierende Felder: Definition der speziellen, zu exportierenden Felder
  * Optionen:

    - Speichern: Speichert den Export als CSV Datei.
    - Öffnen: Öffnet den Export in einem Tabellenkalkulations-Programm.

  * Add field names: Add a header row with field names to the export data.
  * Aktionen:

    - Hinzufügen: Fügt die ausgewählten Felder zu *Zu exportierende Felder* hinzu
    - Entfernen: Löscht die ausgewählten Felder von *Zu exportierende Felder*
    - Leeren: Löscht alle Felder aus *Zu exportierende Felder*
    - Export speichern: Speichert die Feldzuweisungen in einem *vordefinierten Export*
    - Export löschen: Löscht einen *vordefinierten Export*
    - OK: Exportiert die Daten (Aktion hängt von der ausgewählten *Option* ab)
    - Abbrechen: Bricht den Vorgang ab.

.. _Menu-Form-Import_Data:

Daten importieren...:
  Import von Daten von einer :term:`CSV`-Datei.

  * Alle Felder: Verfügbare Felder im Modell (Pflichtfelder sind markiert)
  * Zu importierende Felder: Genaue Reihenfolge aller Spalten der CSV-Datei
  * Importdatei: Öffnen :term:`Dialog` um die zu importierende CSV-Datei auszuwählen
  * CSV Parameter: Einstellungen der ausgewählten CSV-Datei

    - Feldtrennzeichen: Zeichen, welches die einzelnen Spalten
      der CSV-Datei von einander trennt.
    - Texttrennzeichen: Zeichen, welches Textfelder der CSV-Datei einrahmt
    - Kodierung: :term:'Zeichenkodierung' einer CSV-Datei.
    - Zu überspringende Zeilen: Anzahl zu überspringenden Zeilen wie zum
      Beispiel einer Überschrift oder anderen Zeilen.

  * Aktionen:

    - Hinzufügen: Fügt die ausgewählten Felder zu *Zu importierende Felder* hinzu
    - Entfernen: Löscht die ausgewählten Felder von *Zu importierende Felder*
    - Leeren: Löscht alle Felder aus *Zu importierende Felder*
    - OK: Importiert die Daten
    - Abbrechen: Bricht den Vorgang ab.


Einstellungen
^^^^^^^^^^^^^
Das Einstellungs-Menü konfiguriert viele grafische und kontextabhängige Eigenschaften.


Werkzeugleiste
++++++++++++++

.. _Menu-Options-Toolbar-Default:

Standard:
  Zeigt Bezeichnung und Symbole wie in der systemweiten GTK-Konfiguration eingestellt.

.. _Menu-Options-Toolbar-Text_and_Icons:

Text und Symbole:
  Zeigt Bezeichnungen und Symbole in der Werkzeugleiste an.

.. _Menu-Options-Toolbar-Icons:

Symbole:
  Zeigt nur Symbole in der Werkzeugleiste an.

.. _Menu-Options-Toolbar-Text:

Text:
  Zeigt nur Bezeichnungen in der Werkzeugleiste an.

Menüleiste
++++++++++

.. _Menu-Options-Menubar-Accelerators:

Kurzbefehle ändern:
  Falls das Kontrollkästchen aktiv ist, können Schnelltasten eingestellt werden. Siehe auch
  `Maus- und Tastaturbedienung`_

Modus
+++++

.. _Menu-Options-Mode-Normal:

Normal:
  Alle Funktionen des Clients werden angezeigt.

.. _Menu-Options-Mode_PDA:

PDA:
  Der Client wird im abgespeckter Form angezeigt. Der PDA (Persönlicher Daten Assistent) Modus
  blendet das Favoriten Menü in der Baumansicht und die Statusleiste aus.

Formular
++++++++

.. _Menu-Options-Form-Toolbar:

Werkzeugleiste:
  Kontrollkästchen um die Werkzeugleiste ein- und auszuschalten.

.. _Menu-Options-Form-Statusbar:

Statusleiste:
    Kontrollkästchen um die Statusleiste ein- und auszuschalten.

.. _Menu-Options-Form-Save_Columns_Width:

Breite/Höhe speichern:
  Kontrollkästchen zum speichern der manuell geänderte Breite von
  Spalten in Listen und Bäumen. Zusätzlich werden die manuell angepassten
  Breiten und Höhen der Dialog- und Popup-Fenster gespeichert.

.. _Menu-Options-Form-Spell_Checking:

Rechtschreibkorrektur:
  Kontrollkästchen um die Rechtschreibkorrektur in Feldern einzuschalten.

.. _Menu-Options-Form-Tabs_Position:

Position der Tabs:
  Stellt die Position der :term:`Tabs` innerhalb von :term:`Sichten <Sicht>` ein:

  * Oben
  * Links
  * Rechts
  * Unten

.. _Menu-Options-File_Actions:

Dateiaktionen...
  Öffnet einen Dialog um zu den Dateitypen die entsprechende Druck und Öffnen-Aktion auszuwählen.
  Der Dokumentenname wird mit ``"%s"`` als Platzhalter angegeben.

  * Unterstützte Dateitypen:

    - ODT Datei: Open Office Writer Dokument
    - PDF Datei: Adobes(TM) Portable Document Format
    - PNG Datei: Portable Network Graphics Format
    - TXT Datei: Reine Text-Datei

  * Unterstützte Aktionen

    - Öffnen: Das aufzurufende Programm und Parameter welche die angegebene Datei öffnet
    - Drucken: Das aufzurufende Programm und Parameter welches die angegebene Datei druckt

.. _Menu-Options-Email:

E-Mail...:
  Öffnet einen Dialog um das E-Mail-Programm einzustellen.

  * Kommandozeile: Die Kommandozeile um das E-Mail-Programm aufzurufen
  * Platzhalter:

    - ``${to}``: Die Empfänger E-Mail-Adressen
    - ``${cc}``: Die Empfänger E-Mail-Adressen, die eine Kopie der E-Mail erhalten sollen.
    - ``${subject}``: Der Betreff der E-Mail
    - ``${body}``: Der Textteil der E-Mail
    - ``${attachment}``: Der Anhang der E-Mail

  * Beispiele:

    - Thunderbird 2 unter Linux:
      ``thunderbird -compose "to='${to}',cc='${cc}',subject='${subject}',body='${body}',attachment='file://${attachment}'"``

    - Thunderbird 2 auf Windows XP SP3:
      ``"C:\\Programme\\Mozilla Thunderbird\\thunderbird.exe" -compose to="${to}",cc="${cc}",subject="${subject}",body="${body}",attachment="${attachment}"``

.. note:: Der Pfad von *Programme* unterscheidet sich womöglich erheblich abhängig der Sprache ihrer Windows Version.

.. _Menu-Options-Save_Options:

Einstellungen speichern:
  Speichert alle Einstellungen.


Plugins
^^^^^^^
Plugins sind clientseitige Erweiterungen für Tryton. Es gibt ein paar Plugins,
die Tryton im Standard mitbringt.

Ein Plugin ausführen
++++++++++++++++++++
Aktuelle Sicht übersetzen:
  Erstellt eine Übersetzungstabelle der aktuellen Sicht.

Workflow drucken:
  Erstellt ein Schaubild, welches den Workflow der aktuellen Sicht zeigt.

Erweiterten Workflow drucken:
  Wie `Workflow drucken`, allerdings mit zusätzlichen Unter-Workflows welche
  von der aktuellen Sicht abhängig sind.


Favoriten
^^^^^^^^^
Eine Sammlung von benutzerdefinierten Favoriten für spezielle Resourcen.


Hilfe
^^^^^

.. _Menu-Help-Tips:

Tipps...:
  Öffnet den Tipp Dialog.

  * Tipps beim Start von Tryton anzeigen: Der Tipps Dialog wird beim Start
    des Tryton Clients angezeigt
  * Vorheriger: Zeigt den letzten Tipp
  * Nächster: Zeigt den nächsten Tipp

.. _Menu-Help-Keyboard_Shortcuts:

Schnelltasten...:
  Zeigt einen Informations-Dialog über die vordefinierten Schnelltasten an.

  * Widgets zur Bearbeitung: Zeigt Schnelltasten für Texteinträge, verknüpfte
    Einträge und Datums/Zeiteinträge

.. _Menu-Help-About:

Über...:
  Lizenz, Mitwirkende, Autoren von Tryton


Anhang
******


Konfigurations-Dateien
^^^^^^^^^^^^^^^^^^^^^^

::

   ~/.config/tryton/x.y/tryton.conf      # Generelle Konfiguration
   ~/.config/tryton/x.y/accel.map        # Konfiguration der Schnelltasten
   ~/.config/tryton/x.y/known_hosts      # Fingerprints
   ~/.config/tryton/x.y/ca_certs         # Certification Authority (http://docs.python.org/library/ssl.html#ssl-certificates)

