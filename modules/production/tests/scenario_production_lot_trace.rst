=============================
Production Lot Trace Scenario
=============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(['stock_lot', 'production'])

    >>> Lot = Model.get('stock.lot')
    >>> LotTrace = Model.get('stock.lot.trace')
    >>> ProductTemplate = Model.get('product.template')
    >>> Production = Model.get('production')
    >>> UoM = Model.get('product.uom')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> unit, = UoM.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate(name="Product")
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.producible = True
    >>> template.list_price = Decimal(1)
    >>> template.save()
    >>> product, = template.products

Create component::

    >>> template = ProductTemplate(name="Component")
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.save()
    >>> component, = template.products

Create Lots::

    >>> product_lot = Lot(product=product, number="1")
    >>> product_lot.save()
    >>> component_lot = Lot(product=component, number="2")
    >>> component_lot.save()

Make a production::

    >>> production = Production()
    >>> input = production.inputs.new()
    >>> input.from_location = production.warehouse.storage_location
    >>> input.to_location = production.location
    >>> input.product = component
    >>> input.lot = component_lot
    >>> input.quantity = 1
    >>> input.currency = production.company.currency
    >>> input.unit_price = Decimal(0)
    >>> output = production.outputs.new()
    >>> output.from_location = production.location
    >>> output.to_location = production.warehouse.storage_location
    >>> output.product = product
    >>> output.lot = product_lot
    >>> output.quantity = 1
    >>> output.currency = production.company.currency
    >>> output.unit_price = Decimal(0)
    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')
    >>> production.click('do')
    >>> production.state
    'done'


Check lot traces::

    >>> trace, = LotTrace.find([('lot', '=', product_lot.id)])
    >>> trace.document == production
    True
    >>> trace.upward_traces
    []
    >>> trace, = trace.downward_traces
    >>> trace.document == production
    True
    >>> trace.product == component
    True

    >>> trace, = LotTrace.find([('lot', '=', component_lot.id)])
    >>> trace.document == production
    True
    >>> trace.downward_traces
    []
    >>> trace, = trace.upward_traces
    >>> trace.document == production
    True
    >>> trace.product == product
    True
