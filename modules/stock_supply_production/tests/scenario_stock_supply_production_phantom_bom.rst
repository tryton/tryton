=================================================
Stock Supply Production with Phantom BoM Scenario
=================================================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual


Activate modules::

    >>> config = activate_modules('stock_supply_production', create_company)

    >>> BoM = Model.get('production.bom')
    >>> Location = Model.get('stock.location')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Production = Model.get('production')
    >>> Shipment = Model.get('stock.shipment.internal')

Create product with a BoM::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> raw_template = ProductTemplate(name="Raw Product")
    >>> raw_template.default_uom = unit
    >>> raw_template.type = 'goods'
    >>> raw_template.save()
    >>> raw_product, = raw_template.products

    >>> template = ProductTemplate()
    >>> template.name = "product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.save()
    >>> product, = template.products

    >>> phantom_bom_input = BoM(name="Raw Input")
    >>> phantom_bom_input.phantom = True
    >>> phantom_bom_input.phantom_quantity = 1
    >>> phantom_bom_input.phantom_unit = unit
    >>> phantom_input = phantom_bom_input.inputs.new()
    >>> phantom_input.product = raw_product
    >>> phantom_input.quantity = 10
    >>> phantom_bom_input.save()

    >>> phantom_bom_output = BoM(name="Product Output")
    >>> phantom_bom_output.phantom = True
    >>> phantom_bom_output.phantom_quantity = 1
    >>> phantom_bom_output.phantom_unit = unit
    >>> phantom_output = phantom_bom_output.outputs.new()
    >>> phantom_output.product = raw_product
    >>> phantom_output.quantity = 1
    >>> phantom_bom_output.save()

    >>> bom = BoM(name="Product")
    >>> input = bom.inputs.new()
    >>> input.phantom_bom = phantom_bom_input
    >>> input.quantity = 1
    >>> output = bom.outputs.new()
    >>> output.product = product
    >>> output.quantity = 1
    >>> output = bom.outputs.new()
    >>> output.phantom_bom = phantom_bom_output
    >>> output.quantity = 1
    >>> bom.save()

    >>> _ = product.boms.new(bom=bom)
    >>> product.save()

Get stock locations::

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')])

Create needs for product::

    >>> shipment = Shipment(from_location=storage_loc, to_location=lost_loc)
    >>> move = shipment.moves.new()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = lost_loc
    >>> shipment.click('wait')
    >>> shipment.click('assign_force')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Create production request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

    >>> production, = Production.find([])
    >>> assertEqual(production.product, product)
    >>> production.quantity
    1.0
    >>> len(production.inputs)
    1
    >>> len(production.outputs)
    2
