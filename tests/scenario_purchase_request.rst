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

    >>> config = activate_modules(['purchase_request', 'stock_supply'])

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
    >>> stock_group_admin, = Group.find([('name', '=', 'Stock Administration')])
    >>> stock_user.groups.extend([stock_group, stock_group_admin])
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
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
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

    >>> set_user(purchase_user)
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> PurchaseRequest.find([])
    []

Create the purchase request::

    >>> set_user(stock_user)
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a draft purchase request::

    >>> set_user(purchase_user)
    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> pr.product == product
    True
    >>> pr.quantity
    1.0

Create the purchase then cancel it::

    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [pr])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> pr.state
    'purchased'

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase, = Purchase.find()
    >>> purchase.click('cancel')
    >>> pr.reload()
    >>> pr.state
    'exception'

Handle the exception::

    >>> handle_exception = Wizard(
    ...     'purchase.request.handle.purchase.cancellation', [pr])
    >>> handle_exception.execute('reset')
    >>> pr.state
    'draft'

Recreate a purchase and cancel it again::

    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [pr])
    >>> pr.state
    'purchased'

    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> purchase.click('cancel')
    >>> pr.reload()
    >>> pr.state
    'exception'

Handle again the exception::

    >>> handle_exception = Wizard(
    ...     'purchase.request.handle.purchase.cancellation', [pr])
    >>> handle_exception.execute('cancel_request')
    >>> pr.state
    'cancelled'

Re-create the purchase request::

    >>> set_user(stock_user)
    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

Create a second purchase request manually::

    >>> set_user(1)  # admin
    >>> pr_id, = PurchaseRequest.create([{
    ...             'product': product.id,
    ...             'quantity': 1,
    ...             'uom': unit,
    ...             'warehouse': warehouse_loc.id,
    ...             'origin': 'stock.order_point,-1',
    ...             'company': company.id,
    ...             }], config.context)
    >>> pr = PurchaseRequest(pr_id)

There is now 2 draft purchase requests::

    >>> set_user(purchase_user)
    >>> prs = PurchaseRequest.find([('state', '=', 'draft')])
    >>> len(prs)
    2

Create the purchase with a unique line::

    >>> create_purchase = Wizard('purchase.request.create_purchase', prs)
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> pr.state
    'purchased'

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> len(purchase.lines)
    1
    >>> line, = purchase.lines
    >>> line.product == product
    True
    >>> line.quantity
    2.0
    >>> line.unit == unit
    True

Create a purchase request without product::

    >>> set_user(1)  # admin
    >>> pr_id, = PurchaseRequest.create([{
    ...             'description': "Custom product",
    ...             'quantity': 1,
    ...             'origin': 'stock.order_point,-1',
    ...             'company': company.id,
    ...             }], config.context)
    >>> pr = PurchaseRequest(pr_id)
    >>> pr.save()

Create the purchase without product::

    >>> create_purchase = Wizard('purchase.request.create_purchase', [pr])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> pr.state
    'purchased'

    >>> pr.purchase_line.product
    >>> pr.purchase_line.description
    'Custom product'
    >>> pr.purchase_line.quantity
    1.0
    >>> pr.purchase_line.unit
    >>> pr.purchase_line.unit_price
    Decimal('0.0000')

It's not possible to delete a purchase linked to a purchase_request::

    >>> pr.purchase_line.purchase.delete()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    AccessError: ...
