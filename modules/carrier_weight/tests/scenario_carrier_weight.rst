=======================
Carrier Weight Scenario
=======================

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
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'carrier_weight',
    ...         'purchase_shipment_cost',
    ...         'sale_shipment_cost',
    ...         ])

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
    >>> revenue = accounts['revenue']

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name='Supplier')
    >>> supplier.save()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> gram, = ProductUom.find([('name', '=', 'Gram')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.weight = 250
    >>> template.weight_uom = gram
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> product.save()

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.account_category = account_category
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('3')
    >>> carrier_product.save()

Create carrier::

    >>> Carrier = Model.get('carrier')
    >>> WeightPriceList = Model.get('carrier.weight_price_list')
    >>> kilogram, = ProductUom.find([('name', '=', 'Kilogram')])
    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.carrier_cost_method = 'weight'
    >>> carrier.weight_currency = company.currency
    >>> carrier.weight_uom = kilogram
    >>> for weight, price in (
    ...         (0.5, Decimal(25)),
    ...         (1, Decimal(40)),
    ...         (5, Decimal(180)),
    ...         ):
    ...     line = WeightPriceList(weight=weight, price=price)
    ...     carrier.weight_price_list.append(line)
    >>> carrier.save()

Receive a single product line::

    >>> ShipmentIn = Model.get('stock.shipment.in')
    >>> Location = Model.get('stock.location')
    >>> supplier_location, = Location.find([
    ...         ('code', '=', 'SUP'),
    ...         ])
    >>> shipment = ShipmentIn()
    >>> shipment.supplier = supplier
    >>> move = shipment.incoming_moves.new()
    >>> move.from_location = supplier_location
    >>> move.to_location = shipment.warehouse.input_location
    >>> move.product = product
    >>> move.quantity = 4
    >>> move.unit_price = Decimal('8')
    >>> shipment.carrier = carrier
    >>> shipment.cost
    Decimal('25')
    >>> shipment.cost_currency == company.currency
    True
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> move, = shipment.incoming_moves
    >>> move.unit_price
    Decimal('14.2500')

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Sale products with cost on shipment::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'shipment'
    >>> sale.shipment_cost_method = 'shipment'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale_line = sale.lines.new()
    >>> sale_line.type = 'comment'
    >>> sale_line.description = 'Comment'
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.product == carrier_product
    True
    >>> cost_line.quantity == 1
    True
    >>> cost_line.amount
    Decimal('40.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> sale.untaxed_amount
    Decimal('140.00')

Send products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> shipment.carrier == carrier
    True
    >>> shipment.cost
    Decimal('40.0000')
    >>> shipment.cost_currency == company.currency
    True
    >>> move = shipment.inventory_moves[0]
    >>> move.quantity -= 1
    >>> shipment.cost
    Decimal('25.0000')
    >>> shipment.cost_currency == company.currency
    True
    >>> shipment.state
    'waiting'
    >>> shipment.click('assign_force')
    >>> shipment.state
    'assigned'
    >>> shipment.click('pick')
    >>> shipment.state
    'picked'
    >>> shipment.click('pack')
    >>> shipment.state
    'packed'
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('105.00')

Sale products with cost on order::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale.shipment_cost_method = 'order'
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3.0
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.product == carrier_product
    True
    >>> cost_line.quantity == 1
    True
    >>> cost_line.amount
    Decimal('25.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> sale.untaxed_amount
    Decimal('85.00')

Check customer shipment::

    >>> shipment, = sale.shipments
    >>> shipment.carrier == carrier
    True

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('85.00')
