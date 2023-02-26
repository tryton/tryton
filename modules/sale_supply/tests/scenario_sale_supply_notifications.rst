=========================
Sale Supply Notifications
=========================

Imports::

    >>> from proteus import Model

    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company

Activate modules::

    >>> config = activate_modules(['sale_supply', 'stock_supply'])

    >>> Location = Model.get('stock.location')
    >>> OrderPoint = Model.get('stock.order_point')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Create company::

    >>> _ = create_company()

Get locations::

    >>> warehouse_location, = Location.find([('type', '=', 'warehouse')])

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> product_template = ProductTemplate()
    >>> product_template.name = "Product"
    >>> product_template.type = 'goods'
    >>> product_template.default_uom = unit
    >>> product_template.purchasable = True
    >>> product_template.salable = True
    >>> product_template.supply_on_sale = 'always'
    >>> product_template.save()
    >>> product, = product_template.products

Create order point::

    >>> order_point = OrderPoint()
    >>> order_point.product = product
    >>> order_point.warehouse_location = warehouse_location
    >>> order_point.type = 'purchase'
    >>> order_point.min_quantity = 0
    >>> order_point.target_quantity = 5
    >>> order_point.save()

Check notifications::

    >>> len(product_template.notifications())
    1
    >>> len(order_point.notifications())
    1
