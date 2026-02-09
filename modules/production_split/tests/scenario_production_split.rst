=========================
Production Split Scenario
=========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('production_split', create_company)

    >>> BoM = Model.get('production.bom')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Production = Model.get('production')

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal(20)
    >>> template.save()
    >>> product, = template.products

Create bill of material::

    >>> bom = BoM(name="Product")
    >>> _ = bom.outputs.new(product=product, quantity=1)
    >>> bom.save()

    >>> _ = product.boms.new(bom=bom)
    >>> product.save()

Create a production::

    >>> production = Production()
    >>> production.product = product
    >>> production.bom = bom
    >>> production.quantity = 10
    >>> production.save()

Split the production::

    >>> split_production = production.click('split_wizard')
    >>> split_production.form.quantity = 4
    >>> split_production.form.count = 1
    >>> split_production.execute('split')
    >>> production2, = Production.find([('id', '!=', production.id)])

    >>> production.quantity
    4.0
    >>> production2.quantity
    6.0
