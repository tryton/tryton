========================================
Sale Supply Drop Shipment Split Scenario
========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules([
    ...         'sale_supply_drop_shipment',
    ...         'stock_split',
    ...         ],
    ...     create_company, create_chart)

    >>> Move = Model.get('stock.move')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductSupplier = Model.get('purchase.product_supplier')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> Sale = Model.get('sale.sale')
    >>> Shipment = Model.get('stock.shipment.drop')

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('10.000')
    >>> template.supply_on_sale = 'always'
    >>> template.account_category = account_category
    >>> product_supplier = template.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> product_supplier.drop_shipment = True
    >>> supplier_price = product_supplier.prices.new()
    >>> supplier_price.unit_price = Decimal('5.0000')
    >>> template.save()
    >>> product, = template.products

Sale 5 products::

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Create purchase request::

    >>> purchase_request, = PurchaseRequest.find()
    >>> create_purchase = Wizard(
    ...     'purchase.request.create_purchase', [purchase_request])
    >>> purchase, = Purchase.find()
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Split supplier move of drop shipment::

    >>> shipment, = Shipment.find()
    >>> move, = shipment.supplier_moves
    >>> split = move.click('split_wizard')
    >>> split.form.quantity = 2
    >>> split.form.count = 1
    >>> split.execute('split')

    >>> shipment.reload()
    >>> len(shipment.supplier_moves)
    2
    >>> len(shipment.customer_moves)
    2
    >>> for move in shipment.supplier_moves:
    ...     assertEqual(move.quantity, sum(m.quantity for m in move.moves_drop))

Split drop shipment::

    >>> shipment.click('draft')
    >>> split = shipment.click('split_wizard')
    >>> split.form.moves.append(Move(shipment.supplier_moves[0].id))
    >>> split.execute('split')

    >>> shipment2, = Shipment.find([('id', '!=', shipment.id)])

    >>> Shipment.click([shipment, shipment2], 'wait')

    >>> len(shipment.supplier_moves)
    1
    >>> len(shipment.customer_moves)
    1
    >>> assertEqual(
    ...     sum(m.quantity for m in shipment.supplier_moves),
    ...     sum(m.quantity for m in shipment.customer_moves))

    >>> len(shipment2.supplier_moves)
    1
    >>> len(shipment2.customer_moves)
    1
    >>> assertEqual(
    ...     sum(m.quantity for m in shipment2.supplier_moves),
    ...     sum(m.quantity for m in shipment2.customer_moves))
