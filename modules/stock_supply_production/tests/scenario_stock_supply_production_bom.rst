====================================
Production Request with BoM Scenario
====================================

Imports::

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual


Activate modules::

    >>> config = activate_modules('stock_supply_production', create_company)

    >>> BoM = Model.get('production.bom')
    >>> Location = Model.get('stock.location')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Production = Model.get('production')

Create product with a BoM::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> box = ProductUom(name="Box", symbol="b", category=unit.category)
    >>> box.factor = 10
    >>> box.rounding = 1
    >>> box.digits = 0
    >>> box.save()

    >>> template = ProductTemplate()
    >>> template.name = "product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.save()
    >>> product, = template.products

    >>> bom = BoM(name="Product")
    >>> output = bom.outputs.new()
    >>> output.product = product
    >>> output.quantity = 1
    >>> output.unit = box
    >>> bom.save()

    >>> _ = product.boms.new(bom=bom)
    >>> product.save()

Get stock locations::

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')])

Create needs for product::

    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 2
    >>> move.from_location = storage_loc
    >>> move.to_location = lost_loc
    >>> move.click('do')
    >>> move.state
    'done'

Create production request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

    >>> production, = Production.find([])
    >>> assertEqual(production.product, product)
    >>> production.quantity
    1.0
    >>> assertEqual(production.unit, box)
