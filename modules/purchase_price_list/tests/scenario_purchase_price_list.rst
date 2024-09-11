============================
Purchase Price List Scenario
============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('purchase_price_list', create_company)

    >>> Party = Model.get('party.party')
    >>> PriceList = Model.get('product.price_list')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Purchase = Model.get('purchase.purchase')

Create supplier::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.list_price = Decimal('20.0000')
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('15.0000')
    >>> product.save()

Fill a purchase without price list::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.unit_price

Create a price list and assign it to supplier::

    >>> price_list = PriceList(name="Supplier")
    >>> price_list_line = price_list.lines.new()
    >>> price_list_line.product = product
    >>> price_list_line.formula = 'list_price * 0.7'
    >>> price_list.save()

    >>> supplier.purchase_price_list = price_list
    >>> supplier.save()

Fill a purchase with price list::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.unit_price
    Decimal('14.0000')

Define product supplier price::

    >>> product_supplier = product.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> price = product_supplier.prices.new()
    >>> price.quantity = 0
    >>> price.unit_price = Decimal('12.0000')
    >>> product.save()

Fill a purchase with price list and a product supplier price::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product
    >>> purchase_line.unit_price
    Decimal('12.0000')
