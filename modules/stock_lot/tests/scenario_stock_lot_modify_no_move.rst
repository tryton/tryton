=================================
Stock Lot Modify No Move Scenario
=================================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock_lot', create_company)

    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Create products::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template1 = ProductTemplate(
    ...     name="Product 1", type='goods', default_uom=unit)
    >>> template1.save()
    >>> product1, = template1.products

    >>> template2 = ProductTemplate(
    ...     name="Product 2", type='goods', default_uom=unit)
    >>> template2.save()
    >>> product2, = template2.products

Create a lot::

    >>> lot = Lot(number="1", product=product2)
    >>> lot.save()

Modify the product of the lot without move::

    >>> lot.product = product1
    >>> lot.save()

Create a move with the lot::

    >>> lost_found, = Location.find([('type', '=', 'lost_found')])
    >>> storage, = Location.find([('code', '=', 'STO')])

    >>> move = Move(
    ...     product=product1, lot=lot, quantity=1,
    ...     from_location=lost_found, to_location=storage)
    >>> move.save()

Try to modify the product of the lot with move::

    >>> lot.product = product2
    >>> lot.save()
    Traceback (most recent call last):
        ...
    AccessError: ...
