==================================
Stock Conversion with Lot Scenario
==================================

Imports::

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(['stock_lot', 'stock_conversion'], create_company)

    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Lot = Model.get('stock.lot')
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

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.save()
    >>> product, = template.products

Create lots::

    >>> lot_box = Lot(number="1", product=product_box)
    >>> lot_box.save()
    >>> lot = Lot(number="2", product=product)
    >>> lot.save()

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
    >>> inventory_line.quantity = 1
    >>> inventory_line = inventory.lines.new(product=product_box)
    >>> inventory_line.quantity = 2
    >>> inventory_line.lot = lot_box
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Try to convert without enough lot quantity in stock::

    >>> conversion = StockConversion()
    >>> conversion.location = storage
    >>> conversion.input_product = product_box
    >>> conversion.input_lot = lot_box
    >>> conversion.input_quantity = 3
    >>> conversion.output_product = product
    >>> conversion.output_lot = lot
    >>> conversion.save()

    >>> conversion.click('do')
    Traceback (most recent call last):
        ...
    ConversionError: ...

Change converted quantity for the stock::

    >>> conversion.input_quantity = 2
    >>> conversion.click('do')
    >>> conversion.state
    'done'

Check moves::

    >>> assertEqual({m.lot for m in conversion.moves}, {lot_box, lot})
