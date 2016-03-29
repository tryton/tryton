====================
Sale Supply Scenario
====================

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
    ...         ('name', 'in', ('sale_supply', 'sale', 'purchase')),
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
    >>> admin_user, = User.find([('login', '=', 'admin')])

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
    >>> stock_user.groups.append(stock_group)
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
    >>> shipment, = sale.shipments
    >>> move, = shipment.outgoing_moves
    >>> move.state
    u'staging'
    >>> move, = shipment.inventory_moves
    >>> move.state
    u'staging'

Delete Purchase Request::

    >>> config.user = purchase_user.id
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0
    >>> purchase_request.delete()
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0

Create Purchase from Request::

    >>> config.user = purchase_user.id
    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0
    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [purchase_request])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> purchase, = Purchase.find()
    >>> purchase.payment_term = payment_term
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.click('process')
    >>> purchase.state
    u'processing'
    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> shipment, = sale.shipments
    >>> move, = shipment.outgoing_moves
    >>> move.state
    u'draft'
    >>> move, = shipment.inventory_moves
    >>> move.state
    u'draft'

Receive 100 products::

    >>> config.user = stock_user.id
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move, = shipment.incoming_moves.find()
    >>> shipment.incoming_moves.append(move)
    >>> move.quantity = 100
    >>> shipment.click('receive')
    >>> shipment.click('done')
    >>> shipment.state
    u'done'
    >>> config.user = sale_user.id
    >>> sale.reload()
    >>> shipment, = sale.shipments
    >>> move, = [x for x in shipment.inventory_moves
    ...     if x.state == 'assigned']
    >>> move.quantity
    100.0
    >>> move, = [x for x in shipment.inventory_moves
    ...     if x.state == 'draft']
    >>> move.quantity
    150.0

Switching from not supplying on sale to supplying on sale for product should
not create a new purchase request::

    >>> config.user = admin_user.id
    >>> changing_product = Product()
    >>> changing_template = ProductTemplate()
    >>> changing_template.name = 'product'
    >>> changing_template.default_uom = unit
    >>> changing_template.type = 'goods'
    >>> changing_template.purchasable = True
    >>> changing_template.salable = True
    >>> changing_template.list_price = Decimal('10')
    >>> changing_template.cost_price = Decimal('5')
    >>> changing_template.account_expense = expense
    >>> changing_template.account_revenue = revenue
    >>> changing_template.supply_on_sale = False
    >>> changing_template.save()
    >>> changing_product.template = changing_template
    >>> changing_product.save()

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = changing_product
    >>> sale_line.quantity = 100
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    u'processing'
    >>> shipment, = sale.shipments
    >>> config.user = stock_user.id
    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory.save()
    >>> inventory_line = inventory.lines.new()
    >>> inventory_line.product = changing_product
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.save()
    >>> inventory.click('confirm')
    >>> inventory.state
    u'done'
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pack')

    >>> config.user = admin_user.id
    >>> changing_template.supply_on_sale = True
    >>> changing_template.save()

    >>> config.user = stock_user.id
    >>> shipment.click('done')
    >>> len(PurchaseRequest.find([('product', '=', changing_product.id)]))
    0
