====================
Currency RO Scenario
====================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> previous_month = today - dt.timedelta(days=30)
    >>> before_previous_month = previous_month - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('currency_ro')

Import models::

    >>> Currency = Model.get('currency.currency')
    >>> Cron = Model.get('currency.cron')

Create some currencies::

    >>> eur = Currency(name="Euro", code='EUR', symbol="€")
    >>> eur.save()
    >>> ron = Currency(name="Romanian Leu", code='RON', symbol="L")
    >>> ron.save()

Setup cron::

    >>> cron = Cron()
    >>> cron.source = 'bnr_ro'
    >>> cron.frequency = 'daily'
    >>> cron.day = None
    >>> cron.currency = ron
    >>> cron.currencies.append(Currency(eur.id))
    >>> cron.last_update = before_previous_month
    >>> cron.save()

Run update::

    >>> cron.click('run')
    >>> cron.last_update >= previous_month
    True

    >>> ron.reload()
    >>> rate = [r for r in ron.rates if r.date < today][0]
    >>> rate.rate
    Decimal('1.000000')
    >>> eur.reload()
    >>> rate = [r for r in eur.rates if r.date < today][0]
    >>> bool(rate.rate)
    True
