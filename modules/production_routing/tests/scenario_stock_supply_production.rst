===========================
Production Request Scenario
===========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_supply_production', 'production_routing'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal(30)
    >>> template.save()
    >>> product, = template.products

Create a Bill of Material with routing::

    >>> BoM = Model.get('production.bom')
    >>> bom = BoM(name="product")
    >>> _ = bom.outputs.new(product=product, quantity=1)
    >>> bom.save()
    >>> Routing = Model.get('production.routing')
    >>> routing = Routing(name="product")
    >>> routing.boms.append(BoM(bom.id))
    >>> routing.save()
    >>> product_bom = product.boms.new(bom=bom, routing=routing)
    >>> product.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> lost_loc, = Location.find([('type', '=', 'lost_found')])

Create a need for product::

    >>> Move = Model.get('stock.move')
    >>> move = Move()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = storage_loc
    >>> move.to_location = lost_loc
    >>> move.click('do')
    >>> move.state
    'done'

Create production request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a production request with the routing::

    >>> Production = Model.get('production')
    >>> production, = Production.find([])
    >>> production.routing == routing
    True
