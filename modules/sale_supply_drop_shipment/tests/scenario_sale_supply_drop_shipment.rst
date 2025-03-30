==================================
Sale Supply Drop Shipment Scenario
==================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     create_payment_term, set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'sale_supply_drop_shipment',
    ...         'sale',
    ...         'purchase',
    ...         ],
    ...     create_company, create_chart)

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.supply_on_sale = 'always'
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('4')
    >>> product.save()
    >>> product_supplier = ProductSupplier()
    >>> product_supplier.template = template
    >>> product_supplier.party = supplier
    >>> product_supplier.drop_shipment = True
    >>> product_supplier.lead_time = dt.timedelta(0)
    >>> product_supplier.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale 250 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 250
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.shipments
    []
    >>> sale.drop_shipments
    []

Create Purchase from Request::

    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> purchase, = Purchase.find()
    >>> assertEqual(purchase.customer, customer)
    >>> assertEqual(purchase.delivery_address, sale.shipment_address)
    >>> purchase.payment_term = payment_term
    >>> purchase_line, = purchase.lines
    >>> purchase_line.unit_price = Decimal('3.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

    >>> sale.reload()
    >>> sale.shipments
    []
    >>> shipment, = sale.drop_shipments

Receiving only 100 products::

    >>> move, = shipment.supplier_moves
    >>> move.quantity = 100
    >>> move.unit_price
    Decimal('3.0000')
    >>> move.cost_price
    Decimal('3.0000')
    >>> shipment.click('ship')
    >>> move, = shipment.customer_moves
    >>> move.unit_price
    Decimal('10.0000')
    >>> move.cost_price
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> len(sale.drop_shipments)
    2
    >>> shipment, = [s for s in sale.drop_shipments
    ...     if s.state == 'shipped']

    >>> shipment.click('do')
    >>> shipment.state
    'done'
    >>> move, = shipment.customer_moves
    >>> move.cost_price
    Decimal('3.0000')
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> len(sale.drop_shipments)
    2

The purchase is now waiting for his new drop shipment::

    >>> purchase.reload()
    >>> purchase.shipment_state
    'partially shipped'
    >>> len(purchase.drop_shipments)
    2
    >>> shipment, = [s for s in purchase.drop_shipments
    ...     if s.state == 'waiting']
    >>> move, = shipment.customer_moves
    >>> move.quantity
    150.0
    >>> move, = shipment.supplier_moves
    >>> move.quantity
    150.0

Let's cancel the shipment and handle the issue on the purchase.
As a consequence the sale order is now in exception::

    >>> shipment.click('cancel')

    >>> purchase.reload()
    >>> purchase.shipment_state
    'exception'
    >>> handle_exception = purchase.click('handle_shipment_exception')
    >>> handle_exception.form.ignore_moves.extend(
    ...     handle_exception.form.ignore_moves.find())
    >>> handle_exception.execute('handle')
    >>> purchase.reload()
    >>> purchase.shipment_state
    'received'

    >>> sale.reload()
    >>> sale.shipment_state
    'exception'

Receive purchase invoice at different price::

    >>> invoice, = purchase.invoices
    >>> invoice_line, = invoice.lines
    >>> invoice_line.unit_price = Decimal('4.0000')
    >>> invoice.invoice_date = today
    >>> invoice.click('post')


    >>> recompute = Wizard('product.recompute_cost_price', [product])
    >>> recompute.execute('recompute')

    >>> shipment, = [s for s in purchase.drop_shipments
    ...     if s.state == 'done']
    >>> move, = shipment.supplier_moves
    >>> move.cost_price
    Decimal('4.0000')
    >>> move, = shipment.customer_moves
    >>> move.cost_price
    Decimal('4.0000')

Cancelling the workflow on the purchase step::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 125
    >>> sale.save()
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> sale.shipments
    []
    >>> sale.drop_shipments
    []

    >>> purchase_request, = PurchaseRequest.find([('purchase_line', '=', None)])
    >>> purchase_request.quantity
    125.0
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> purchase.click('cancel')
    >>> purchase_request.state
    'exception'

Let's reset the purchase request and create a new purchase::

    >>> handle_exception = purchase_request.click(
    ...     'handle_purchase_cancellation_exception')
    >>> handle_exception.execute('reset')
    >>> purchase_request.state
    'draft'

    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> purchase_request.state
    'purchased'

Let's cancel it again and cancel the request in order to manage the process on
the sale::

    >>> purchase.click('cancel')
    >>> purchase_request.reload()
    >>> purchase_request.state
    'exception'
    >>> handle_exception = purchase_request.click(
    ...     'handle_purchase_cancellation_exception')
    >>> handle_exception.execute('cancel_request')
    >>> purchase_request.state
    'cancelled'

The sale is then in exception::

    >>> sale.reload()
    >>> sale.shipment_state
    'exception'
    >>> handle_exception = sale.click('handle_shipment_exception')
    >>> handle_exception.form.recreate_moves.extend(
    ...     handle_exception.form.recreate_moves.find())
    >>> handle_exception.execute('handle')
    >>> sale.reload()
    >>> sale.shipment_state
    'waiting'

The sale just created a new outgoing shipment for the sale and we can deliver
from stock::

    >>> shipment, = sale.shipments

    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')

    >>> sale.reload()
    >>> sale.shipment_state
    'sent'
