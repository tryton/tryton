Glossar
#######

.. glossary::
   :sorted:

   Aktionen
      Eine *Aktion* ist eine Funktion, die durch einen Benutzereingriff ausgelöst wird.
      *Aktionen* werden über Menü-Einträge oder Drücken von Knöpfen aufgerufen.
      Aktionen stellen oft :term:`Wizards` bereit.

   Infoseite
      Die *Infoseite* ist ein :term:`Sicht`-Typ, mit der Möglichkeit andere Sichten zu verarbeiten.
      Diese Art von Sicht ist weder dokumentiert noch bisher benutzt.

   Zeichen Kodierung
      Siehe [WP-ENCOD]_

   CSV
      Dateiformat für Komma separierte Werte (Comma Separated Values). Siehe [WP-CSV]_

   Daten
      *Daten* sind Informationen, welche von Benutzern erstellt wurden.


   Dialog
      *Dialoge* werden benutzt um Einstellungen für verschiedene :term:`Aktionen`
      abzufragen oder um eine Bestätigung des Benutzers abzuwarten.

   Felder
      *Felder* sind Attribute von *Daten-Objekten*. Die *Felder* sind
      in relationalen Datenbanken als Tabellenspalten dargestellt.

   Formularansicht
      Die *Formularansicht* ist ein :term:`Sicht-Typ <Sicht>`, der einen einzigen
      :term:`Datensatz` darstellt.

   Formular
      Das *Formular* ist eine grundlegende Art von :term:`Sicht` in Tryton.
      *Formulare* können unterschiedliche Sichten auf :term:`Daten`: bereitstellen.

      * :term:`Formularansicht`
      * :term:`Baumansicht`
      * :term:`Diagrammansicht`

   Diagrammansicht
      *Diagrammansicht* ist eine Art von :term:`Sicht` um Datensätze in einem
      Diagramm darzustellen. Die *Diagrammansichten* können Tortendiagramme oder
      Balkendiagramme sein.

   Hauptbereich
      Der *Hauptbereich* ist eine großer Teil in der Mitte des
      :term:`Tryton Client`. *Den Tryton Client benutzen* bezeichnet hauptsächlich den
      *Hauptbereich*. Er beinhaltet :term:`Tabs` um die verschiedenen
      :term:`Formulare <Formular>` zu ordnen und darzustellen.

   Modell
      Ein *Modell* beschreibt wie Daten intern strukturiert und gespeichert werden.
      Modelle legen auch fest, wie auf Daten zugegriffen wird. Modelle definieren den
      Rahmen, in dem Datensätze und Beziehungen für ein bestimmtes Aufgabengebiet
      hinterlegt werden können.

   Module
      *Module* sind Pakete aus Dateien für den :term:`Tryton Server`. Ein
      *Module* definiert :term:`Modelle <Modell>`, die Präsentation der Information
      (:term:`Sichten <Sicht>`), Funktionen, :term:`Aktionen` und Voreinstellungen.
      Zusätzlich können *Module* standardisierte Systemdaten wie zum Beispiel die ISO
      Namen der Länder beinhalten. *Module* sind in Tryton generisch aufgebaut.
      Das bedeutet, sie sind so einfach, dass die meisten nur die grundlegende
      Funktionalität bereitzustellen. Spezielle Anpassungen für unterschiedliche
      Anwendungsfälle werden in Zusatzmodulen realisiert.

   Plugins
      Ein *Plugin* ist ein Zusatzmodul für den :term:`Tryton Client`.

   Popup
      Ein kleines Fenster, welches sich im Hauptbereich in den Vordergrund stellt.

   Datensatz
      Ein Datensatz ist eine zusammengefasste Einheit von :term:`Datenfeldern
      <felder>`. *Datensätze* werden als Zeilen
      in einer relationalen Datenbank-Tabellen dargestellt.

   Tabs
      *Tabs* sind :term:`Widgets` um verschiedene Inhalte nebeneinander darzustellen.
      Sie werden benutzt um zwischen verschiedenen Aufgabengebieten umzuschalten.
      Tryton benutzt *Tabs* auf zwei Ebenen:

      * Ein unterteilter :term:`Hauptbereich`.
      * Tabs innerhalb einer :term:`Sicht`.

      Der Hauptbereich besteht aus *Tabs*, welche das Hauptmenü und alle
      Sichten zu einem dazugehörigen :term:`Modell` einbetten. Der andere Typ eines
      *Tabs* wird innerhalb einer :term:`Sicht` benutzt um die
      verschiedene Bereiche des gleichen Modells visuell abzutrennen.
      Diese *Tabs* werden benutzt um die Inhalte eines Modells in verschiedene
      Unterpunkte zu strukturieren.

   Drei Schichten
      Eine *Drei-Schichten*-Anwendungs-Plattform wie Tryton, besteht aus drei
      verschiedenen Software Komponenten:

      1. Die Speicher- oder Daten-Schicht
      2. Die Logik- oder Anwendungs-Schicht
      3. Die Präsentations-Schicht

      Die Speicher-Schicht im Tryton-Plattform wird durch die PostgreSQL
      Datenbank bereitgestellt. Die Logik-Schicht wird durch den
      :term:`Tryton Server` und dessen :term:`Module` zur Verfügung gestellt.
      Die Präsentations-Schicht ist hauptsächlich durch den :term:`Tryton Client`
      dargestellt. In einer *Drei-Schichten*-Architektur verbindet sich die
      Präsentations-Schicht (Client) nie direkt mit der Speicher-Schicht.
      Jede Kommunikation wird durch die Logik-Schicht überwacht.

   Baumansicht
      Die *Baumansicht* ist ein :term:`Sicht-Typ <Sicht>`, der mehrere :term:`Datensätze <Datensatz>` gleichzeitig anzeigt.
      *Baumansichten* können flache Listen oder Tabellen wie auch verschachtelte baumartige Listen sein.

   Tryton Server
      Der *Tryton Server* ist die Anwendungs- oder Logik-Schicht in der
      :term:`drei Schichten` Anwendungs-Plattform *Tryton*. Der *Tryton Server*
      verbindet die zugrunde liegende Anwendungslogik der verschiedenen
      :term:`Module` mit den dazugehörigen Datensätzen. Der
      *Tryton Server* stellt verschiedene Schnittstellen zur Darstellung der
      erstellten Informationen bereit:

      * :term:`Tryton Client`: (grafische Benutzeroberläche GUI)
      * XMLRPC siehe [WP-XMLRPC]_
      * WebDAV siehe [WP-WebDAV]_
      * OpenOffice

   Tryton Client
      Die *Tryton client* Anwendung ist der grafische Benutzeroberfläche (GUI)
      des :term:`Tryton Servers <Tryton server>`.

   Sicht
      Eine *Sicht* ist die visuelle Präsentation von :term:`Daten`.
      *Sichten* befinden sich in :term:`Tabs` im :term:`Hauptbereich` des
      :term:`Tryton Client`. Es gibt zwei grundsätzliche Typen von *Sichten* in Tryton:

      1. :term:`Formular`
      2. :term:`Infoseite`

      Jede der Sichten-Typen hat verschiedene Arten der Darstellung. *Sichten*
      sind aus mehreren :term:`Widgets` aufgebaut und stellen oft zusätzliche
      :term:`Aktionen` bereit. Es ist auch möglich die gleichen Daten mit
      verschiedenen alternativen Sichten darzustellen.

   Widgets
      Ein *Widget* ist ein visuelles Steuerelement der grafischen
      Benutzeroberfläche (GUI). Einige *Widgets* stellen lediglich Informationen
      dar, Andere erlauben es dem Benutzer Änderungen zu machen. Bespiele von
      *Widgets* sind Knöpfe, Check-Boxen, Eingabefelder, Auswahllisten,
      Tabellen, Listen, Bäume, ...

   Wizards
      *Wizards* beinhalten mehrere aufeinander folgende Schritte um komplexe
      :term:`Aktionen` auszuführen. Ein *Wizard* teilt die Komplexität
      mancher Aktionen in mehrere geführte Schritte auf.

Quellen
*******

.. [WP-XMLRPC] http://de.wikipedia.org/wiki/XMLRPC

.. [WP-WebDAV] http://de.wikipedia.org/wiki/Webdav

.. [WP-CSV] http://de.wikipedia.org/wiki/CSV_%28Dateiformat%29 
.. [WP-ENCOD] http://de.wikipedia.org/wiki/Zeichenkodierung


