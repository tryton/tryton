Installing tryton
=================

Prerequisites
-------------

 * Python 3.4 or later (http://www.python.org/)
 * gtk+ 3.20 or later and py-gobject3 (http://www.gtk.org/)
 * librsvg (http://librsvg.sourceforge.net/)
 * python-dateutil (http://labix.org/python-dateutil)
 * Optional: GooCalendar 0.4 or later (https://pypi.python.org/pypi/GooCalendar)

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

__ http://setuptools.readthedocs.io/en/latest/easy_install.html

__ http://docs.python.org/inst/inst.html

To use without installation, run ``bin/tryton`` from where the archive was
unpacked.

