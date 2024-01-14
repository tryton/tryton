==============
Country Import
==============

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.country.scripts import (
    ...     import_countries, import_postal_codes)
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('country')

Import countries::

    >>> Country = Model.get('country.country')
    >>> belgium = Country(name="Belgium", code='BE')
    >>> belgium.save()

    >>> import_countries.do_import()

Import postal codes::

    >>> import_postal_codes.do_import(['us'])
