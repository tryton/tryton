=======================================
Sale Supply Production Routing Scenario
=======================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['sale_supply_production', 'production_routing'],
    ...     create_company)

    >>> BoM = Model.get('production.bom')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Production = Model.get('production')
    >>> Routing = Model.get('production.routing')
    >>> Sale = Model.get('sale.sale')

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.salable = True
    >>> template.supply_on_sale = 'always'
    >>> template.list_price = Decimal(30)
    >>> product, = template.products
    >>> product.cost_price = Decimal(20)
    >>> template.save()
    >>> product, = template.products

Create a Bill of Material with routing::

    >>> bom = BoM(name="product")
    >>> _ = bom.outputs.new(product=product, quantity=1)
    >>> bom.save()
    >>> routing = Routing(name="product")
    >>> routing.boms.append(BoM(bom.id))
    >>> routing.save()

    >>> _ = product.boms.new(bom=bom, routing=routing)
    >>> product.save()

Sale 10 products::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.invoice_method = 'manual'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Check the production::

    >>> production, = Production.find([])
    >>> production.state
    'request'
    >>> assertEqual(production.product, product)
    >>> assertEqual(production.bom, bom)
    >>> assertEqual(production.routing, routing)
