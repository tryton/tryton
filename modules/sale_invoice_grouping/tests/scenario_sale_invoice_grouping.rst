==============================
Sale Invoice Grouping Scenario
==============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     create_payment_term, set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     'sale_invoice_grouping', create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> customer_grouped = Party(name='Customer Grouped',
    ...     sale_invoice_grouping_method='standard')
    >>> customer_grouped.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale some products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Make another sale::

    >>> sale, = Sale.duplicate([sale])
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check the invoices::

    >>> Invoice = Model.get('account.invoice')
    >>> invoices = Invoice.find([('party', '=', customer.id)])
    >>> len(invoices)
    2
    >>> invoice = invoices[0]
    >>> invoice.type
    'out'
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Now we'll use the same scenario with the grouped customer::

    >>> sale = Sale()
    >>> sale.party = customer_grouped
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Make another sale::

    >>> sale = Sale()
    >>> sale.party = customer_grouped
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check the invoices::

    >>> invoices = Invoice.find([
    ...     ('party', '=', customer_grouped.id),
    ...     ('state', '=', 'draft'),
    ...     ])
    >>> len(invoices)
    1
    >>> invoice, = invoices
    >>> len(invoice.lines)
    2
    >>> invoice.lines[0].quantity
    1.0
    >>> invoice.lines[1].quantity
    2.0
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Create a manual invoice::

    >>> manual_invoice = Invoice()
    >>> manual_invoice.party = customer_grouped
    >>> manual_invoice.payment_term = payment_term
    >>> manual_invoice.save()

Check that a new sale won't be grouped with the manual invoice::

    >>> sale = Sale()
    >>> sale.party = customer_grouped
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check the invoices::

    >>> invoices = Invoice.find([
    ...     ('party', '=', customer_grouped.id),
    ...     ('state', '=', 'draft'),
    ...     ])
    >>> len(invoices)
    2
