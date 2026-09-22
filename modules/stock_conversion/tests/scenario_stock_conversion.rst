=========================
Stock Conversion Scenario
=========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, assertIsNotNone

Activate modules::

    >>> config = activate_modules('stock_conversion', create_company)

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Product = Model.get('product.product')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> StockConversion = Model.get('stock.conversion')

Create products::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])

    >>> template_box = ProductTemplate()
    >>> template_box.name = "Product Box"
    >>> template_box.default_uom = unit
    >>> template_box.type = 'goods'
    >>> template_box.save()
    >>> product_box, = template_box.products
    >>> product_box.cost_price = Decimal('50.0000')
    >>> product_box.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product, = template.products

Define a conversion rule::

    >>> conversion_rule = product_box.conversion_rules.new()
    >>> conversion_rule.input_quantity = 1
    >>> assertEqual(conversion_rule.input_unit, unit)
    >>> conversion_rule.output_product = product
    >>> conversion_rule.output_quantity = 6
    >>> assertEqual(conversion_rule.output_unit, unit)
    >>> product_box.save()
    >>> conversion_rule, = product_box.conversion_rules

Setup an inventory::

    >>> storage, = Location.find([('code', '=', 'STO')], limit=1)

    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line = inventory.lines.new(product=product_box)
    >>> inventory_line.quantity = 100
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Try to convert without enough quantity in stock::

    >>> conversion = StockConversion()
    >>> conversion.location = storage
    >>> conversion.input_product = product_box
    >>> conversion.input_quantity = 120
    >>> conversion.output_product = product
    >>> assertEqual(conversion.conversion_rule, conversion_rule)
    >>> conversion.output_quantity
    720.0
    >>> conversion.save()
    >>> assertIsNotNone(conversion.number)

    >>> conversion.click('do')
    Traceback (most recent call last):
        ...
    ConversionError: ...

Change converted quantity for the stock::

    >>> conversion.input_quantity = 10
    >>> conversion.output_quantity
    60.0
    >>> conversion.click('do')
    >>> conversion.state
    'done'
    >>> len(conversion.moves)
    2
    >>> input_move, = [m for m in conversion.moves if m.product == product_box]
    >>> input_move.cost_price
    Decimal('50.0000')
    >>> output_move, = [m for m in conversion.moves if m.product == product]
    >>> output_move.unit_price
    Decimal('8.3333')

Check stock quantities::

    >>> with config.set_context(location=storage.id):
    ...     product_box = Product(product_box.id)
    ...     product = Product(product.id)
    >>> product_box.quantity
    90.0
    >>> product.quantity
    60.0

Cancel conversion::

    >>> conversion.click('cancel')
    >>> conversion.state
    'cancelled'

Check stock quantities::

    >>> product_box.reload()
    >>> product_box.quantity
    100.0
    >>> product.reload()
    >>> product.quantity
    0.0

Check conversion rule modification is forbidden once used::

    >>> conversion_rule.input_quantity = 2
    >>> conversion_rule.save()
    Traceback (most recent call last):
        ...
    AccessError: ...
