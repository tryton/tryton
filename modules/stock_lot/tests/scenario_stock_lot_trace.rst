========================
Stock Lot Trace Scenario
========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock_lot', create_company)

    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> LotTrace = Model.get('stock.lot.trace')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.save()
    >>> product, = template.products

Create lot::

    >>> lot = Lot(product=product, number="1")
    >>> lot.save()

Get locations::

    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Make some moves::

    >>> move_in = Move(product=product, lot=lot)
    >>> move_in.quantity = 10
    >>> move_in.from_location = supplier_loc
    >>> move_in.to_location = storage_loc
    >>> move_in.currency = get_currency()
    >>> move_in.unit_price = Decimal('0')
    >>> move_in.click('do')
    >>> move_in.state
    'done'

    >>> move_out = Move(product=product, lot=lot)
    >>> move_out.quantity = 2
    >>> move_out.from_location = storage_loc
    >>> move_out.to_location = customer_loc
    >>> move_out.currency = get_currency()
    >>> move_out.unit_price = Decimal('0')
    >>> move_out.click('do')
    >>> move_out.state
    'done'

Check lot traces::

    >>> trace = LotTrace(move_in.id)
    >>> trace.upward_traces == [LotTrace(move_out.id)]
    True
    >>> trace.downward_traces
    []

    >>> trace = LotTrace(move_out.id)
    >>> trace.upward_traces
    []
    >>> trace.downward_traces == [LotTrace(move_in.id)]
    True
