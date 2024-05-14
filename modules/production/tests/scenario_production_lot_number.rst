====================================
Stock Lot Number Production Scenario
====================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules(['stock_lot', 'production'])

    >>> ProductTemplate = Model.get('product.template')
    >>> Production = Model.get('production')
    >>> Production = Model.get('production')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> UoM = Model.get('product.uom')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create lot sequence::

    >>> sequence_type, = SequenceType.find(
    ...     [('name', '=', "Stock Lot")], limit=1)
    >>> sequence = Sequence(name="Lot", sequence_type=sequence_type, company=None)
    >>> sequence.save()

Create product::

    >>> unit, = UoM.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.0000')
    >>> template.lot_required = ['storage']
    >>> template.lot_sequence = sequence
    >>> template.save()
    >>> product, = template.products

Make a production::

    >>> production = Production()
    >>> output = production.outputs.new()
    >>> output.from_location = production.location
    >>> output.to_location = production.warehouse.storage_location
    >>> output.product = product
    >>> output.quantity = 1
    >>> output.unit_price = Decimal(0)
    >>> output.currency = production.company.currency
    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')
    >>> production.click('done')
    >>> production.state
    'done'

    >>> output, = production.outputs
    >>> bool(output.lot)
    True
