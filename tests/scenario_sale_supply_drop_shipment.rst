==================================
Sale Supply Drop Shipment Scenario
==================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'sale_supply_drop_shipment',
    ...         'sale',
    ...         'purchase',
    ...         ])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create sale user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

Create purchase user::

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_request_group, = Group.find(
    ...     [('name', '=', 'Purchase Request')])
    >>> purchase_user.groups.append(purchase_request_group)
    >>> purchase_user.save()

Create stock user::

    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_force_group, = Group.find([
    ...     ('name', '=', 'Stock Force Assignment'),
    ...     ])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.groups.append(stock_force_group)
    >>> stock_user.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
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
    >>> template.supply_on_sale = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('4')
    >>> product.save()
    >>> product_supplier = ProductSupplier()
    >>> product_supplier.template = template
    >>> product_supplier.party = supplier
    >>> product_supplier.drop_shipment = True
    >>> product_supplier.lead_time = datetime.timedelta(0)
    >>> product_supplier.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale 250 products::

    >>> set_user(sale_user)
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

    >>> set_user(purchase_user)
    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> purchase, = Purchase.find()
    >>> purchase.customer == customer
    True
    >>> purchase.delivery_address == sale.shipment_address
    True
    >>> purchase.payment_term = payment_term
    >>> purchase_line, = purchase.lines
    >>> purchase_line.unit_price = Decimal('3.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

    >>> set_user(sale_user)
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> shipment, = sale.drop_shipments

Receiving only 100 products::

    >>> set_user(stock_user)
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
    Decimal('3.0000')
    >>> set_user(sale_user)
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> shipment, = sale.drop_shipments

    >>> set_user(stock_user)
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> set_user(sale_user)
    >>> sale.reload()
    >>> sale.shipments
    []

The purchase is now waiting for his new drop shipment::

    >>> set_user(purchase_user)
    >>> purchase.reload()
    >>> purchase.shipment_state
    'waiting'
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

    >>> set_user(stock_user)
    >>> shipment.click('cancel')

    >>> set_user(purchase_user)
    >>> purchase.reload()
    >>> purchase.shipment_state
    'exception'
    >>> handle_exception = Wizard('purchase.handle.shipment.exception',
    ...     [purchase])
    >>> _ = handle_exception.form.recreate_moves.pop()
    >>> handle_exception.execute('handle')
    >>> purchase.reload()
    >>> purchase.shipment_state
    'received'

    >>> set_user(sale_user)
    >>> sale.reload()
    >>> sale.shipment_state
    'exception'

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

    >>> set_user(purchase_user)
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

    >>> handle_exception = Wizard(
    ...     'purchase.request.handle.purchase.cancellation',
    ...     [purchase_request])
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
    >>> handle_exception = Wizard(
    ...     'purchase.request.handle.purchase.cancellation',
    ...     [purchase_request])
    >>> handle_exception.execute('cancel_request')
    >>> purchase_request.state
    'cancelled'

The sale is then in exception::

    >>> set_user(sale_user)
    >>> sale.reload()
    >>> sale.shipment_state
    'exception'
    >>> handle_exception = Wizard('sale.handle.shipment.exception', [sale])
    >>> handle_exception.execute('handle')
    >>> sale.reload()
    >>> sale.shipment_state
    'waiting'

The sale just created a new outgoing shipment for the sale and we can deliver
from stock::

    >>> shipment, = sale.shipments

    >>> set_user(stock_user)
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')

    >>> set_user(sale_user)
    >>> sale.reload()
    >>> sale.shipment_state
    'sent'
