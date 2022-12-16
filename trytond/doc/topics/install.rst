.. _topics-install:

======================
How to install Tryton
======================

Prerequisites
=============

    * Python 2.6 or later (http://www.python.org/)
    * lxml 2.0 or later (http://codespeak.net/lxml/)
    * relatorio 0.2.0 or later (http://relatorio.openhex.org/)
    * python-dateutil (http://labix.org/python-dateutil)
    * polib (https://bitbucket.org/izi/polib/wiki/Home)
    * Optional: psycopg 2 or later (http://www.initd.org/)
    * Optional: MySQL-python (http://sourceforge.net/projects/mysql-python/)
    * Optional: pywebdav 0.9.8 or later (http://code.google.com/p/pywebdav/)
    * Optional: pydot (http://code.google.com/p/pydot/)
    * Optional: pytz (http://pytz.sourceforge.net/)
    * Optional: unoconv http://dag.wieers.com/home-made/unoconv/)
    * Optional: sphinx (http://sphinx.pocoo.org/)
    * Optional: simplejson (http://undefined.org/python/#simplejson)
    * Optional: cdecimal (http://www.bytereef.org/mpdecimal/index.html)
    * Optional: python-Levenshtein
      (http://github.com/miohtama/python-Levenshtein)

Install Tryton
==============

There are three easy options to install Tryton:

    * Install the version provided by your operating system distribution. This
      is the quickest and recommended option for those who has operating system
      that distributes Tryton.

    * Install an official release. Once you've downloaded and unpacked a
      trytond source release, enter the directory where the archive was
      unpacked, and run: ``python setup.py install``

      For advanced options, please refer to the easy_install and/or the
      distutils documentation:

          * http://peak.telecommunity.com/DevCenter/EasyInstall
          * http://docs.python.org/inst/inst.html

    * Without installation, just run ``bin/trytond`` from where the archive was
      unpacked.

.. warning::
      Note that you may need administrator/root privileges for this step, as
      this command will by default attempt to install trytond to the Python
      site-packages directory on your system.
..
