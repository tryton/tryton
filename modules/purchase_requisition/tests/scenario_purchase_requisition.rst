=============================
Purchase Requisition Scenario
=============================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import (create_company,
    ...     get_company)
    >>> from trytond.modules.account.tests.tools import (create_chart,
    ...     get_accounts)
    >>> today = datetime.date.today()

Activate purchase_requisition Module::

    >>> config = activate_modules(['purchase_requisition'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']

Create purchase requisition user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> requisition_user = User()
    >>> requisition_user.name = 'Requisition'
    >>> requisition_user.login = 'requisition'
    >>> requisition_user.main_company = company
    >>> requisition_group, = Group.find([
    ...         ('name', '=', 'Purchase Requisition')])
    >>> requisition_user.groups.append(requisition_group)
    >>> employee_party = Party(name='Employee')
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> requisition_user.employees.append(employee)
    >>> requisition_user.employee = employee
    >>> requisition_user.save()

    >>> party_approval, = Party.duplicate([employee_party],  {
    ...         'name': 'Employee Approval',
    ...         })
    >>> employee_approval, = Employee.duplicate([employee], {
    ...         'party': party_approval.id,
    ...         })
    >>> requisition_approval_user, = User.duplicate([requisition_user], {
    ...         'name': 'Requisition Approval',
    ...         'login': 'requisition_approval',
    ...         })
    >>> requisition_approval_group, = Group.find([
    ...         ('name', '=', 'Purchase Requisition Approval')])
    >>> requisition_approval_user.groups.append(requisition_approval_group)
    >>> _ = requisition_approval_user.employees.pop()
    >>> requisition_approval_user.employees.append(employee_approval)
    >>> requisition_approval_user.employee = employee_approval
    >>> requisition_approval_user.save()

Create purchase user::

    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_user.main_company = company
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_request_group, = Group.find(
    ...     [('name', '=', 'Purchase Request')])
    >>> purchase_user.groups.append(purchase_request_group)
    >>> purchase_user.save()


Create supplier::

    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> supplier2 = Party(name='Supplier2')
    >>> supplier2.save()

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
    >>> template.account_expense = expense
    >>> product, = template.products
    >>> product.cost_price = Decimal('8')
    >>> template.save()
    >>> product, = template.products

Create purchase requisition without product and description::

    >>> set_user(requisition_user)
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
    >>> requisition.click('wait')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Create purchase requisition without product and quantity::

    >>> requisition_line.description = 'Description'
    >>> requisition.click('wait')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Create purchase requisition with product goods and without warehouse::

    >>> requisition.warehouse = None
    >>> requisition_line.product = product
    >>> requisition_line.description = 'Requisition Test'
    >>> requisition_line.quantity = 2.0
    >>> requisition.click('wait')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Create purchase requisition with supplier and price::

    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> requisition.warehouse = warehouse_loc
    >>> requisition.click('wait')
    >>> requisition.state
    u'waiting'

Approve workflow by requisition user raise an exception because he's not in
approval_group::

    >>> set_user(requisition_user)
    >>> requisition.click('approve')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Approve workflow by purchaser raise an exception because he's not in
approval_group::

    >>> set_user(purchase_user)
    >>> requisition.click('approve')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Approve workflow with user in approval_group::

    >>> set_user(requisition_approval_user)
    >>> requisition.click('approve')
    >>> requisition.state
    u'processing'
    >>> requisition.total_amount
    Decimal('20.00')

Create Purchase order from Request::

    >>> set_user(purchase_user)
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> pr, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> pr.state
    u'draft'
    >>> pr.product == product
    True
    >>> pr.party == supplier
    True
    >>> pr.quantity
    2.0
    >>> pr.computed_quantity
    2.0
    >>> pr.supply_date == today
    True
    >>> pr.warehouse == warehouse_loc
    True
    >>> create_purchase = Wizard('purchase.request.create_purchase', [pr])
    >>> pr.state
    u'purchased'
    >>> requisition.state
    u'processing'

Cancel the purchase order::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> purchase.click('cancel')
    >>> purchase.state
    u'cancel'
    >>> pr.reload()
    >>> pr.state
    u'exception'
    >>> requisition.reload()
    >>> requisition.state
    u'done'

Handle request exception::

    >>> handle_exception = Wizard(
    ...     'purchase.request.handle.purchase.cancellation', [pr])
    >>> handle_exception.execute('reset')
    >>> pr.state
    u'draft'
    >>> requisition.reload()
    >>> requisition.state
    u'processing'
    >>> create_purchase = Wizard('purchase.request.create_purchase', [pr])
    >>> pr.state
    u'purchased'
    >>> requisition.reload()
    >>> requisition.state
    u'processing'

Confirm the purchase order::

    >>> purchase, = Purchase.find([('state', '=', 'draft')])
    >>> purchase.click('quote')
    >>> requisition.reload()
    >>> requisition.state
    u'processing'
    >>> purchase.click('confirm')
    >>> purchase.reload()
    >>> purchase.state
    u'confirmed'
    >>> requisition.reload()
    >>> requisition.state
    u'done'

Try to delete requisition done::

    >>> set_user(requisition_user)
    >>> PurchaseRequisition.delete([requisition])  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    UserError: ...

Delete draft requisition::

    >>> requisition = PurchaseRequisition()
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition.save()
    >>> PurchaseRequisition.delete([requisition])

Create purchase requisition with two different suppliers::

    >>> set_user(requisition_user)
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

    >>> set_user(requisition_approval_user)
    >>> requisition.click('approve')

    >>> set_user(purchase_user)
    >>> pr = PurchaseRequest.find([('state', '=', 'draft')])
    >>> len(pr)
    2
    >>> pr[0].party == supplier2
    True
    >>> pr[1].party == supplier
    True
    >>> create_purchase = Wizard('purchase.request.create_purchase', pr)
    >>> purchase, = Purchase.find([
    ...         ('state', '=', 'draft'),
    ...         ('party', '=', supplier.id),
    ...         ])
    >>> purchase.click('cancel')
    >>> requisition.reload()
    >>> requisition.state
    u'processing'
    >>> purchase, = Purchase.find([
    ...         ('state', '=', 'draft'),
    ...         ('party', '=', supplier2.id),
    ...         ])
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> requisition.reload()
    >>> requisition.state
    u'done'

Create purchase requisition then cancel::

    >>> set_user(requisition_user)
    >>> requisition = PurchaseRequisition()
    >>> requisition.description = 'Description'
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.description = 'Description'
    >>> requisition_line.quantity = 4.0
    >>> requisition.click('cancel')
    >>> requisition.state
    u'cancel'

Create purchase requisition, wait then reject::

    >>> set_user(requisition_user)
    >>> requisition = PurchaseRequisition()
    >>> requisition.description = 'Description'
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.description = 'Description'
    >>> requisition_line.quantity = 4.0
    >>> requisition.click('wait')
    >>> requisition.state
    u'waiting'

    >>> set_user(requisition_approval_user)
    >>> requisition.click('reject')
    >>> requisition.state
    u'rejected'
