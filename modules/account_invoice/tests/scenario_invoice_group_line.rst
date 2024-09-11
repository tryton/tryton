================
Invoice Scenario
================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
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
    >>> invoice.amount_to_pay
    Decimal('10.00')

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
    >>> supplier_invoice.amount_to_pay
    Decimal('5.00')

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
    >>> invoice.amount_to_pay
    Decimal('0')
    >>> supplier_invoice.reload()
    >>> supplier_invoice.state
    'posted'
    >>> supplier_invoice.amount_to_pay
    Decimal('0')

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
    >>> reconcile_lines.state
    'end'

    >>> invoice.reload()
    >>> invoice.state
    'paid'
    >>> invoice.amount_to_pay
    Decimal('0')
    >>> supplier_invoice.reload()
    >>> supplier_invoice.state
    'paid'
    >>> supplier_invoice.amount_to_pay
    Decimal('0')

Remove the created reconciliation::

    >>> Reconciliation = Model.get('account.move.reconciliation')
    >>> reconciliation, = Reconciliation.find([('lines', '=', lines[0].id)])
    >>> Reconciliation.delete([reconciliation])

    >>> invoice.reload()
    >>> invoice.state
    'posted'
    >>> invoice.amount_to_pay
    Decimal('0')
    >>> supplier_invoice.reload()
    >>> supplier_invoice.state
    'posted'
    >>> supplier_invoice.amount_to_pay
    Decimal('0')
