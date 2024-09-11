==========================
Sale Invoice Date Scenario
==========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> end_month = today + relativedelta(day=31)

Activate modules::

    >>> config = activate_modules('sale_invoice_date', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> InvoiceTerm = Model.get('sale.invoice.term')
    >>> Sale = Model.get('sale.sale')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=(today, end_month)))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create invoice term::

    >>> invoice_term = InvoiceTerm(name="End of Month")
    >>> relative_delta = invoice_term.relative_deltas.new()
    >>> relative_delta.day = 31
    >>> invoice_term.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.sale_invoice_term = invoice_term
    >>> customer.save()

Create account categories::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Make a sale::

    >>> sale = Sale(party=customer)
    >>> assertEqual(sale.invoice_term, invoice_term)
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice date::

    >>> invoice, = sale.invoices
    >>> assertEqual(invoice.invoice_date, end_month)
