==================================
Sale Product Quantity POS Scenario
==================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules(
    ...     ['sale_product_quantity', 'sale_point'])

    >>> Journal = Model.get('account.journal')
    >>> Location = Model.get('stock.location')
    >>> POS = Model.get('sale.point')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.point.sale')
    >>> SequenceStrict = Model.get('ir.sequence.strict')
    >>> SequenceType = Model.get('ir.sequence.type')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Get journal::

    >>> journal_revenue, = Journal.find([('type', '=', 'revenue')], limit=1)

Get stock locations::

    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create POS::

    >>> pos = POS(name="POS")
    >>> pos.journal = journal_revenue
    >>> pos.sequence = SequenceStrict(name="POS", company=pos.company)
    >>> pos.sequence.sequence_type, = SequenceType.find(
    ...     [('name', '=', "POS")], limit=1)
    >>> pos.sequence.save()
    >>> pos.storage_location = storage_loc
    >>> pos.customer_location = customer_loc
    >>> pos.save()

Create product::

    >>> gr, = ProductUom.find([('name', '=', "Gram")])
    >>> kg, = ProductUom.find([('name', '=', "Kilogram")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = gr
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10')
    >>> template.salable = True
    >>> template.sale_uom = kg
    >>> template.sale_quantity_minimal = 0.1
    >>> template.sale_quantity_rounding = 0.05
    >>> template.save()
    >>> product, = template.products

Make a sale::

    >>> sale = Sale(point=pos)

    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity
    0.1
    >>> sale.save()

Can not set quantity below minimal::

    >>> line, = sale.lines
    >>> line.quantity = 0.05
    >>> sale.save()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    SaleValidationError: ...

Can not set quantity different than rounding::

    >>> line, = sale.lines
    >>> line.quantity = 1.01
    >>> sale.save()  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    SaleValidationError: ...
