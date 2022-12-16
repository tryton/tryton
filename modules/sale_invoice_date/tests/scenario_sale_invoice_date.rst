==========================
Sale Invoice Date Scenario
==========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from dateutil.relativedelta import relativedelta

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('sale_invoice_date')

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> InvoiceTerm = Model.get('sale.invoice.term')
    >>> Sale = Model.get('sale.sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

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
    >>> sale.invoice_term == invoice_term
    True
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check invoice date::

    >>> invoice, = sale.invoices
    >>> invoice.invoice_date == today + relativedelta(day=31)
    True
