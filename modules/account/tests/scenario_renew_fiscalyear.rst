=================================
Account Renew Fiscalyear Scenario
=================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> today = datetime.date.today()
    >>> end_year = today + relativedelta(month=12, day=31)

Install account::

    >>> config = activate_modules('account')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods.new()
    >>> period.name = 'Adjustment'
    >>> period.start_date = end_year
    >>> period.end_date = end_year
    >>> period.type = 'adjustment'
    >>> fiscalyear.save()

Set the sequence number::

    >>> sequence = fiscalyear.post_move_sequence
    >>> sequence.number_next = 10
    >>> sequence.save()

Renew fiscalyear using the wizard::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = False
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> len(new_fiscalyear.periods)
    12
    >>> int(new_fiscalyear.post_move_sequence.number_next)
    10

Renew fiscalyear resetting sequences::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.form.reset_sequences = True
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]
    >>> int(new_fiscalyear.post_move_sequence.number_next)
    1
