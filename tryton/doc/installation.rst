Installing tryton
=================

Prerequisites
-------------

 * Python 2.6 or later (http://www.python.org/)
 * pygtk 2.6 or later (http://www.pygtk.org/)
 * librsvg (http://librsvg.sourceforge.net/)
 * python-dateutil (http://labix.org/python-dateutil)
 * weakrefset for Python 2.6 (https://code.google.com/p/weakrefset/)
 * Optional: simplejson (http://undefined.org/python/#simplejson)
 * Optional: pytz (http://pytz.sourceforge.net/)
 * Optional: cdecimal (http://www.bytereef.org/mpdecimal/index.html)

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

