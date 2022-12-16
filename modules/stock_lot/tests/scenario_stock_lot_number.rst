=========================
Stock Lot Number Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('stock_lot')

Create lot sequence::

    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> sequence_type, = SequenceType.find(
    ...     [('name', '=', "Stock Lot")], limit=1)
    >>> sequence = Sequence(name="Lot", sequence_type=sequence_type)
    >>> sequence.save()

Set default sequence::

    >>> Configuration = Model.get('product.configuration')
    >>> configuration = Configuration(1)
    >>> configuration.default_lot_sequence = sequence
    >>> configuration.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.lot_sequence == sequence
    True
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product, = template.products

Create lot without number::

    >>> Lot = Model.get('stock.lot')
    >>> lot = Lot(product=product)
    >>> lot.save()

    >>> lot.number
    '1'
