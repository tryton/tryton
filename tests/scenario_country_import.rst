==============
Country Import
==============

Imports::

    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.country.scripts import import_countries, import_zip

Install currency::

    >>> config = activate_modules('country')

Import countries::

    >>> import_countries.do_import()

Import ZIP::

    >>> import_zip.do_import(['us'])
