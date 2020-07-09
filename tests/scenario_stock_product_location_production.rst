===========================================
Stock Product Locations Production Scenario
===========================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company

Activate modules::

    >>> _ = activate_modules(['stock_product_location', 'production'])

Create company::

    >>> _ = create_company()

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> production_loc, = Location.find([('code', '=', 'PROD')])

Create new location::

    >>> Location = Model.get('stock.location')
    >>> child_loc = Location()
    >>> child_loc.name = 'Child Location'
    >>> child_loc.parent = storage_loc
    >>> child_loc.code = 'CHI'
    >>> child_loc.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal(30)
    >>> template.save()
    >>> product, = template.products
    >>> product_location = product.locations.new()
    >>> product_location.warehouse = warehouse_loc
    >>> product_location.location = child_loc
    >>> product.save()

Create Components::

    >>> template1 = ProductTemplate()
    >>> template1.name = 'component 1'
    >>> template1.default_uom = unit
    >>> template1.type = 'goods'
    >>> template1.list_price = Decimal(5)
    >>> template1.save()
    >>> component1, = template1.products

    >>> meter, = ProductUom.find([('name', '=', 'Meter')])
    >>> centimeter, = ProductUom.find([('name', '=', 'centimeter')])
    >>> template2 = ProductTemplate()
    >>> template2.name = 'component 2'
    >>> template2.default_uom = meter
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal(7)
    >>> template2.save()
    >>> component2, = template2.products

Create Bill of Material::

    >>> BOM = Model.get('production.bom')
    >>> BOMInput = Model.get('production.bom.input')
    >>> BOMOutput = Model.get('production.bom.output')
    >>> bom = BOM(name='product')
    >>> input1 = BOMInput()
    >>> bom.inputs.append(input1)
    >>> input1.product = component1
    >>> input1.quantity = 5
    >>> input2 = BOMInput()
    >>> bom.inputs.append(input2)
    >>> input2.product = component2
    >>> input2.quantity = 150
    >>> input2.uom = centimeter
    >>> output = BOMOutput()
    >>> bom.outputs.append(output)
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.save()

    >>> ProductBom = Model.get('product.product-production.bom')
    >>> product.boms.append(ProductBom(bom=bom))
    >>> product.save()

Create an Inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory_line1 = InventoryLine()
    >>> inventory.lines.append(inventory_line1)
    >>> inventory_line1.product = component1
    >>> inventory_line1.quantity = 20
    >>> inventory_line2 = InventoryLine()
    >>> inventory.lines.append(inventory_line2)
    >>> inventory_line2.product = component2
    >>> inventory_line2.quantity = 6
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Make a production::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> production.planned_date = datetime.date.today()
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 2

Test storage location of the warehouse::

    >> warehouse_loc.storage_location == storage_loc
    True

Test locations of the production inputs::

    >>> all([input_.from_location == storage_loc for \
    ...      input_ in production.inputs])
    True
    >>> all([input_.to_location == production_loc for \
    ...      input_ in production.inputs])
    True

Test location of the production output::

    >>> output, = production.outputs
    >>> output.from_location == production_loc
    True
    >>> output.to_location == child_loc
    True
