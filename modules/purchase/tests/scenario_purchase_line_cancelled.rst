================================
Purchase Line Cancelled Scenario
================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('purchase', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Purchase = Model.get('purchase.purchase')

Get accounts::

    >>> accounts = get_accounts()

Create party::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create product::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.save()

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom, = ProductUom.find([('name', '=', "Unit")])
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Purchase product::

    >>> purchase = Purchase(party=supplier)
    >>> line = purchase.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'
    >>> purchase.shipment_state
    'waiting'
    >>> purchase.invoice_state
    'pending'

Cancel stock move and invoice::

    >>> move, = purchase.moves
    >>> move.click('cancel')
    >>> move.state
    'cancelled'

    >>> invoice, = purchase.invoices
    >>> invoice.click('cancel')
    >>> invoice.state
    'cancelled'

    >>> purchase.reload()
    >>> purchase.state
    'processing'
    >>> purchase.shipment_state
    'exception'
    >>> purchase.invoice_state
    'exception'

Ignore exceptions::

    >>> invoice_handle_exception = purchase.click('handle_invoice_exception')
    >>> invoice_handle_exception.form.ignore_invoices.extend(
    ...     invoice_handle_exception.form.ignore_invoices.find())
    >>> invoice_handle_exception.execute('handle')

    >>> purchase.invoice_state
    'none'

    >>> shipment_handle_exception = purchase.click('handle_shipment_exception')
    >>> shipment_handle_exception.form.ignore_moves.extend(
    ...     shipment_handle_exception.form.ignore_moves.find())
    >>> shipment_handle_exception.execute('handle')

    >>> purchase.shipment_state
    'none'

    >>> purchase.state
    'done'
