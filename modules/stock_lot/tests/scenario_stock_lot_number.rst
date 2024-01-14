=========================
Stock Lot Number Scenario
=========================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules, assertEqual

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
    >>> assertEqual(template.lot_sequence, sequence)
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

Copy set a new number::

    >>> lot2, = lot.duplicate()
    >>> lot2.number
    '2'

Copy without sequence keep same number::

    >>> template.lot_sequence = None
    >>> template.save()
    >>> lot3, = lot.duplicate()
    >>> lot3.number
    '1'
