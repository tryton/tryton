============
FEC Scenario
============

Imports::

    >>> import datetime as dt
    >>> import io
    >>> import os
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_fiscalyear
    >>> from trytond.modules.account_fr.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('account_fr', create_company, create_chart)

Setup company::

    >>> company = get_company()
    >>> siren = company.party.identifiers.new(type='fr_siren')
    >>> siren.code = '820043784'
    >>> company.party.save()

Create last year fiscal year::

    >>> fiscalyear_previous = create_fiscalyear(
    ...     today=(dt.date(2017, 1, 1), dt.date(2017, 12, 31)))
    >>> fiscalyear_previous.click('create_period')
    >>> period_previous = fiscalyear_previous.periods[0]

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(
    ...     today=(dt.date(2018, 1, 1), dt.date(2018, 12, 31)))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
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
    >>> move.save()
    >>> Move.write([move.id], {
    ...         'post_date': period_previous.start_date,
    ...         'number': '1',
    ...         }, config.context)
    >>> move.click('post')

With an empty line::

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
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = line.credit = Decimal(0)
    >>> move.save()
    >>> Move.write([move.id], {
    ...         'post_date': period.start_date,
    ...         'number': '1',
    ...         }, config.context)
    >>> move.click('post')

With reconciliation::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = revenue
    >>> line.credit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.debit = Decimal(42)
    >>> line.party = party
    >>> move.save()
    >>> reconcile1, = [l for l in move.lines if l.account == receivable]
    >>> Move.write([move.id], {
    ...         'post_date': period.start_date,
    ...         'number': '2',
    ...         }, config.context)
    >>> move.click('post')
    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = cash
    >>> line.debit = Decimal(42)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.credit = Decimal(42)
    >>> line.party = party
    >>> move.save()
    >>> Move.write([move.id], {
    ...         'post_date': period.start_date,
    ...         'number': '3',
    ...         }, config.context)
    >>> move.click('post')
    >>> reconcile2, = [l for l in move.lines if l.account == receivable]
    >>> reconcile_lines = Wizard('account.move.reconcile_lines',
    ...     [reconcile1, reconcile2])
    >>> reconcile_lines.state
    'end'
    >>> reconcile_date = reconcile1.reconciliation.create_date

Balance non-deferral::

    >>> Period = Model.get('account.period')
    >>> Account = Model.get('account.account')

    >>> journal_closing = Journal(name="Closing", code="CLO", type='situation')
    >>> journal_closing.save()

    >>> period_closing = Period(name="Closing")
    >>> period_closing.fiscalyear = fiscalyear
    >>> period_closing.start_date = fiscalyear.end_date
    >>> period_closing.end_date = fiscalyear.end_date
    >>> period_closing.type = 'adjustment'
    >>> period_closing.save()

    >>> balance_non_deferral = Wizard('account.fiscalyear.balance_non_deferral')
    >>> balance_non_deferral.form.fiscalyear = fiscalyear
    >>> balance_non_deferral.form.journal = journal_closing
    >>> balance_non_deferral.form.period = period_closing
    >>> balance_non_deferral.form.credit_account, = Account.find([
    ...         ('code', '=', '120'),
    ...         ])
    >>> balance_non_deferral.form.debit_account, = Account.find([
    ...         ('code', '=', '129'),
    ...         ])
    >>> balance_non_deferral.execute('balance')
    >>> move, = balance_non_deferral.actions[0]
    >>> move.click('post')

Generate FEC::

    >>> FEC = Wizard('account.fr.fec')
    >>> FEC.form.fiscalyear = fiscalyear
    >>> FEC.form.deferral_period = period_closing
    >>> FEC.execute('generate')
    >>> FEC.form.filename
    >>> file = os.path.join(os.path.dirname(__file__), 'FEC.csv')
    >>> with io.open(file, mode='rb') as fp:
    ...     template = fp.read().decode('utf-8')
    >>> current_date = reconcile_date.strftime('%Y%m%d')
    >>> template = template.format(
    ...         current_date=current_date,
    ...         )
    >>> assertEqual(FEC.form.file.decode('utf-8'), template)

Generate FEC for previous fiscal year::

    >>> FEC = Wizard('account.fr.fec')
    >>> FEC.form.fiscalyear = fiscalyear_previous
    >>> FEC.execute('generate')
    >>> file = os.path.join(os.path.dirname(__file__), 'FEC-previous.csv')
    >>> with io.open(file, mode='rb') as fp:
    ...     assertEqual(FEC.form.file.decode('utf-8'), fp.read().decode('utf-8'))
