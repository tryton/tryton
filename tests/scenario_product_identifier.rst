===========================
Product Identifier Scenario
===========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('product')

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal('40')
    >>> template.save()
    >>> product, = template.products

The identifier code is computed when set::

    >>> identifier = product.identifiers.new()
    >>> identifier.type = 'ean'
    >>> identifier.code = '123 456 7890 123'
    >>> identifier.code
    '1234567890123'

An Error is raised for invalid code::

    >>> product.save() # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    InvalidIdentifierCode: ...

Valid codes are saved correctly::

    >>> identifier.code = '978-0-471-11709-4'
    >>> product.save()
    >>> identifier, = product.identifiers
    >>> identifier.code
    '9780471117094'
