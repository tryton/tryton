================================
Purchase Manual Invoice Scenario
================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('purchase', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Purchase = Model.get('purchase.purchase')

Get accounts::

    >>> accounts = get_accounts()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Create party::

    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Purchase with manual invoice method::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.invoice_method = 'manual'
    >>> line = purchase.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> line.unit_price = Decimal('5.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'
    >>> purchase.invoice_state
    'none'
    >>> len(purchase.invoices)
    0
    >>> bool(purchase.to_invoice)
    True
    >>> line, = purchase.lines
    >>> line.quantity_to_invoice
    10.0

Manually create an invoice::

    >>> purchase.click('manual_invoice')
    >>> purchase.state
    'processing'
    >>> purchase.invoice_state
    'pending'
    >>> bool(purchase.to_invoice)
    False
    >>> line, = purchase.lines
    >>> line.quantity_to_invoice
    0.0

Change quantity on invoice and create a new invoice::

    >>> invoice, = purchase.invoices
    >>> invoice.invoice_date = today
    >>> line, = invoice.lines
    >>> line.quantity = 5
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> purchase.reload()
    >>> len(purchase.invoices)
    1
    >>> bool(purchase.to_invoice)
    True
    >>> purchase.click('manual_invoice')
    >>> len(purchase.invoices)
    2
