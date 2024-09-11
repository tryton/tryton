=======================================
Sale Line Cancelled On Invoice Scenario
=======================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
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

Create party::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create product::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom, = ProductUom.find([('name', '=', "Unit")])
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10.0000')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Sale product::

    >>> sale = Sale(party=customer)
    >>> sale.shipment_method = 'invoice'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'none'
    >>> sale.invoice_state
    'pending'

Cancel invoice::

    >>> invoice, = sale.invoices
    >>> invoice.click('cancel')
    >>> invoice.state
    'cancelled'

    >>> sale.reload()
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'none'
    >>> sale.invoice_state
    'exception'

Ignore exception::

    >>> invoice_handle_exception = sale.click('handle_invoice_exception')
    >>> invoice_handle_exception.form.ignore_invoices.extend(
    ...     invoice_handle_exception.form.ignore_invoices.find())
    >>> invoice_handle_exception.execute('handle')

    >>> sale.shipment_state
    'none'

    >>> sale.state
    'done'
