=======================================
Sale Invoice Grouping Multiple Scenario
=======================================

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

    >>> config = activate_modules(
    ...     'sale_invoice_grouping', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sale = Model.get('sale.sale')
    >>> Invoice = Model.get('account.invoice')

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> customer = Party(
    ...     name="Customer",
    ...     sale_invoice_grouping_method='standard')
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
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Sale some products::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.click('quote')
    >>> sales = [sale]

Make another sale::

    >>> sale, = Sale.duplicate([sale])
    >>> sale.click('quote')
    >>> sales.append(sale)

Confirm both sales::

    >>> Sale.click(sales, 'confirm')
    >>> state, = set(s.state for s in sales)
    >>> state
    'processing'

Check the invoices::

    >>> invoice, = Invoice.find([('party', '=', customer.id)])

Deleting the invoice keeps same grouping::

    >>> invoice.delete()
    >>> invoice, = Invoice.find([('party', '=', customer.id)])
