=============================
Purchase Requisition Scenario
=============================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()

Activate purchase_requisition Module::

    >>> config = activate_modules('purchase_requisition', create_company, create_chart)

    >>> Employee = Model.get('company.employee')
    >>> Party = Model.get('party.party')

Create employee::

    >>> employee_party = Party(name="Employee")
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()

Get accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']

Create supplier::

    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> supplier2 = Party(name='Supplier2')
    >>> supplier2.save()

Set default account::

    >>> Configuration = Model.get('account.configuration')
    >>> config = Configuration(1)
    >>> config.default_category_account_expense = expense
    >>> config.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> template.save()
    >>> product, = template.products

Create purchase requisition without product and description::

    >>> PurchaseRequisition = Model.get('purchase.requisition')
    >>> requisition = PurchaseRequisition()
    >>> requisition.description = 'Description'
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.product = None
    >>> requisition_line.description = None
    >>> requisition_line.supplier = supplier
    >>> requisition_line.unit_price = Decimal('10')
    >>> requisition.click('wait')
    Traceback (most recent call last):
        ...
    RequiredValidationError: ...

Create purchase requisition without product and quantity::

    >>> requisition_line.description = 'Description'
    >>> requisition.click('wait')
    Traceback (most recent call last):
        ...
    RequiredValidationError: ...

Create purchase requisition with product goods and without warehouse::

    >>> requisition.warehouse = None
    >>> requisition_line.product = product
    >>> requisition_line.description = 'Requisition Test'
    >>> requisition_line.quantity = 2.0
    >>> requisition.click('wait')
    Traceback (most recent call last):
        ...
    RequiredValidationError: ...

Create purchase requisition with supplier and price::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> requisition.warehouse = warehouse_loc
    >>> requisition.click('wait')
    >>> requisition.state
    'waiting'

Approve workflow with user in approval_group::

    >>> requisition.click('approve')
    >>> requisition.state
    'processing'
    >>> requisition.total_amount
    Decimal('20.00')

Create Purchase order from Request::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> pr.state
    'draft'
    >>> assertEqual(pr.product, product)
    >>> assertEqual(pr.party, supplier)
    >>> pr.quantity
    2.0
    >>> pr.computed_quantity
    2.0
    >>> assertEqual(pr.supply_date, today)
    >>> assertEqual(pr.warehouse, warehouse_loc)
    >>> create_purchase = Wizard('purchase.request.create_purchase', [pr])
    >>> pr.state
    'purchased'
    >>> requisition.state
    'processing'

Cancel the purchase order::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> purchase.click('cancel')
    >>> purchase.state
    'cancelled'
    >>> pr.reload()
    >>> pr.state
    'exception'
    >>> requisition.reload()
    >>> requisition.state
    'processing'

Handle request exception::

    >>> handle_exception = Wizard(
    ...     'purchase.request.handle.purchase.cancellation', [pr])
    >>> handle_exception.execute('reset')
    >>> pr.state
    'draft'
    >>> requisition.reload()
    >>> requisition.state
    'processing'
    >>> create_purchase = Wizard('purchase.request.create_purchase', [pr])
    >>> pr.state
    'purchased'
    >>> requisition.reload()
    >>> requisition.state
    'done'

Confirm the purchase order::

    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> purchase_line, = purchase.lines
    >>> purchase_line.unit_price
    Decimal('10.0000')
    >>> purchase.click('quote')
    >>> requisition.reload()
    >>> requisition.state
    'done'
    >>> purchase.click('confirm')
    >>> purchase.reload()
    >>> purchase.state
    'processing'
    >>> requisition.reload()
    >>> requisition.state
    'done'

Try to delete requisition done::

    >>> PurchaseRequisition.delete([requisition])
    Traceback (most recent call last):
        ...
    AccessError: ...

Delete draft requisition::

    >>> requisition = PurchaseRequisition()
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition.save()
    >>> PurchaseRequisition.delete([requisition])

Create purchase requisition with two different suppliers::

    >>> requisition = PurchaseRequisition()
    >>> requisition.description = 'Description'
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.description = 'Description'
    >>> requisition_line.quantity = 4.0
    >>> requisition_line.supplier = supplier
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.description = 'Description2'
    >>> requisition_line.quantity = 2.0
    >>> requisition_line.supplier = supplier2
    >>> requisition.click('wait')

    >>> requisition.click('approve')

    >>> pr = PurchaseRequest.find([('state', '=', 'draft')])
    >>> len(pr)
    2
    >>> assertEqual(pr[0].party, supplier2)
    >>> assertEqual(pr[1].party, supplier)
    >>> create_purchase = Wizard('purchase.request.create_purchase', pr)
    >>> purchase, = Purchase.find([
    ...         ('state', '=', 'draft'),
    ...         ('party', '=', supplier.id),
    ...         ])
    >>> purchase.click('cancel')
    >>> requisition.reload()
    >>> requisition.state
    'processing'
    >>> purchase, = Purchase.find([
    ...         ('state', '=', 'draft'),
    ...         ('party', '=', supplier2.id),
    ...         ])
    >>> purchase_line, = purchase.lines
    >>> purchase_line.unit_price = Decimal('8.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> requisition.reload()
    >>> requisition.state
    'processing'
    >>> pr = pr[1]
    >>> pr.state
    'exception'
    >>> handle_exception = Wizard(
    ...     'purchase.request.handle.purchase.cancellation', [pr])
    >>> handle_exception.execute('cancel_request')
    >>> pr.state
    'cancelled'
    >>> requisition.reload()
    >>> requisition.state
    'done'

Create purchase requisition then cancel::

    >>> requisition = PurchaseRequisition()
    >>> requisition.description = 'Description'
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.description = 'Description'
    >>> requisition_line.quantity = 4.0
    >>> requisition.click('cancel')
    >>> requisition.state
    'cancelled'

Create purchase requisition, wait then reject::

    >>> requisition = PurchaseRequisition()
    >>> requisition.description = 'Description'
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.description = 'Description'
    >>> requisition_line.quantity = 4.0
    >>> requisition.click('wait')
    >>> requisition.state
    'waiting'

    >>> requisition.click('reject')
    >>> requisition.state
    'rejected'
