==================================
Purchase Product Quantity Scenario
==================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, set_user

Activate modules::

    >>> config = activate_modules(
    ...     ['purchase_product_quantity', 'purchase_request'],
    ...     create_company, create_chart)

    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> PurchaseRequest = Model.get('purchase.request')

Get accounts::

    >>> accounts = get_accounts()

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.save()

Create product::

    >>> gr, = ProductUom.find([('name', '=', "Gram")])
    >>> kg, = ProductUom.find([('name', '=', "Kilogram")])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = gr
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.purchasable = True
    >>> template.purchase_uom = kg
    >>> product_supplier = template.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> product_supplier.quantity_minimal = 0.1
    >>> product_supplier.quantity_rounding = 0.05
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> template.save()
    >>> product, = template.products

Get stock locations::

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])

Create the purchase request below minimal::

    >>> ctx = config.context
    >>> set_user(0)
    >>> pr_id, = PurchaseRequest.create([{
    ...             'product': product.id,
    ...             'quantity': 30,
    ...             'unit': gr,
    ...             'warehouse': warehouse_loc.id,
    ...             }], ctx)
    >>> set_user()
    >>> purchase_request = PurchaseRequest(pr_id)

Create purchase::

    >>> create_purchase = Wizard(
    ...     'purchase.request.create_purchase', [purchase_request])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> purchase_request.state
    'purchased'

    >>> assertEqual(purchase_request.purchase_line.unit, gr)
    >>> purchase_request.purchase_line.quantity
    100.0

Create the purchase request wrong rounding::

    >>> ctx = config.context
    >>> set_user(0)
    >>> pr_id, = PurchaseRequest.create([{
    ...             'product': product.id,
    ...             'quantity': 1001,
    ...             'unit': gr,
    ...             'warehouse': warehouse_loc.id,
    ...             }], ctx)
    >>> set_user()
    >>> purchase_request = PurchaseRequest(pr_id)

Create purchase::

    >>> create_purchase = Wizard(
    ...     'purchase.request.create_purchase', [purchase_request])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> purchase_request.state
    'purchased'

    >>> assertEqual(purchase_request.purchase_line.unit, gr)
    >>> purchase_request.purchase_line.quantity
    1050.0
