=========================
Account Stock Landed Cost
=========================

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
    ...     set_fiscalyear_invoice_sequences
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install account_stock_landed_cost Module::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([('name', '=', 'account_stock_landed_cost')])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

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

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price = Decimal('80')
    >>> template.cost_price_method = 'average'
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product.template = template
    >>> product.save()

    >>> product_landed_cost = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Landed Cost'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.landed_cost = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('10')
    >>> template.account_expense = expense
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product_landed_cost.template = template
    >>> product_landed_cost.save()

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
    >>> shipment.click('receive')
    >>> move, = shipment.incoming_moves
    >>> move.unit_price
    Decimal('100')

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
    >>> landed_cost.save()
    >>> landed_cost.state
    u'draft'
    >>> landed_cost.click('post')
    >>> landed_cost.state
    u'posted'

Check move unit price is 101::

    >>> move.reload()
    >>> move.unit_price
    Decimal('101.0000')
