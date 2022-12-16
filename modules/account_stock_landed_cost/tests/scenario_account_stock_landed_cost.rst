=========================
Account Stock Landed Cost
=========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules('account_stock_landed_cost')

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
    >>> payable = accounts['payable']
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']
    >>> account_tax = accounts['tax']

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()
    >>> category = ProductCategory(name="Category")
    >>> category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'average'
    >>> template.account_category = account_category
    >>> template.categories.append(ProductCategory(category.id))
    >>> product, = template.products
    >>> product.cost_price = Decimal('80')
    >>> template.save()
    >>> product, = template.products
    >>> template2, = template.duplicate(default={'categories': None})
    >>> product2, = template2.products

    >>> template = ProductTemplate()
    >>> template.name = 'Landed Cost'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.landed_cost = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> product_landed_cost, = template.products
    >>> product_landed_cost.cost_price = Decimal('10')
    >>> template.save()
    >>> product_landed_cost, = template.products

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> input_loc, = Location.find([('code', '=', 'IN')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create payment term::

    >>> PaymentTerm = Model.get('account.invoice.payment_term')
    >>> payment_term = PaymentTerm(name='Term')
    >>> line = payment_term.lines.new(type='remainder')
    >>> payment_term.save()

Receive 10 unit of the product @ 100::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment = ShipmentIn()
    >>> shipment.planned_date = today
    >>> shipment.supplier = supplier
    >>> shipment.warehouse = warehouse_loc
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('100')

    >>> move = shipment.incoming_moves.new()
    >>> move.product = product2
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('10')

    >>> move_empty = shipment.incoming_moves.new()
    >>> move_empty.product = product
    >>> move_empty.quantity = 0
    >>> move_empty.from_location = supplier_loc
    >>> move_empty.to_location = input_loc
    >>> move_empty.unit_price = Decimal('100')

    >>> shipment.click('receive')
    >>> sorted([m.unit_price for m in shipment.incoming_moves if m.quantity])
    [Decimal('10'), Decimal('100')]

Invoice landed cost::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.type = 'in'
    >>> invoice.party = supplier
    >>> invoice.payment_term = payment_term
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product_landed_cost
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('10')
    >>> invoice.click('post')

Add landed cost::

    >>> LandedCost = Model.get('account.landed_cost')
    >>> landed_cost = LandedCost()
    >>> shipment, = landed_cost.shipments.find([])
    >>> landed_cost.shipments.append(shipment)
    >>> invoice_line, = landed_cost.invoice_lines.find([])
    >>> landed_cost.invoice_lines.append(invoice_line)
    >>> landed_cost.allocation_method = 'value'
    >>> landed_cost.categories.append(ProductCategory(category.id))
    >>> landed_cost.products.append(Product(product.id))
    >>> landed_cost.save()
    >>> landed_cost.state
    'draft'
    >>> landed_cost.click('post')
    >>> landed_cost.state
    'posted'
    >>> bool(landed_cost.posted_date)
    True

Check move unit price is 101::

    >>> shipment.reload()
    >>> sorted([m.unit_price for m in shipment.incoming_moves if m.quantity])
    [Decimal('10'), Decimal('101.0000')]

Landed cost is cleared when duplicated invoice::

    >>> copy_invoice = invoice.duplicate()
    >>> landed_cost.reload()
    >>> len(landed_cost.invoice_lines)
    1

Cancel landed cost reset unit price::

    >>> landed_cost.click('cancel')
    >>> landed_cost.state
    'cancelled'
    >>> landed_cost.posted_date

    >>> shipment.reload()
    >>> sorted([m.unit_price for m in shipment.incoming_moves if m.quantity])
    [Decimal('10'), Decimal('100.0000')]
