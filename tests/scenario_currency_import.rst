===============
Currency Import
===============

Imports::

    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.scripts import import_currencies

Install currency::

    >>> config = activate_modules('currency')

Import currencies::

    >>> import_currencies.do_import()
