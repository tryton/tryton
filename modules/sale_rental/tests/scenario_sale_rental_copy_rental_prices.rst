================================
Sale Copy Rental Prices Scenario
================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('sale_rental', create_company)

    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Create a rentable asset::

    >>> unit, = UoM.find([('name', '=', "Unit")])
    >>> day, = UoM.find([('name', '=', "Day")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.type = 'assets'
    >>> template.default_uom = unit
    >>> template.rentable = True
    >>> template.rental_unit = day
    >>> rental_price = template.rental_prices.new()
    >>> rental_price.duration = dt.timedelta(days=1)
    >>> rental_price.price = Decimal('10.0000')
    >>> template.save()
    >>> product, = template.products
    >>> rental_price = product.rental_prices.new()
    >>> rental_price.duration = dt.timedelta(days=7)
    >>> rental_price.price = Decimal('50.0000')
    >>> assertEqual(rental_price.template, template)
    >>> product.save()

Rental prices are copied when copying the template::

    >>> template_copy, = template.duplicate()
    >>> product_copy, = template_copy.products
    >>> len(template_copy.rental_prices)
    2
    >>> len(product_copy.rental_prices)
    1
