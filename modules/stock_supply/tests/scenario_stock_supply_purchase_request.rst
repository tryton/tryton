=========================
Purchase Request Scenario
=========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('stock_supply', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Configure supply period::

    >>> PurchaseConfig = Model.get('purchase.configuration')
    >>> purchase_config = PurchaseConfig(1)
    >>> purchase_config.supply_period = dt.timedelta(days=30)
    >>> purchase_config.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Define a product supplier::

    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> product_supplier = ProductSupplier(template=template)
    >>> product_supplier.party = supplier
    >>> product_supplier.lead_time = dt.timedelta(days=1)
    >>> product_supplier.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create needs for missing product::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = today
    >>> shipment_out.effective_date = today
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('1')
    >>> move.currency = get_currency()
    >>> shipment_out.click('wait')

    >>> shipment_out, = shipment_out.duplicate(
    ...     default={'planned_date': today + dt.timedelta(days=10)})
    >>> shipment_out.click('wait')

There is no purchase request::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> PurchaseRequest.find([])
    []

Create the purchase request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a draft purchase request::

    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> assertEqual(pr.product, product)
    >>> pr.quantity
    2.0

Create an order point with negative minimal quantity::

    >>> OrderPoint = Model.get('stock.order_point')
    >>> order_point = OrderPoint()
    >>> order_point.type = 'purchase'
    >>> order_point.product = product
    >>> order_point.location = warehouse_loc
    >>> order_point.min_quantity = -2
    >>> order_point.target_quantity = 10
    >>> order_point.save()

Create purchase request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is no more purchase request::

    >>> PurchaseRequest.find([])
    []

Set a positive minimal quantity on order point create purchase request::

    >>> order_point.min_quantity = 5
    >>> order_point.save()
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a draft purchase request::

    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> assertEqual(pr.product, product)
    >>> pr.quantity
    12.0

Using zero as minimal quantity on order point also creates purchase request::

    >>> order_point.min_quantity = 0
    >>> order_point.save()
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a draft purchase request::

    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> assertEqual(pr.product, product)
    >>> pr.quantity
    12.0

Re-run with purchased request::

    >>> create_purchase = Wizard('purchase.request.create_purchase', [pr])
    >>> pr.state
    'purchased'

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

    >>> len(PurchaseRequest.find([('state', '=', 'draft')]))
    0
