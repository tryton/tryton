.. _topics-install:

======================
How to install Tryton
======================

Prerequisites
=============

    * Python 3.4 or later (http://www.python.org/)
    * Werkzeug (http://werkzeug.pocoo.org/)
    * wrapt (https://github.com/GrahamDumpleton/wrapt)
    * lxml 2.0 or later (http://lxml.de/)
    * relatorio 0.7.0 or later (http://relatorio.tryton.org/)
    * Genshi (http://genshi.edgewall.org/)
    * python-dateutil (http://labix.org/python-dateutil)
    * polib (https://bitbucket.org/izi/polib/wiki/Home)
    * python-sql 0.5 or later (http://code.google.com/p/python-sql/)
    * passlib (https://bitbucket.org/ecollins/passlib)
    * Optional: psycopg 2.5.0 or later (http://www.initd.org/)
    * Optional: psycopg2cffi 2.5.0 or later
      (http://github.com/chtd/psycopg2cffi)
    * Optional: pydot (http://code.google.com/p/pydot/)
    * Optional: sphinx (http://sphinx.pocoo.org/)
    * Optional: python-Levenshtein
      (http://github.com/miohtama/python-Levenshtein)
    * Optional: bcrypt (https://github.com/pyca/bcrypt)
    * Optional: html2text (https://pypi.python.org/pypi/html2text)

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

          * http://setuptools.readthedocs.io/en/latest/easy_install.html
          * http://docs.python.org/inst/inst.html

    * Without installation, just run ``bin/trytond`` from where the archive was
      unpacked.

.. warning::
      Note that you may need administrator/root privileges for this step, as
      this command will by default attempt to install trytond to the Python
      site-packages directory on your system.
..
