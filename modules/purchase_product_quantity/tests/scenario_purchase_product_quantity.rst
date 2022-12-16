==================================
Purchase Product Quantity Scenario
==================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules(
    ...     ['purchase_product_quantity', 'purchase_request'])
    >>> user = config.user

    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> PurchaseRequest = Model.get('purchase.request')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

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

    >>> set_user(0)
    >>> pr_id, = PurchaseRequest.create([{
    ...             'product': product.id,
    ...             'quantity': 30,
    ...             'uom': gr,
    ...             'warehouse': warehouse_loc.id,
    ...             'company': company.id,
    ...             }], config.context)
    >>> set_user(user)
    >>> purchase_request = PurchaseRequest(pr_id)

Create purchase::

    >>> create_purchase = Wizard(
    ...     'purchase.request.create_purchase',[purchase_request])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> purchase_request.state
    'purchased'

    >>> purchase_request.purchase_line.unit == gr
    True
    >>> purchase_request.purchase_line.quantity
    100.0

Create the purchase request wrong rounding::

    >>> set_user(0)
    >>> pr_id, = PurchaseRequest.create([{
    ...             'product': product.id,
    ...             'quantity': 1001,
    ...             'uom': gr,
    ...             'warehouse': warehouse_loc.id,
    ...             'company': company.id,
    ...             }], config.context)
    >>> set_user(user)
    >>> purchase_request = PurchaseRequest(pr_id)

Create purchase::

    >>> create_purchase = Wizard(
    ...     'purchase.request.create_purchase',[purchase_request])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> purchase_request.state
    'purchased'

    >>> purchase_request.purchase_line.unit == gr
    True
    >>> purchase_request.purchase_line.quantity
    1050.0
