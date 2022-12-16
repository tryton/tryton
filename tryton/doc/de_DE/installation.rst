Tryton Installation
===================

Voraussetzungen
---------------

 * Python 2.4 oder neuer (http://www.python.org/)
 * pygtk 2.0 oder neuer (http://www.pygtk.org/)
 * librsvg (http://librsvg.sourceforge.net/)
 * python-dateutil (http://labix.org/python-dateutil)
 * simplejson (http://undefined.org/python/#simplejson)
 * Optional: pytz (http://pytz.sourceforge.net/)

Installation
------------

Nach dem Herunterladen und Auspacken der Tryton Quellen wechselt man in das
Verzeichnis in welches das Archiv ausgepackt wurde und führt folgenden Befehl
aus:

    ``python setup.py install``

Für diesen Schritt können Administrator/root Berechtigungen benötigt
werden, da dieser Befehl Tryton standardmäßig in das systemweite Python
site-package Verzeichnis installiert.

Für weitere Installationsoptionen kann man die Dokumentation von
easy_install__ oder distutils__ beachten.

__ http://peak.telecommunity.com/DevCenter/EasyInstall

__ http://docs.python.org/inst/inst.html

Um Tryton ohne Installation zu benutzen kann man ``bin/tryton`` im Verzeichnis
des entpackten Archiv aufrufen.

