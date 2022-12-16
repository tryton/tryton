==============
Country Import
==============

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.country.scripts import import_countries, import_zip

Install currency::

    >>> config = activate_modules('country')

Import countries::

    >>> Country = Model.get('country.country')
    >>> belgium = Country(name="Belgium", code='BE')
    >>> belgium.save()

    >>> import_countries.do_import()

Import ZIP::

    >>> import_zip.do_import(['us'])
