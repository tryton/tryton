================
Invoice Scenario
================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Activate modules::

    >>> config = activate_modules('account_invoice')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> receivable = accounts['receivable']
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_cash = accounts['cash']

    >>> Journal = Model.get('account.journal')
    >>> journal_cash, = Journal.find([
    ...         ('code', '=', 'CASH'),
    ...         ])

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Post customer invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.account = revenue
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(10)
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Post supplier invoice::

    >>> supplier_invoice = Invoice(type='in')
    >>> supplier_invoice.party = party
    >>> supplier_invoice.invoice_date = period.start_date
    >>> line = supplier_invoice.lines.new()
    >>> line.account = expense
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(5)
    >>> supplier_invoice.click('post')
    >>> supplier_invoice.state
    'posted'

Group lines::

    >>> Line = Model.get('account.move.line')
    >>> lines = Line.find([('account', 'in', [payable.id, receivable.id])])
    >>> len(lines)
    2
    >>> group = Wizard('account.move.line.group', lines)
    >>> group.form.journal = journal_cash
    >>> group.execute('group')

    >>> invoice.reload()
    >>> invoice.state
    'posted'
    >>> supplier_invoice.reload()
    >>> supplier_invoice.state
    'posted'

Receive remaining line::

    >>> Move = Model.get('account.move')
    >>> move = Move()
    >>> move.journal = journal_cash
    >>> move.date = period.start_date
    >>> line = move.lines.new()
    >>> line.account = account_cash
    >>> line.debit = Decimal(5)
    >>> line = move.lines.new()
    >>> line.account = receivable
    >>> line.party = party
    >>> line.credit = Decimal(5)
    >>> move.click('post')

    >>> lines = Line.find([
    ...         ('account', '=', receivable.id),
    ...         ('reconciliation', '=', None),
    ...         ])
    >>> reconcile_lines = Wizard('account.move.reconcile_lines', lines)
    >>> reconcile_lines.state == 'end'
    True

    >>> invoice.reload()
    >>> invoice.state
    'paid'
    >>> supplier_invoice.reload()
    >>> supplier_invoice.state
    'paid'
