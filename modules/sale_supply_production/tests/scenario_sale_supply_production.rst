===============================
Sale Supply Production Scenario
===============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     'sale_supply_production', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.salable = True
    >>> template.supply_on_sale = 'always'
    >>> template.list_price = Decimal(30)
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal(20)
    >>> template.save()
    >>> product, = template.products

Create components::

    >>> template = ProductTemplate()
    >>> template.name = "Component 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(5)
    >>> component, = template.products
    >>> component.cost_price = Decimal(1)
    >>> template.save()
    >>> component, = template.products

Create bill of material::

    >>> BOM = Model.get('production.bom')
    >>> bom = BOM(name="Product")
    >>> input = bom.inputs.new()
    >>> input.product = component
    >>> input.quantity = 5
    >>> output = bom.outputs.new()
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.save()

    >>> product_bom = product.boms.new()
    >>> product_bom.bom = bom
    >>> product.save()

Sale 10 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> shipment, = sale.shipments
    >>> move, = shipment.outgoing_moves
    >>> move.state
    'staging'
    >>> move, = shipment.inventory_moves
    >>> move.state
    'staging'

Check the production::

    >>> Production = Model.get('production')
    >>> production, = Production.find([])
    >>> production.state
    'request'
    >>> assertEqual(production.origin, sale.lines[0])
    >>> assertEqual(production.product, product)
    >>> assertEqual(production.bom, bom)
    >>> production.quantity
    10.0

Delete the production, recreate one::

    >>> production.delete()
    >>> production, = Production.find([])
    >>> production.quantity
    10.0

Start the production::

    >>> production.click('draft')
    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')
    >>> production.state
    'running'

    >>> shipment.reload()
    >>> move, = shipment.outgoing_moves
    >>> move.state
    'draft'
    >>> move, = shipment.inventory_moves
    >>> move.state
    'draft'

Finish the production::

    >>> production.click('do')

    >>> shipment.reload()
    >>> move, = shipment.outgoing_moves
    >>> move.state
    'draft'
    >>> move, = shipment.inventory_moves
    >>> move.state
    'assigned'
