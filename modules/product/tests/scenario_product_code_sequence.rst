=====================
Product Code Sequence
=====================

Imports::

    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('product')

    >>> ProductConfiguration = Model.get('product.configuration')
    >>> ProductTemplate = Model.get('product.template')
    >>> Sequence = Model.get('ir.sequence')
    >>> SequenceType = Model.get('ir.sequence.type')
    >>> UoM = Model.get('product.uom')

Set sequences::

    >>> template_sequence = Sequence(name="Template")
    >>> template_sequence.sequence_type, = SequenceType.find(
    ...     [('name', '=', "Product")], limit=1)
    >>> template_sequence.save()
    >>> product_sequence = Sequence(name="Product")
    >>> product_sequence.sequence_type, = SequenceType.find(
    ...     [('name', '=', "Variant")], limit=1)
    >>> product_sequence.save()
    >>> product_configuration = ProductConfiguration(1)
    >>> product_configuration.template_sequence = template_sequence
    >>> product_configuration.product_sequence = product_sequence
    >>> product_configuration.save()

Create product::

    >>> template = ProductTemplate(code=None)
    >>> template.name = 'product'
    >>> template.default_uom, = UoM.find([('name', '=', 'Unit')])
    >>> template.type = 'service'
    >>> template.save()
    >>> product, = template.products

    >>> template.code
    '1'
    >>> product.suffix_code
    '1'
    >>> product.code
    '11'
