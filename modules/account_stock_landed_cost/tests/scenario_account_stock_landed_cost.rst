=========================
Account Stock Landed Cost
=========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     'account_stock_landed_cost', create_company, create_chart)

Get company::

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
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
    >>> move.currency = company.currency

    >>> move = shipment.incoming_moves.new()
    >>> move.product = product2
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = input_loc
    >>> move.unit_price = Decimal('10')
    >>> move.currency = company.currency

    >>> move_empty = shipment.incoming_moves.new()
    >>> move_empty.product = product
    >>> move_empty.quantity = 0
    >>> move_empty.from_location = supplier_loc
    >>> move_empty.to_location = input_loc
    >>> move_empty.unit_price = Decimal('100')
    >>> move_empty.currency = company.currency

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

    >>> post_landed_cost = landed_cost.click('post_wizard')
    >>> post_landed_cost.form.cost
    Decimal('10.0000')
    >>> sorted([m.cost for m in post_landed_cost.form.moves])
    [Decimal('1.0000')]
    >>> post_landed_cost.execute('post')
    >>> landed_cost.state
    'posted'
    >>> bool(landed_cost.posted_date)
    True
    >>> bool(landed_cost.factors)
    True

Show landed cost::

    >>> show_landed_cost = landed_cost.click('show')
    >>> show_landed_cost.form.cost
    Decimal('10.0000')
    >>> sorted([m.cost for m in show_landed_cost.form.moves])
    [Decimal('1.0000')]

Check move unit price is 101::

    >>> shipment.reload()
    >>> sorted([m.unit_price for m in shipment.incoming_moves if m.quantity])
    [Decimal('10'), Decimal('101.0000')]

Landed cost is cleared when duplicated invoice::

    >>> copy_invoice = invoice.duplicate()
    >>> landed_cost.reload()
    >>> len(landed_cost.invoice_lines)
    1

Can not delete posted landed cost::

    >>> landed_cost.delete()
    Traceback (most recent call last):
        ...
    AccessError: ...

Cancel landed cost reset unit price::

    >>> landed_cost.click('cancel')
    >>> landed_cost.state
    'cancelled'
    >>> landed_cost.posted_date
    >>> landed_cost.factors

    >>> shipment.reload()
    >>> sorted([m.unit_price for m in shipment.incoming_moves if m.quantity])
    [Decimal('10'), Decimal('100.0000')]

Can delete cancelled landed cost::

    >>> landed_cost.delete()
