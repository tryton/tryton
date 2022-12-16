=======================
Account Active Scenario
=======================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts

Install account::

    >>> config = activate_modules('account')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[1]

Create chart of accounts::

    >>> Account = Model.get('account.account')
    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> cash = accounts['cash']

Check active without start or end date::

    >>> cash.active
    True
    >>> len(Account.find([('id', '=', cash.id)]))
    1

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
