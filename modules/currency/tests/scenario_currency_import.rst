===============
Currency Import
===============

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.currency.scripts import import_currencies
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('currency')

Import currencies::

    >>> Currency = Model.get('currency.currency')
    >>> eur = Currency(name="Euro", symbol="€", code='EUR')
    >>> eur.save()

    >>> import_currencies.do_import()
