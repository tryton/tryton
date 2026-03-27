============================
Sale Manual Invoice Scenario
============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Get accounts::

    >>> accounts = get_accounts()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Create party::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.list_price = Decimal('10')
    >>> template.save()
    >>> product, = template.products

Sale with manual invoice method::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.invoice_method = 'manual'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.invoice_state
    'none'
    >>> len(sale.invoices)
    0
    >>> bool(sale.to_invoice)
    True
    >>> line, = sale.lines
    >>> line.quantity_to_invoice
    10.0

Manually create an invoice::

    >>> sale.click('manual_invoice')
    >>> sale.state
    'processing'
    >>> sale.invoice_state
    'pending'
    >>> bool(sale.to_invoice)
    False
    >>> line, = sale.lines
    >>> line.quantity_to_invoice
    0.0

Change quantity on invoice and create a new invoice::

    >>> invoice, = sale.invoices
    >>> line, = invoice.lines
    >>> line.quantity = 5
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> sale.reload()
    >>> len(sale.invoices)
    1
    >>> bool(sale.to_invoice)
    True
    >>> sale.click('manual_invoice')
    >>> len(sale.invoices)
    2
