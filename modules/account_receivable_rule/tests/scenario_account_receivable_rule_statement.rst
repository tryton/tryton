==========================================
Account Receivable Rule Statement Scenario
==========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['account_receivable_rule', 'account_statement'],
    ...     create_company, create_chart)

    >>> AccountJournal = Model.get('account.journal')
    >>> Journal = Model.get('account.journal')
    >>> Move = Model.get('account.move')
    >>> Party = Model.get('party.party')
    >>> ReceivableRule = Model.get('account.account.receivable.rule')
    >>> Statement = Model.get('account.statement')
    >>> StatementJournal = Model.get('account.statement.journal')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()

Create multiple receivable::

    >>> receivable_bis, = accounts['receivable'].duplicate()

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
    >>> account_rule = receivable_rule.accounts.new()
    >>> account_rule.account = receivable_bis
    >>> receivable_rule.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create receivable bis of 50::

    >>> move = Move()
    >>> move.period = period
    >>> move.journal = journal_revenue
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = accounts['revenue']
    >>> line.credit = Decimal('50.00')
    >>> line = move.lines.new()
    >>> line.account = receivable_bis
    >>> line.party = customer
    >>> line.debit = Decimal('50.00')
    >>> line.maturity_date = period.start_date
    >>> move.click('post')

Create statement receiving 50 from customer on receivable::

    >>> account_journal, = AccountJournal.find([('code', '=', 'STA')], limit=1)
    >>> statement_journal = StatementJournal(
    ...     name="Journal",
    ...     journal=account_journal,
    ...     account=accounts['cash'],
    ...     validation='balance',
    ...     )
    >>> statement_journal.save()

    >>> statement = Statement(
    ...     name="Statement",
    ...     journal=statement_journal,
    ...     start_balance=Decimal('0.00'),
    ...     end_balance=Decimal('50.00'),
    ...     )
    >>> statement_line = statement.lines.new()
    >>> statement_line.number = '0001'
    >>> statement_line.description = "Description"
    >>> statement_line.date = period.start_date
    >>> statement_line.amount = Decimal('50.00')
    >>> statement_line.party = customer
    >>> assertEqual(statement_line.account, accounts['receivable'])
    >>> statement_line.amount
    Decimal('50.00')

Validate and Post statement::

    >>> statement.click('validate_statement')
    >>> statement.state
    'validated'
    >>> statement.click('post')
    >>> statement.state
    'posted'

Check receivable bis has been credited::

    >>> accounts['receivable'].reload()
    >>> accounts['receivable'].balance
    Decimal('0.00')
    >>> receivable_bis.reload()
    >>> receivable_bis.balance
    Decimal('0.00')
