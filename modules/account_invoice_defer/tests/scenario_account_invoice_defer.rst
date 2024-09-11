==============================
Account Invoice Defer Scenario
==============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.account_invoice_defer.tests.tools import (
    ...     add_deferred_accounts)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     'account_invoice_defer', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceDeferred = Model.get('account.invoice.deferred')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductUom = Model.get('product.uom')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')
    >>> period = fiscalyear.periods[0]

Get accounts::

    >>> accounts = add_deferred_accounts(get_accounts())

Create party::

    >>> party = Party(name="Insurer")
    >>> party.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = "Insurance"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('1000')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create invoice::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = party
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('1000')
    >>> line.defer_from = period.start_date
    >>> line.defer_to = line.defer_from + dt.timedelta(days=499)
    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice_line, = invoice.lines

Check invoice deferred and run it::

    >>> deferral, = InvoiceDeferred.find([])
    >>> assertEqual(deferral.invoice_line, invoice_line)
    >>> deferral.amount
    Decimal('1000.00')
    >>> assertEqual(deferral.start_date, invoice_line.defer_from)
    >>> assertEqual(deferral.end_date, invoice_line.defer_to)
    >>> deferral.click('run')

Check moves on invoice deferred::

    >>> deferral.reload()
    >>> deferral.state
    'running'
    >>> len(deferral.moves)
    13
    >>> accounts['deferred_expense'].reload()
    >>> Decimal('268') <= accounts['deferred_expense'].balance <= Decimal('271')
    True

Define next fiscal year::

    >>> renew_fiscalyear = Wizard('account.fiscalyear.renew')
    >>> renew_fiscalyear.execute('create_')
    >>> new_fiscalyear, = renew_fiscalyear.actions[0]

Create moves::

    >>> create_moves = Wizard('account.invoice.deferred.create_moves')

Check moves on invoice deferred::

    >>> deferral.reload()
    >>> deferral.state
    'closed'
    >>> len(deferral.moves)
    18
    >>> accounts['deferred_expense'].reload()
    >>> accounts['deferred_expense'].balance
    Decimal('0.00')
