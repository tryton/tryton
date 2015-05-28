========================
Stock Inventory Scenario
========================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> today = datetime.date.today()

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install stock Module::

    >>> Module = Model.get('ir.module')
    >>> stock_module, = Module.find([('name', '=', 'stock')])
    >>> stock_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Get stock locations::

    >>> Location = Model.get('stock.location')
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price = Decimal('80')
    >>> template.cost_price_method = 'average'
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Fill storage::

    >>> StockMove = Model.get('stock.move')
    >>> incoming_move = StockMove()
    >>> incoming_move.product = product
    >>> incoming_move.uom = unit
    >>> incoming_move.quantity = 1
    >>> incoming_move.from_location = supplier_loc
    >>> incoming_move.to_location = storage_loc
    >>> incoming_move.planned_date = today
    >>> incoming_move.effective_date = today
    >>> incoming_move.company = company
    >>> incoming_move.unit_price = Decimal('100')
    >>> incoming_move.currency = company.currency
    >>> incoming_move.click('do')

Create an inventory::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.save()
    >>> inventory.click('complete_lines')
    >>> line, = inventory.lines
    >>> line.expected_quantity == 1
    True
    >>> line.quantity = 2
    >>> inventory.save()
    >>> inventory.click('confirm')
    >>> line.reload()
    >>> move, = line.moves
    >>> move.quantity == 1
    True
    >>> move.from_location == inventory.lost_found
    True
    >>> move.to_location == inventory.location
    True

Empty storage::

    >>> StockMove = Model.get('stock.move')
    >>> outgoing_move = StockMove()
    >>> outgoing_move.product = product
    >>> outgoing_move.uom = unit
    >>> outgoing_move.quantity = 2
    >>> outgoing_move.from_location = storage_loc
    >>> outgoing_move.to_location = customer_loc
    >>> outgoing_move.planned_date = today
    >>> outgoing_move.effective_date = today
    >>> outgoing_move.company = company
    >>> outgoing_move.unit_price = Decimal('100')
    >>> outgoing_move.currency = company.currency
    >>> outgoing_move.click('do')

Create an inventory that should be empty after completion::

    >>> Inventory = Model.get('stock.inventory')
    >>> inventory = Inventory()
    >>> inventory.location = storage_loc
    >>> inventory.click('complete_lines')
    >>> len(inventory.lines)
    0
