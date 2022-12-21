====================
Sale Supply Scenario
====================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term

Activate modules::

    >>> config = activate_modules(['sale_supply', 'sale', 'purchase'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create sale user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> admin_user, = User.find([('login', '=', 'admin')])
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

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
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
    >>> shipment, = sale.shipments
    >>> move, = shipment.outgoing_moves
    >>> move.state
    'staging'
    >>> move, = shipment.inventory_moves
    >>> move.state
    'staging'

Delete Purchase Request::

    >>> set_user(purchase_user)
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0
    >>> purchase_request.delete()
    >>> purchase_request, = PurchaseRequest.find()
    >>> purchase_request.quantity
    250.0

Create Purchase from Request::

    >>> set_user(purchase_user)
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
    >>> purchase.state
    'processing'
    >>> set_user(sale_user)
    >>> sale.reload()
    >>> shipment, = sale.shipments
    >>> move, = shipment.outgoing_moves
    >>> move.state
    'draft'
    >>> move, = shipment.inventory_moves
    >>> move.state
    'draft'

Receive 100 products::

    >>> set_user(stock_user)
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Move = Model.get('stock.move')
    >>> shipment = ShipmentIn(supplier=supplier)
    >>> move, = shipment.incoming_moves.find()
    >>> shipment.incoming_moves.append(move)
    >>> move.quantity = 100
    >>> shipment.click('receive')
    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> set_user(sale_user)
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

    >>> set_user(admin_user)

    >>> changing_template = ProductTemplate()
    >>> changing_template.name = 'product'
    >>> changing_template.default_uom = unit
    >>> changing_template.type = 'goods'
    >>> changing_template.purchasable = True
    >>> changing_template.salable = True
    >>> changing_template.list_price = Decimal('10')
    >>> changing_template.account_category = account_category
    >>> changing_template.supply_on_sale = None
    >>> changing_template.save()
    >>> changing_product, = changing_template.products

    >>> set_user(sale_user)
    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = changing_product
    >>> sale_line.quantity = 100
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> shipment, = sale.shipments
    >>> set_user(stock_user)
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
    'done'
    >>> shipment.click('assign_try')
    >>> shipment.click('pick')
    >>> shipment.click('pack')

    >>> set_user(admin_user)
    >>> changing_template.supply_on_sale = 'always'
    >>> changing_template.save()

    >>> set_user(stock_user)
    >>> shipment.click('done')
    >>> set_user(purchase_user)
    >>> len(PurchaseRequest.find([('product', '=', changing_product.id)]))
    0
