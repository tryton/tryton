=======================================================
Carrier Percentage with Purchase Shipment Cost Scenario
=======================================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     create_payment_term, set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules([
    ...         'carrier_percentage',
    ...         'purchase_shipment_cost',
    ...         'sale_shipment_cost',
    ...         ],
    ...     create_company, create_chart)

Get company::

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()
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

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> product.save()

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('5')
    >>> carrier_template.account_category = account_category
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products
    >>> carrier_product.cost_price = Decimal('3')
    >>> carrier_product.save()

Create carrier::

    >>> Carrier = Model.get('carrier')
    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.carrier_cost_method = 'percentage'
    >>> carrier.percentage = Decimal('15')
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
    >>> move.quantity = 50
    >>> move.unit_price = Decimal('8')
    >>> move.currency = company.currency
    >>> shipment.carrier = carrier
    >>> shipment.cost_used
    Decimal('60.0000')
    >>> assertEqual(shipment.cost_currency_used, company.currency)
    >>> shipment.click('receive')
    >>> shipment.state
    'received'
    >>> move, = shipment.incoming_moves
    >>> move.unit_price
    Decimal('9.2000')

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
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> assertEqual(cost_line.product, carrier_product)
    >>> cost_line.quantity
    1.0
    >>> cost_line.amount
    Decimal('15.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> sale.untaxed_amount
    Decimal('115.00')

Send products::

    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> shipment, = sale.shipments
    >>> assertEqual(shipment.carrier, carrier)
    >>> shipment.cost_used
    Decimal('15.0000')
    >>> shipment.cost_sale_used
    Decimal('15.0000')
    >>> assertEqual(shipment.cost_sale_currency_used, company.currency)
    >>> move, = shipment.inventory_moves
    >>> move.quantity = 4
    >>> shipment.cost_used
    Decimal('12.0000')
    >>> shipment.cost_sale_used
    Decimal('12.0000')
    >>> assertEqual(shipment.cost_sale_currency_used, company.currency)
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
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('92.00')

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
    >>> assertEqual(cost_line.product, carrier_product)
    >>> cost_line.quantity
    1.0
    >>> cost_line.amount
    Decimal('9.00')
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.state
    'processing'
    >>> sale.untaxed_amount
    Decimal('69.00')

Check customer shipment::

    >>> shipment, = sale.shipments
    >>> assertEqual(shipment.carrier, carrier)

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('69.00')
