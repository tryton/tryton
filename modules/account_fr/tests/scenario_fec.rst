============
FEC Scenario
============

Imports::

    >>> import datetime
    >>> import os
    >>> import io
    >>> from decimal import Decimal
    >>> from dateutil.relativedelta import relativedelta
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.account_fr.tests.tools import create_chart, \
    ...     get_accounts

    >>> today = datetime.date(2018, 1, 1)

Install account_fr::

    >>> config = activate_modules('account_fr')

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> company.party.siren = '820043784'
    >>> company.party.save()

Create last year fiscal year::

    >>> fiscalyear_previous = create_fiscalyear(
    ...     company, today=today - relativedelta(years=1))
    >>> fiscalyear_previous.click('create_period')
    >>> period_previous = fiscalyear_previous.periods[0]

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company, today=today)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

Create parties::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create some moves::

    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> journal_revenue, = Journal.find([
    ...         ('code', '=', 'REV'),
    ...         ])
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

    >>> move = Move()
    >>> move.period = period_previous
    >>> move.journal = journal_revenue
    >>> move.date = period_previous.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(5)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(5)
    >>> line.party = party
    >>> move.post_date = period_previous.start_date
    >>> move.post_number = '1'
    >>> move.click('post')

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(10)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(10)
    >>> line.party = party
    >>> move.post_date = period.start_date
    >>> move.post_number = '1'
    >>> move.click('post')

Generate FEC::

    >>> deferral_journal = Journal(name="Deferral", type='situation')
    >>> deferral_journal.sequence = journal_cash.sequence
    >>> deferral_journal.save()

    >>> FEC = Wizard('account.fr.fec')
    >>> FEC.form.fiscalyear = fiscalyear
    >>> FEC.form.deferral_journal = deferral_journal
    >>> FEC.execute('generate')
    >>> FEC.form.filename
    >>> file = os.path.join(os.path.dirname(__file__), 'FEC.csv')
    >>> FEC.form.file.decode('utf-8') == io.open(file, mode='rb').read().decode('utf-8')
    True
