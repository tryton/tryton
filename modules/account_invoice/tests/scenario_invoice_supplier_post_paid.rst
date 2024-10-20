==========================
Invoice Supplier Post Paid
==========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_invoice', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = get_accounts()
    >>> payable = accounts['payable']
    >>> expense = accounts['expense']
    >>> cash = accounts['cash']

Create party::

    >>> Party = Model.get('party.party')
    >>> party = Party(name='Party')
    >>> party.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create validated invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = party
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> line.unit_price = Decimal('20')
    >>> invoice.click('validate_invoice')
    >>> invoice.state
    'validated'

Pay invoice::

   >>> Move = Model.get('account.move')
   >>> Journal = Model.get('account.journal')
   >>> journal_cash, = Journal.find([
   ...         ('code', '=', 'CASH'),
   ...         ])
   >>> move = Move()
   >>> move.period = period
   >>> move.journal = journal_cash
   >>> move.date = period.start_date
   >>> line = move.lines.new()
   >>> line.account = payable
   >>> line.debit = Decimal('100')
   >>> line.party = party
   >>> line = move.lines.new()
   >>> line.account = cash
   >>> line.credit = Decimal('100')
   >>> move.save()

   >>> Line = Model.get('account.move.line')
   >>> lines = Line.find([('account', '=', payable.id)])
   >>> reconcile = Wizard('account.move.reconcile_lines', lines)

Check invoice::

   >>> invoice.reload()
   >>> invoice.state
   'validated'
   >>> bool(invoice.reconciled)
   True

Post invoice::

   >>> invoice.click('post')
   >>> invoice.state
   'paid'
