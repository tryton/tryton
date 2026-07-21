=================================
Stock Lot Modify No Move Scenario
=================================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock_lot_unit', create_company)

    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
    >>> Move = Model.get('stock.move')
    >>> ProductTemplate = Model.get('product.template')
    >>> UoM = Model.get('product.uom')

Create product::

    >>> unit1, = UoM.find([('name', '=', "Unit")])
    >>> unit2, = unit1.duplicate()

    >>> template = ProductTemplate(
    ...     name="Product", type='goods', default_uom=unit1)
    >>> template.save()
    >>> product, = template.products

Create a lot::

    >>> lot = Lot(
    ...     number="1", product=product,
    ...     unit=unit2, unit_quantity=3)
    >>> lot.save()

Create a move with the lot::

    >>> lost_found, = Location.find([('type', '=', 'lost_found')])
    >>> storage, = Location.find([('code', '=', 'STO')])

    >>> move = Move(
    ...     product=product, lot=lot, quantity=5,
    ...     from_location=lost_found, to_location=storage)
    >>> move.save()

Modify the units of the lot without move done::

    >>> lot.unit = unit1
    >>> lot.unit_quantity = 5
    >>> lot.save()

Complete the move::

    >>> move.click('do')
    >>> move.state
    'done'

Try to modify the units of the lot with move done::

    >>> lot.unit = unit2
    >>> lot.save()
    Traceback (most recent call last):
        ...
    AccessError: ...

    >>> lot.reload()
    >>> lot.unit_quantity = 3
    >>> lot.save()
    Traceback (most recent call last):
        ...
    AccessError: ...

