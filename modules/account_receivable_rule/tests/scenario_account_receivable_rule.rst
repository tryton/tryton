================================
Account Receivable Rule Scenario
================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('account_receivable_rule')

    >>> Journal = Model.get('account.journal')
    >>> Party = Model.get('party.party')
    >>> Move = Model.get('account.move')
    >>> ReceivableRule = Model.get('account.account.receivable.rule')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create multiple receivable::

    >>> receivable1, = accounts['receivable'].duplicate()
    >>> receivable2, = accounts['receivable'].duplicate()

Setup journals::

    >>> journal_general = Journal(name="General", type='general')
    >>> journal_general.save()
    >>> journal_revenue, = Journal.find([('code', '=', "REV")])
    >>> journal_cash, = Journal.find([('code', '=', "CASH")])

Create a receivable rule::

    >>> receivable_rule = ReceivableRule()
    >>> receivable_rule.account = accounts['receivable']
    >>> receivable_rule.journal = journal_general
    >>> receivable_rule.priorities = 'maturity_date|account'
    >>> account_rule1 = receivable_rule.accounts.new()
    >>> account_rule1.account = receivable1
    >>> account_rule2 = receivable_rule.accounts.new()
    >>> account_rule2.account = receivable2
    >>> account_rule2.only_reconcile = False
    >>> receivable_rule.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create receivable lines for 100::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('50.00')
    >>> line = move.lines.new()
    >>> line.account = receivable1
    >>> line.party = customer
    >>> line.debit = Decimal('50.00')
    >>> line.maturity_date = period.start_date
    >>> move.click('post')

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('20.00')
    >>> line = move.lines.new()
    >>> line.account = receivable2
    >>> line.party = customer
    >>> line.debit = Decimal('20.00')
    >>> line.maturity_date = period.start_date
    >>> move.click('post')

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('30.00')
    >>> line = move.lines.new()
    >>> line.account = receivable2
    >>> line.party = customer
    >>> line.debit = Decimal('30.00')
    >>> line.maturity_date = period.end_date
    >>> move.click('post')

Receive 80::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['cash']
    >>> line.debit = Decimal('80.00')
    >>> line = move.lines.new()
    >>> line.account = accounts['receivable']
    >>> line.party = customer
    >>> line.credit = Decimal('80.00')
    >>> move.click('post')

Check balance of accounts::

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('-80.00')
    >>> receivable1.reload()
    >>> receivable1.balance
    Decimal('50.00')
    >>> receivable2.reload()
    >>> receivable2.balance
    Decimal('50.00')


Apply receivable rule::

    >>> receivable_rule.click('apply')

Check balance of accounts::

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('0.00')
    >>> receivable1.reload()
    >>> receivable1.balance
    Decimal('0.00')
    >>> receivable2.reload()
    >>> receivable2.balance
    Decimal('20.00')
