===========================================
Account Stock Shipment Cost Weight Scenario
===========================================

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
    ...     'account_stock_shipment_cost_weight', create_company, create_chart)

    >>> Invoice = Model.get('account.invoice')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> ShipmentCost = Model.get('account.shipment_cost')

Get company::

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=today))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()
    >>> carrier = Party(name="Carrier")
    >>> carrier.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('100.00')
    >>> template.account_category = account_category
    >>> template.weight_uom = kg
    >>> template.weight = 10
    >>> template.save()
    >>> product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Shipment Cost"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.shipment_cost = True
    >>> template.list_price = Decimal('4.00')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product_shipment_cost, = template.products

Get stock locations::

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Ship 20 units of the product in two shipments::

    >>> shipment1 = ShipmentOut()
    >>> shipment1.customer = customer
    >>> shipment1.cost_edit = True
    >>> shipment1.cost_used = Decimal('4.00')
    >>> shipment1.cost_currency_used = company.currency
    >>> move = shipment1.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 15
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('100.00')
    >>> move.currency = company.currency
    >>> shipment1.click('wait')
    >>> shipment1.click('assign_force')
    >>> shipment1.click('pick')
    >>> shipment1.click('pack')
    >>> shipment1.click('do')
    >>> shipment1.state
    'done'

    >>> shipment2, = shipment1.duplicate()
    >>> move, = shipment2.outgoing_moves
    >>> move.quantity = 5
    >>> shipment2.click('wait')
    >>> shipment2.click('assign_force')
    >>> shipment2.click('pick')
    >>> shipment2.click('pack')
    >>> shipment2.click('do')
    >>> shipment2.state
    'done'

Invoice shipment cost::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = carrier
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product_shipment_cost
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('20.00')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Add shipment cost to both shipments::

    >>> shipment_cost = ShipmentCost(allocation_method='weight')
    >>> shipment_cost.invoice_lines.extend(
    ...     shipment_cost.invoice_lines.find([]))
    >>> shipment_cost.shipments.extend(
    ...     shipment_cost.shipments.find([]))
    >>> shipment_cost.save()
    >>> shipment_cost.state
    'draft'
    >>> post_shipment_cost = shipment_cost.click('post_wizard')
    >>> post_shipment_cost.form.cost
    Decimal('20.0000')
    >>> sorted([s.cost for s in post_shipment_cost.form.shipments])
    [Decimal('5.0000'), Decimal('15.0000')]
    >>> post_shipment_cost.execute('post')
    >>> shipment_cost.state
    'posted'
    >>> bool(shipment_cost.posted_date)
    True

Check shipment cost::

    >>> shipment1.reload()
    >>> shipment1.cost
    Decimal('15.0000')
    >>> shipment2.reload()
    >>> shipment2.cost
    Decimal('5.0000')
