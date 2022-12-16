=========================
Currency Compute Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.currency.tests.tools import get_currency

Activate modules::

    >>> config = activate_modules('currency')

Call compute::

    >>> Currency = Model.get('currency.currency')
    >>> usd = get_currency(code='USD')
    >>> eur = get_currency(code='EUR')
    >>> Currency.compute(usd.id, Decimal('10.00'), eur.id, {})
    Decimal('20.00')
