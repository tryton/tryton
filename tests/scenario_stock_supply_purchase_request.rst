=========================
Purchase Request Scenario
=========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import (create_chart,
    ...     get_accounts)
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('stock_supply')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create stock admin user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> stock_admin_user = User()
    >>> stock_admin_user.name = 'Stock Admin'
    >>> stock_admin_user.login = 'stock_admin'
    >>> stock_admin_user.main_company = company
    >>> stock_admin_group, = Group.find([('name', '=', 'Stock Administration')])
    >>> stock_admin_user.groups.append(stock_admin_group)
    >>> stock_admin_user.save()

Create stock user::

    >>> stock_user = User()
    >>> stock_user.name = 'Stock'
    >>> stock_user.login = 'stock'
    >>> stock_user.main_company = company
    >>> stock_group, = Group.find([('name', '=', 'Stock')])
    >>> stock_user.groups.append(stock_group)
    >>> stock_user.save()

Create product user::

    >>> product_admin_user = User()
    >>> product_admin_user.name = 'Product'
    >>> product_admin_user.login = 'product'
    >>> product_admin_user.main_company = company
    >>> product_admin_group, = Group.find([
    ...         ('name', '=', 'Product Administration')
    ...         ])
    >>> product_admin_user.groups.append(product_admin_group)
    >>> product_admin_user.save()

Create purchase user::

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_user.main_company = company
    >>> purchase_groups = Group.find(['OR',
    ...     ('name', '=', "Purchase"),
    ...     ('name', '=', "Purchase Request"),
    ...     ])
    >>> purchase_user.groups.extend(purchase_groups)
    >>> purchase_user.save()


Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.save()

Create product::

    >>> set_user(product_admin_user)
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

Get stock locations::

    >>> set_user(stock_admin_user)
    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create a need for missing product::

    >>> set_user(stock_user)
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment_out = ShipmentOut()
    >>> shipment_out.planned_date = today
    >>> shipment_out.effective_date = today
    >>> shipment_out.customer = customer
    >>> shipment_out.warehouse = warehouse_loc
    >>> shipment_out.company = company
    >>> move = shipment_out.outgoing_moves.new()
    >>> move.product = product
    >>> move.uom = unit
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.company = company
    >>> move.unit_price = Decimal('1')
    >>> move.currency = company.currency
    >>> shipment_out.click('wait')

There is no purchase request::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> set_user(purchase_user)
    >>> PurchaseRequest.find([])
    []

Create the purchase request::

    >>> set_user(stock_admin_user)
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a draft purchase request::

    >>> set_user(purchase_user)
    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> pr.product == product
    True
    >>> pr.quantity
    1.0

Create an order point with negative minimal quantity::

    >>> set_user(stock_admin_user)
    >>> OrderPoint = Model.get('stock.order_point')
    >>> order_point = OrderPoint()
    >>> order_point.type = 'purchase'
    >>> order_point.product = product
    >>> order_point.warehouse_location = warehouse_loc
    >>> order_point.min_quantity = -1
    >>> order_point.target_quantity = 10
    >>> order_point.save()

Create production request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is no more production request::

    >>> set_user(purchase_user)
    >>> PurchaseRequest.find([])
    []

Set a postive minimal quantity on order point create purchase request::

    >>> set_user(stock_admin_user)
    >>> order_point.min_quantity = 5
    >>> order_point.save()
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a draft purchase request::

    >>> set_user(purchase_user)
    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> pr.product == product
    True
    >>> pr.quantity
    11.0

Using zero as minimal quantity on order point also creates purchase request::

    >>> set_user(stock_admin_user)
    >>> order_point.min_quantity = 0
    >>> order_point.save()
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a draft purchase request::

    >>> set_user(purchase_user)
    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> pr.product == product
    True
    >>> pr.quantity
    11.0

Re-run with purchased request::

    >>> create_purchase = Wizard('purchase.request.create_purchase', [pr])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> pr.state
    'purchased'

    >>> set_user(stock_admin_user)
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

    >>> set_user(purchase_user)
    >>> len(PurchaseRequest.find([('state', '=', 'draft')]))
    0
