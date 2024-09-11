===============================
Production Outsourcing Scenario
===============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     'production_outsourcing', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']

Create supplier::

    >>> Party = Model.get('party.party')
    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.save()

Create Product::

    >>> Uom = Model.get('product.uom')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.producible = True
    >>> template.list_price = Decimal(30)
    >>> product, = template.products
    >>> product.cost_price = Decimal(20)
    >>> template.save()
    >>> product, = template.products

Create Component::

    >>> template = ProductTemplate()
    >>> template.name = "Component"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal(5)
    >>> component, = template.products
    >>> component.cost_price = Decimal(1)
    >>> template.save()
    >>> component, = template.products

Create Supplier Service::

    >>> template = ProductTemplate()
    >>> template.name = "Production Service"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.purchasable = True
    >>> template.list_price = Decimal(20)
    >>> template.account_category = account_category
    >>> service, = template.products
    >>> service_supplier = template.product_suppliers.new()
    >>> service_supplier.party = supplier
    >>> service_supplier_price = service_supplier.prices.new()
    >>> service_supplier_price.unit_price = Decimal('20.0000')
    >>> template.save()
    >>> service, = template.products
    >>> service_supplier, = template.product_suppliers

Create Bill of Material::

    >>> BOM = Model.get('production.bom')
    >>> bom = BOM(name="Product")
    >>> input = bom.inputs.new()
    >>> input.product = component
    >>> input.quantity = 1
    >>> output = bom.outputs.new()
    >>> output.product = product
    >>> output.quantity = 1
    >>> bom.save()

Create Routing::

    >>> Routing = Model.get('production.routing')
    >>> routing = Routing(name="Supplier")
    >>> routing.supplier = supplier
    >>> routing.supplier_service = service
    >>> assertEqual(routing.supplier_service_supplier, service_supplier)
    >>> routing.supplier_quantity = 2
    >>> routing.boms.append(bom)
    >>> routing.save()

Set Bill of Material and Routing to the Product::

    >>> ProductBOM = Model.get('product.product-production.bom')
    >>> product.boms.append(ProductBOM(bom=bom, routing=routing))
    >>> product.save()

Make a production::

    >>> Production = Model.get('production')
    >>> production = Production()
    >>> production.product = product
    >>> production.bom = bom
    >>> production.routing = routing
    >>> production.quantity = 10
    >>> production.click('wait')
    >>> production.state
    'waiting'
    >>> purchase_line, = production.purchase_lines
    >>> assertEqual(purchase_line.product, service)
    >>> assertEqual(purchase_line.product_supplier, service_supplier)
    >>> purchase_line.quantity
    20.0
    >>> production.cost
    Decimal('410.0000')

Reset to draft::

    >>> production.click('draft')
    >>> production.purchase_lines
    []

Try to do the production with pending purchase::

    >>> production.click('wait')
    >>> production.click('assign_force')
    >>> production.click('run')
    >>> production.click('do')
    Traceback (most recent call last):
        ...
    PurchaseWarning: ...

Validate the purchase::

    >>> purchase_line, = production.purchase_lines
    >>> purchase = purchase_line.purchase
    >>> purchase.click('quote')
    >>> purchase.click('confirm')

Do the production::

    >>> production.click('do')
