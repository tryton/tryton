==================================
Sale Supply Drop Shipment Scenario
==================================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install sale_supply, sale, purchase::

    >>> Module = Model.get('ir.module')
    >>> modules = Module.find([
    ...         ('name', 'in', ('sale_supply_drop_shipment', 'sale',
    ...             'purchase')),
    ...         ])
    >>> for module in modules:
    ...     module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create sale user::

    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_user.main_company = company
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

Create purchase user::

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_user.main_company = company
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
    >>> stock_user.main_company = company
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

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.supply_on_sale = True
    >>> template.save()
    >>> product.template = template
    >>> product.save()
    >>> product_supplier = ProductSupplier()
    >>> product_supplier.product = template
    >>> product_supplier.party = supplier
    >>> product_supplier.drop_shipment = True
    >>> product_supplier.lead_time = datetime.timedelta(0)
    >>> product_supplier.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale 250 products::

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 250
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    u'processing'
    >>> sale.shipments
    []
    >>> sale.drop_shipments
    []

Create Purchase from Request::

    >>> config.user = purchase_user.id
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
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> purchase.state
    u'processing'

    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> shipment, = sale.drop_shipments

Receiving only 100 products::

    >>> config.user = stock_user.id
    >>> move, = shipment.supplier_moves
    >>> move.quantity = 100
    >>> shipment.click('ship')
    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> sale.shipments
    []
    >>> shipment, = sale.drop_shipments

    >>> config.user = stock_user.id
    >>> shipment.click('done')
    >>> shipment.state
    u'done'
    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> sale.shipments
    []

The purchase is now waiting for his new drop shipment::

    >>> config.user = purchase_user.id
    >>> purchase.reload()
    >>> purchase.shipment_state
    u'waiting'
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

    >>> config.user = stock_user.id
    >>> shipment.click('cancel')

    >>> config.user = purchase_user.id
    >>> purchase.reload()
    >>> purchase.shipment_state
    u'exception'
    >>> handle_exception = Wizard('purchase.handle.shipment.exception',
    ...     [purchase])
    >>> _ = handle_exception.form.recreate_moves.pop()
    >>> handle_exception.execute('handle')
    >>> purchase.reload()
    >>> purchase.shipment_state
    u'received'

    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> sale.shipment_state
    u'exception'

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
    >>> sale.click('process')
    >>> sale.state
    u'processing'
    >>> sale.shipments
    []
    >>> sale.drop_shipments
    []

    >>> config.user = purchase_user.id
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
    'cancel'

The sale is then in exception::

    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> sale.shipment_state
    u'exception'
    >>> handle_exception = Wizard('sale.handle.shipment.exception', [sale])
    >>> handle_exception.execute('handle')
    >>> sale.reload()
    >>> sale.shipment_state
    u'waiting'

The sale just created a new outgoing shipment for the sale and we can deliver
from stock::

    >>> shipment, = sale.shipments

    >>> config.user = stock_user.id
    >>> shipment.click('assign_force')
    >>> shipment.click('pack')
    >>> shipment.click('done')

    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> sale.shipment_state
    u'sent'
