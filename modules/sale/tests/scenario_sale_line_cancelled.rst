============================
Sale Line Cancelled Scenario
============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale')

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Create company::

    >>> _ = create_company()

Create chart of accounts::

    >>> _ = create_chart()
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
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'waiting'
    >>> sale.invoice_state
    'pending'

Cancel shipment and invoice::

    >>> shipment, = sale.shipments
    >>> shipment.click('cancel')
    >>> shipment.state
    'cancelled'

    >>> invoice, = sale.invoices
    >>> invoice.click('cancel')
    >>> invoice.state
    'cancelled'

    >>> sale.reload()
    >>> sale.state
    'processing'
    >>> sale.shipment_state
    'exception'
    >>> sale.invoice_state
    'exception'

Ignore exceptions::

    >>> invoice_handle_exception = sale.click('handle_invoice_exception')
    >>> invoice_handle_exception.form.recreate_invoices.clear()
    >>> invoice_handle_exception.execute('handle')

    >>> sale.invoice_state
    'none'

    >>> shipment_handle_exception = sale.click('handle_shipment_exception')
    >>> shipment_handle_exception.form.recreate_moves.clear()
    >>> shipment_handle_exception.execute('handle')

    >>> sale.shipment_state
    'none'

    >>> sale.state
    'done'
