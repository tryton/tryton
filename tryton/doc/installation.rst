Installing tryton
=================

Prerequisites
-------------

 * Python 2.7 or later (http://www.python.org/)
 * pygtk 2.22 or later (http://www.pygtk.org/)
 * librsvg (http://librsvg.sourceforge.net/)
 * python-dateutil (http://labix.org/python-dateutil)
 * chardet (http://pypi.python.org/pypi/chardet)
 * Optional: simplejson (http://undefined.org/python/#simplejson)
 * Optional: cdecimal (http://www.bytereef.org/mpdecimal/index.html)
 * Optional: GooCalendar (http://code.google.com/p/goocalendar/)

Installation
------------

Once you've downloaded and unpacked a tryton source release, enter the
directory where the archive was unpacked, and run:

    ``python setup.py install``

Note that you may need administrator/root privileges for this step, as
this command will by default attempt to install tryton to the Python
site-packages directory on your system.

For advanced options, please refer to the easy_install__ and/or the
distutils__ documentation:

__ http://peak.telecommunity.com/DevCenter/EasyInstall

__ http://docs.python.org/inst/inst.html

To use without installation, run ``bin/tryton`` from where the archive was
unpacked.

