============================
Stock Shipment Cost Scenario
============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules('stock_shipment_cost')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product1'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('10.0000')
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = 'Product2'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('20.0000')
    >>> product2.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Create a customer shipment::

    >>> Shipment = Model.get('stock.shipment.out')
    >>> shipment = Shipment()
    >>> shipment.customer = customer
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product1
    >>> move.quantity = 1
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('30')
    >>> move.currency = company.currency
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product2
    >>> move.quantity = 2
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('40')
    >>> move.currency = company.currency
    >>> shipment.click('wait')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.cost_edit = True
    >>> shipment.cost_used = Decimal('5')
    >>> shipment.cost_currency_used = company.currency
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check move costs::

    >>> sorted([
    ...         (m.cost_price, m.shipment_out_cost_price)
    ...         for m in shipment.outgoing_moves])
    [(Decimal('10.0000'), Decimal('1.0000')), (Decimal('20.0000'), Decimal('2.0000'))]

Check reporting margin::

    >>> MarginProduct = Model.get('stock.reporting.margin.product')
    >>> MarginProductTimeseries = Model.get(
    ...     'stock.reporting.margin.product.time_series')
    >>> context = {
    ...     'from_date': yesterday,
    ...     'to_date': today,
    ...     'period': 'day',
    ...     }
    >>> with config.set_context(context=context):
    ...     reports = MarginProduct.find([])
    ...     time_series = MarginProductTimeseries.find([])
    >>> len(reports)
    2
    >>> sorted([r.cost for r in reports]) == [Decimal('10.0000'), Decimal('40.0000')]
    True

    >>> context['include_shipment_cost'] = True
    >>> with config.set_context(context=context):
    ...     reports = MarginProduct.find([])
    ...     time_series = MarginProductTimeseries.find([])
    >>> len(reports)
    2
    >>> sorted([r.cost for r in reports]) == [Decimal('11.0000'), Decimal('44.0000')]
    True
