================================
Account Stock Landed Cost Weight
================================

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

    >>> config = activate_modules('account_stock_landed_cost_weight')

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

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'average'
    >>> template.account_category = account_category
    >>> template.weight_uom = kg
    >>> template.weight = 20
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('80')
    >>> template.save()
    >>> product1, = template.products

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('200')
    >>> template.cost_price_method = 'average'
    >>> template.account_category = account_category
    >>> template.weight_uom = kg
    >>> template.weight = 10
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('50')
    >>> template.save()
    >>> product2, = template.products

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

Receive 10 unit of the product1 @ 100 and 10 unit of product2 @50::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> shipment = ShipmentIn()
    >>> shipment.planned_date = today
    >>> shipment.supplier = supplier
    >>> shipment.warehouse = warehouse_loc
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product1
    >>> move.quantity = 10
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('100')
    >>> move = shipment.incoming_moves.new()
    >>> move.product = product2
    >>> move.quantity = 10
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('50')
    >>> shipment.click('receive')
    >>> sorted([m.unit_price for m in shipment.incoming_moves])
    [Decimal('50'), Decimal('100')]

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
    >>> line.unit_price = Decimal('30')
    >>> invoice.click('post')

Add landed cost::

    >>> LandedCost = Model.get('account.landed_cost')
    >>> landed_cost = LandedCost()
    >>> shipment, = landed_cost.shipments.find([])
    >>> landed_cost.shipments.append(shipment)
    >>> invoice_line, = landed_cost.invoice_lines.find([])
    >>> landed_cost.invoice_lines.append(invoice_line)
    >>> landed_cost.allocation_method = 'weight'
    >>> landed_cost.save()
    >>> landed_cost.state
    'draft'
    >>> landed_cost.click('post')
    >>> landed_cost.state
    'posted'

Check move unit price is 101::

    >>> sorted([m.unit_price for m in shipment.incoming_moves])
    [Decimal('51.0000'), Decimal('102.0000')]

Cancel landed cost reset unit price::

    >>> landed_cost.click('cancel')
    >>> landed_cost.state
    'cancelled'

    >>> shipment.reload()
    >>> sorted([m.unit_price for m in shipment.incoming_moves])
    [Decimal('50.0000'), Decimal('100.0000')]
