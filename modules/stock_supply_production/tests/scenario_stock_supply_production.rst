===========================
Production Request Scenario
===========================

Imports::

    >>> from datetime import timedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company

Install stock_supply_production Module::

    >>> config = activate_modules('stock_supply_production')

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

Define a supply period for production::

    >>> ProductionConfiguration = Model.get('production.configuration')
    >>> production_configuration = ProductionConfiguration(1)
    >>> production_configuration.supply_period = timedelta(1)
    >>> production_configuration.save()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
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
    u'done'

The is no production request::

    >>> Production = Model.get('production')
    >>> Production.find([])
    []

Create production request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a production request::

    >>> production, = Production.find([])
    >>> production.state
    u'request'
    >>> production.product == product
    True
    >>> production.quantity
    1.0

With an order point without minimal quantity::

    >>> OrderPoint = Model.get('stock.order_point')
    >>> order_point = OrderPoint()
    >>> order_point.type = 'production'
    >>> order_point.product = product
    >>> order_point.warehouse_location = warehouse_loc
    >>> order_point.min_quantity = None
    >>> order_point.target_quantity = 10
    >>> order_point.save()

Create production request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

The is no more production request::

    >>> Production = Model.get('production')
    >>> Production.find([])
    []

Set a minimal quantity on order point::

    >>> order_point.min_quantity = 5
    >>> order_point.save()

Create production request::

    >>> create_pr = Wizard('stock.supply')
    >>> create_pr.execute('create_')

There is now a production request::

    >>> production, = Production.find([])
    >>> production.state
    u'request'
    >>> production.product == product
    True
    >>> production.quantity
    11.0
