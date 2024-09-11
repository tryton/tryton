=======================
Account Active Scenario
=======================

Imports::

    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('account', create_company, create_chart)

    >>> Account = Model.get('account.account')

Create fiscal year::

    >>> fiscalyear = create_fiscalyear()
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[1]

Get accounts::

    >>> accounts = get_accounts()
    >>> cash = accounts['cash']

Check active without start or end date::

    >>> cash.active
    True
    >>> len(Account.find([('id', '=', cash.id)]))
    1
    >>> len(Account.find([('id', '=', cash.id), ('active', '=', True)]))
    1
    >>> len(Account.find([('id', '=', cash.id), ('active', 'in', [True])]))
    1
    >>> len(Account.find([('id', '=', cash.id), ('active', 'in', [True, False])]))
    1

Check negative search::

    >>> len(Account.find([('id', '=', cash.id), ('active', '=', False)]))
    0
    >>> len(Account.find([('id', '=', cash.id), ('active', 'in', [False])]))
    0

Check active with a start date::

    >>> cash.start_date = period.start_date
    >>> cash.save()

    >>> with config.set_context(date=period.start_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=period.end_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.start_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.start_date - relativedelta(days=1)):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    False
    0
    >>> with config.set_context(date=fiscalyear.end_date - relativedelta(days=1)):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1

Check active with an end date::

    >>> cash.start_date = None
    >>> cash.end_date = period.end_date
    >>> cash.save()

    >>> with config.set_context(date=period.start_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=period.end_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.end_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.start_date - relativedelta(days=1)):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.end_date + relativedelta(days=1)):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    False
    0

Check active with start and end date::

    >>> cash.start_date = period.start_date
    >>> cash.end_date = period.end_date
    >>> cash.save()

    >>> with config.set_context(date=period.start_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=period.end_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.start_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.end_date):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    True
    1
    >>> with config.set_context(date=fiscalyear.start_date - relativedelta(days=1)):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    False
    0
    >>> with config.set_context(date=fiscalyear.end_date + relativedelta(days=1)):
    ...     Account(cash.id).active
    ...     len(Account.find([('id', '=', cash.id)]))
    False
    0
