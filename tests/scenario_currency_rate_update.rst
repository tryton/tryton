====================
Currency Rate Update
====================

Imports::

    >>> import datetime as dt
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)
    >>> before_yesterday = yesterday - dt.timedelta(days=1)

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
    >>> cron.last_update = before_yesterday
    >>> cron.save()

Run update::

    >>> cron.click('run')
    >>> cron.last_update >= yesterday
    True

    >>> eur.reload()
    >>> rate, = [r for r in eur.rates if r.date == yesterday]
    >>> rate.rate
    Decimal('1.000000')
    >>> rate, = [r for r in usd.rates if r.date == yesterday]
    >>> bool(rate.rate)
    True
