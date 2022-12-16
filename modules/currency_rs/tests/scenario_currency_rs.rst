====================
Currency RS Scenario
====================

Imports::

    >>> import datetime as dt
    >>> import os

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> previous_week = today - dt.timedelta(days=7)
    >>> before_previous_week = previous_week - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('currency_rs')

Import models::

    >>> Currency = Model.get('currency.currency')
    >>> Cron = Model.get('currency.cron')

Create some currencies::

    >>> eur = Currency(name="Euro", code='EUR', symbol="€")
    >>> eur.save()
    >>> rsd = Currency(name="Serbian Dinar", code='RSD', symbol="din.")
    >>> rsd.save()

Setup cron::

    >>> cron = Cron()
    >>> cron.source = 'nbs_rs'
    >>> cron.rs_username = os.getenv('NBS_RS_USERNAME')
    >>> cron.rs_password = os.getenv('NBS_RS_PASSWORD')
    >>> cron.rs_license_id = os.getenv('NBS_RS_LICENSE_ID')
    >>> cron.rs_list_type = '3'
    >>> cron.frequency = 'daily'
    >>> cron.day = None
    >>> cron.currency = rsd
    >>> cron.currencies.append(Currency(eur.id))
    >>> cron.last_update = before_previous_week
    >>> cron.save()

Run update::

    >>> cron.click('run')
    >>> cron.last_update >= previous_week
    True

    >>> rsd.reload()
    >>> rate = [r for r in rsd.rates if r.date < today][0]
    >>> rate.rate
    Decimal('1.000000')
    >>> eur.reload()
    >>> rate = [r for r in eur.rates if r.date < today][0]
    >>> bool(rate.rate)
    True
