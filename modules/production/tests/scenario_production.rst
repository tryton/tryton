===================
Production Scenario
===================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.production.production import BOM_CHANGES
    >>> today = datetime.date.today()
    >>> yesterday = today - relativedelta(days=1)
    >>> before_yesterday = yesterday - relativedelta(days=1)

Activate modules::

    >>> config = activate_modules('production')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal(30)
    >>> product, = template.products
    >>> product.cost_price = Decimal(20)
    >>> template.save()
    >>> product, = template.products

Create Components::

    >>> template1 = ProductTemplate()
    >>> template1.name = 'component 1'
    >>> template1.default_uom = unit
    >>> template1.type = 'goods'
    >>> template1.list_price = Decimal(5)
    >>> component1, = template1.products
    >>> component1.cost_price = Decimal(1)
    >>> template1.save()
    >>> component1, = template1.products

    >>> meter, = ProductUom.find([('name', '=', 'Meter')])
    >>> centimeter, = ProductUom.find([('name', '=', 'centimeter')])

    >>> template2 = ProductTemplate()
    >>> template2.name = 'component 2'
    >>> template2.default_uom = meter
    >>> template2.type = 'goods'
    >>> template2.list_price = Decimal(7)
    >>> component2, = template2.products
    >>> component2.cost_price = Decimal(5)
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

    >>> ProductionLeadTime = Model.get('production.lead_time')
    >>> production_lead_time = ProductionLeadTime()
    >>> production_lead_time.product = product
    >>> production_lead_time.bom = bom
    >>> production_lead_time.lead_time = datetime.timedelta(1)
    >>> production_lead_time.save()

Create an Inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> InventoryLine = Model.get('stock.inventory.line')
    >>> Location = Model.get('stock.location')
    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
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
    >>> production.planned_date = today
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 2
    >>> production.planned_start_date == yesterday
    True
    >>> sorted([i.quantity for i in production.inputs]) == [10, 300]
    True
    >>> output, = production.outputs
    >>> output.quantity == 2
    True
    >>> production.save()
    >>> production.cost
    Decimal('25.0000')
    >>> production.click('wait')
    >>> production.state
    'waiting'

Test reset bom button::

    >>> for input in production.inputs:
    ...     input.quantity += 1
    >>> production.click('reset_bom', change=BOM_CHANGES)
    >>> sorted([i.quantity for i in production.inputs]) == [10, 300]
    True
    >>> output, = production.outputs
    >>> output.quantity == 2
    True

Do the production::

    >>> production.click('assign_try')
    True
    >>> all(i.state == 'assigned' for i in production.inputs)
    True
    >>> production.click('run')
    >>> all(i.state == 'done' for i in production.inputs)
    True
    >>> len(set(i.effective_date == today for i in production.inputs))
    1
    >>> production.click('done')
    >>> output, = production.outputs
    >>> output.state
    'done'
    >>> output.effective_date == production.effective_date
    True
    >>> output.unit_price
    Decimal('12.5000')
    >>> with config.set_context(locations=[storage.id]):
    ...     Product(product.id).quantity == 2
    True

Make a production with effective date yesterday and running the day before::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> production.effective_date = yesterday
    >>> production.effective_start_date = before_yesterday
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 2
    >>> production.click('wait')
    >>> production.click('assign_try')
    True
    >>> production.click('run')
    >>> production.reload()
    >>> all(i.effective_date == before_yesterday for i in production.inputs)
    True
    >>> production.click('done')
    >>> production.reload()
    >>> output, = production.outputs
    >>> output.effective_date == yesterday
    True


Make a production with a bom of zero quantity::

    >>> zero_bom, = BOM.duplicate([bom])
    >>> for input_ in bom.inputs:
    ...     input_.quantity = 0.0
    >>> bom_output, = bom.outputs
    >>> bom_output.quantity = 0.0
    >>> bom.save()
    >>> production = Production()
    >>> production.product = product
    >>> production.bom = bom
    >>> production.planned_start_date = yesterday
    >>> production.quantity = 2
    >>> [i.quantity for i in production.inputs]
    [0.0, 0.0]
    >>> output, = production.outputs
    >>> output.quantity
    0.0

Reschedule productions::

    >>> production.click('wait')
    >>> Cron = Model.get('ir.cron')
    >>> cron = Cron(method='production|reschedule')
    >>> cron.interval_number = 1
    >>> cron.interval_type = 'months'
    >>> cron.click('run_once')
    >>> production.reload()
    >>> production.planned_start_date == today
    True
