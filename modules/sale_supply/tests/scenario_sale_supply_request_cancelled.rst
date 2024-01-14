======================================
Sale Supply Request Cancelled Scenario
======================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('sale_supply')

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> Purchase = Model.get('purchase.purchase')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> Sale = Model.get('sale.sale')
    >>> UoM = Model.get('product.uom')

Create company::

    >>> _ = create_company()

Create chart of accounts::

    >>> _ = create_chart()
    >>> accounts = get_accounts()

Create parties::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()
    >>> customer = Party(name="Customer")
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.salable = True
    >>> template.list_price = Decimal('100.0000')
    >>> template.supply_on_sale = 'always'
    >>> product_supplier = template.product_suppliers.new()
    >>> product_supplier.party = supplier
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Sale product::

    >>> sale = Sale(party=customer)
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

    >>> shipment, = sale.shipments
    >>> shipment.state
    'waiting'
    >>> [m.state for m in shipment.moves]
    ['staging', 'staging']

Create purchase from request::

    >>> purchase_request, = PurchaseRequest.find()
    >>> create_purchase = Wizard(
    ...     'purchase.request.create_purchase', [purchase_request])

    >>> purchase_request.state
    'purchased'
    >>> shipment.reload()
    >>> [m.state for m in shipment.moves]
    ['staging', 'staging']

Cancel purchase::

    >>> purchase = purchase_request.purchase
    >>> purchase.click('cancel')
    >>> purchase.state
    'cancelled'

    >>> purchase_request.reload()
    >>> purchase_request.state
    'exception'
    >>> shipment.reload()
    >>> [m.state for m in shipment.moves]
    ['staging', 'staging']

Reset exception::

    >>> handle_purchase = purchase_request.click(
    ...     'handle_purchase_cancellation_exception')
    >>> handle_purchase.execute('reset')

    >>> purchase_request.state
    'draft'
    >>> shipment.reload()
    >>> [m.state for m in shipment.moves]
    ['staging', 'staging']

Cancel again purchase::

    >>> create_purchase = Wizard(
    ...     'purchase.request.create_purchase', [purchase_request])
    >>> purchase = purchase_request.purchase
    >>> purchase.click('cancel')
    >>> purchase.state
    'cancelled'

    >>> purchase_request.reload()
    >>> purchase_request.state
    'exception'
    >>> shipment.reload()
    >>> [m.state for m in shipment.moves]
    ['staging', 'staging']

Cancel request::

    >>> handle_purchase = purchase_request.click(
    ...     'handle_purchase_cancellation_exception')
    >>> handle_purchase.execute('cancel_request')
    >>> purchase_request.state
    'cancelled'

    >>> shipment.reload()
    >>> move, = shipment.moves
    >>> move.state
    'cancelled'
    >>> shipment.state
    'cancelled'

    >>> sale.reload()
    >>> sale.shipment_state
    'exception'
