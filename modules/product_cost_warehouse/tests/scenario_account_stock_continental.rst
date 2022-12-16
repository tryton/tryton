==================================
Account Stock Continental Scenario
==================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_stock_continental.tests.tools import (
    ...     add_stock_accounts)

Activate product_cost_warehouse::

    >>> config = activate_modules([
    ...         'product_cost_warehouse', 'account_stock_continental'])

    >>> Location = Model.get('stock.location')
    >>> Product = Model.get('product.product')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductConfiguration = Model.get('product.configuration')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentInternal = Model.get('stock.shipment.internal')
    >>> StockConfiguration = Model.get('stock.configuration')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = create_fiscalyear(company)
    >>> fiscalyear.account_stock_method = 'continental'
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = add_stock_accounts(get_accounts(company), company)

Create product category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.account_stock = accounts['stock']
    >>> account_category.account_stock_in = accounts['stock_expense']
    >>> account_category.account_stock_out = accounts['stock_expense']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('300')
    >>> template.cost_price_method = 'average'
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> template.save()
    >>> product, = template.products

Set cost per warehouse::

    >>> product_config = ProductConfiguration(1)
    >>> product_config.cost_price_warehouse = True
    >>> product_config.save()

Create stock locations::

    >>> warehouse1, = Location.find([('code', '=', 'WH')])
    >>> warehouse2, = warehouse1.duplicate(default={'name': "Warhouse bis"})
    >>> transit = Location(name="Transit", type='storage')
    >>> transit.save()
    >>> stock_config = StockConfiguration(1)
    >>> stock_config.shipment_internal_transit = transit
    >>> stock_config.save()
    >>> supplier_loc, = Location.find([('code', '=', 'SUP')])

Make 1 unit of product available @ 100 on 1st warehouse::

    >>> StockMove = Model.get('stock.move')
    >>> move = StockMove()
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.from_location = supplier_loc
    >>> move.to_location = warehouse1.storage_location
    >>> move.unit_price = Decimal('100')
    >>> move.currency = company.currency
    >>> move.click('do')

    >>> accounts['stock'].reload()
    >>> accounts['stock'].balance
    Decimal('100.00')

Transfer 1 product between warehouses::

    >>> shipment = ShipmentInternal()
    >>> shipment.from_location = warehouse1.storage_location
    >>> shipment.to_location = warehouse2.storage_location
    >>> move = shipment.moves.new()
    >>> move.from_location = shipment.from_location
    >>> move.to_location = shipment.to_location
    >>> move.product = product
    >>> move.quantity = 1
    >>> move.unit_price = product.cost_price
    >>> shipment.click('wait')
    >>> shipment.click('assign_force')

    >>> shipment.click('ship')
    >>> shipment.state
    'shipped'
    >>> accounts['stock'].reload()
    >>> accounts['stock'].balance
    Decimal('0.00')

    >>> shipment.click('done')
    >>> shipment.state
    'done'
    >>> accounts['stock'].reload()
    >>> accounts['stock'].balance
    Decimal('100.00')
