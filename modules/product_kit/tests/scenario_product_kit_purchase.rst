=============================
Purchase Product Kit Scenario
=============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> today = dt.date.today()

Activate product_kit, purchase and account_invoice::

    >>> config = activate_modules(
    ...     ['product_kit', 'purchase', 'account_invoice',
    ...         'account_invoice_stock'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create party::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> meter, = ProductUom.find([('name', '=', "Meter")])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = "Product 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('5')
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product 2"
    >>> template.default_uom = meter
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('8')
    >>> product2.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product 3"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('30')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product3, = template.products
    >>> product3.cost_price = Decimal('10')
    >>> product3.save()

    >>> template = ProductTemplate()
    >>> template.name = "Service"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('30')
    >>> template.account_category = account_category
    >>> template.save()
    >>> service, = template.products
    >>> service.cost_price = Decimal('20')
    >>> service.save()

Create composed product::

    >>> template = ProductTemplate()
    >>> template.name = "Composed Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> composed_product, = template.products
    >>> composed_product.cost_price = Decimal('5')

    >>> component = composed_product.components.new()
    >>> component.product = product1
    >>> component.quantity = 1
    >>> component = composed_product.components.new()
    >>> component.product = service
    >>> component.quantity = 2
    >>> component.fixed = True
    >>> composed_product.save()

Create kit product::

    >>> template = ProductTemplate()
    >>> template.name = "Kit"
    >>> template.default_uom = unit
    >>> template.type = 'kit'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> template.save()
    >>> kit, = template.products

    >>> component = kit.components.new()
    >>> component.product = product2
    >>> component.quantity = 2
    >>> component = kit.components.new()
    >>> component.product = product3
    >>> component.quantity = 1
    >>> component.fixed = True
    >>> kit.save()

Purchase composed and kit products::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.invoice_method = 'shipment'
    >>> line = purchase.lines.new()
    >>> line.product = composed_product
    >>> line.quantity = 1
    >>> line = purchase.lines.new()
    >>> line.product = kit
    >>> line.quantity = 2
    >>> purchase.click('quote')
    >>> len(purchase.lines)
    4
    >>> [l.quantity for l in purchase.lines]
    [1.0, 1.0, 2.0, 2.0]
    >>> line_kit, = [l for l in purchase.lines if l.product == kit]
    >>> [c.quantity for c in line_kit.components]
    [4.0, 1.0]

Reset to draft remove components::

    >>> purchase.click('draft')
    >>> line_kit, = [l for l in purchase.lines if l.product == kit]
    >>> bool(line_kit.components)
    False
    >>> purchase.click('quote')

Process purchase::

    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'
    >>> len(purchase.shipments), len(purchase.invoices)
    (0, 1)

Check invoice::

    >>> invoice, = purchase.invoices
    >>> line, = invoice.lines
    >>> line.product == service
    True

Check stock moves::

    >>> len(purchase.moves)
    4
    >>> product2quantity = {
    ...     m.product: m.quantity for m in purchase.moves}
    >>> product2quantity[composed_product]
    1.0
    >>> product2quantity[product1]
    1.0
    >>> product2quantity[product2]
    4.0
    >>> product2quantity[product3]
    1.0

Receive partial shipment::

    >>> Move = Model.get('stock.move')
    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> for move in purchase.moves:
    ...     incoming_move = Move(move.id)
    ...     shipment.incoming_moves.append(incoming_move)
    >>> shipment.save()

    >>> product2move = {
    ...     m.product: m for m in shipment.incoming_moves}
    >>> product2move[product2].quantity = 2.0
    >>> shipment.click('receive')
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check new invoice::

    >>> purchase.reload()
    >>> _, invoice = purchase.invoices
    >>> len(invoice.lines)
    3
    >>> product2quantity = {l.product: l.quantity for l in invoice.lines}
    >>> product2quantity[composed_product]
    1.0
    >>> product2quantity[product1]
    1.0
    >>> product2quantity[kit]
    1.0

Post invoice::

    >>> invoice.invoice_date = today
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check unit price of moves::

    >>> shipment.reload()
    >>> invoice.reload()
    >>> sorted([m.unit_price for m in shipment.incoming_moves])
    [Decimal('5.0000'), Decimal('5.0000'), Decimal('7.0909'), Decimal('18.9091')]

Check backorder moves::

    >>> len(purchase.moves)
    5
    >>> backorder, = [m for m in purchase.moves if m.state == 'draft']

Cancel backorder::

    >>> backorder.click('cancel')
    >>> backorder.state
    'cancelled'
    >>> purchase.reload()
    >>> purchase.shipment_state
    'exception'

Handle shipment exception::

    >>> shipment_exception = Wizard('purchase.handle.shipment.exception', [purchase])
    >>> shipment_exception.execute('handle')

    >>> len(purchase.moves)
    6
