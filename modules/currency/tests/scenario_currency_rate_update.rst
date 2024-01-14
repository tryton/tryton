====================
Currency Rate Update
====================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> previous_week = today - dt.timedelta(days=7)
    >>> before_previous_week = previous_week - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('currency')

Import models::

    >>> Currency = Model.get('currency.currency')
    >>> Cron = Model.get('currency.cron')

Create some currencies::

    >>> eur = Currency(name="Euro", code='EUR', symbol="€")
    >>> eur.save()
    >>> usd = Currency(name="U.S. Dollar", code='USD', symbol="$")
    >>> usd.save()

Setup cron::

    >>> cron = Cron()
    >>> cron.source = 'ecb'
    >>> cron.frequency = 'daily'
    >>> cron.day = None
    >>> cron.currency = eur
    >>> cron.currencies.append(Currency(usd.id))
    >>> cron.last_update = before_previous_week
    >>> cron.save()

Run update::

    >>> cron.click('run')
    >>> cron.last_update >= previous_week
    True

    >>> eur.reload()
    >>> rate = [r for r in eur.rates if r.date < today][0]
    >>> rate.rate
    Decimal('1.000000')
    >>> rate = [r for r in usd.rates if r.date < today][0]
    >>> bool(rate.rate)
    True
