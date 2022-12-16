=======================================
Purchase Request For Quotation Scenario
=======================================

Imports::

    >>> import datetime
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)
    >>> today = datetime.date.today()

Activate purchase_request_quotation Module::

    >>> config = activate_modules(['purchase_request_quotation',
    ...     'purchase_requisition'])

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> expense = accounts['expense']

Create purchase user which is also in requisition approval group::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> purchase_user = User()
    >>> purchase_user.name = 'Purchase'
    >>> purchase_user.login = 'purchase'
    >>> purchase_user.main_company = company
    >>> purchase_group, = Group.find([('name', '=', 'Purchase')])
    >>> purchase_user.groups.append(purchase_group)
    >>> purchase_request_group, = Group.find(
    ...     [('name', '=', 'Purchase Request')])
    >>> purchase_user.groups.append(purchase_request_group)
    >>> requisition_group, = Group.find([
    ...         ('name', '=', 'Purchase Requisition')])
    >>> purchase_user.groups.append(requisition_group)
    >>> requisition_approval_group, = Group.find([
    ...         ('name', '=', 'Purchase Requisition Approval')])
    >>> purchase_user.groups.append(requisition_approval_group)
    >>> employee_party = Party(name='Employee')
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> purchase_user.employees.append(employee)
    >>> purchase_user.employee = employee
    >>> purchase_user.save()


Create suppliers::

    >>> supplier = Party(name='Supplier')
    >>> supplier.save()
    >>> supplier2 = Party(name='Supplier2')
    >>> supplier2.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20.000')
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product.template = template
    >>> product.cost_price = Decimal('8.000')
    >>> product.save()

Create purchase requisition::

    >>> set_user(purchase_user)
    >>> Location = Model.get('stock.location')
    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> PurchaseRequisition = Model.get('purchase.requisition')
    >>> requisition = PurchaseRequisition()
    >>> requisition.description = 'Description'
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> requisition_line = requisition.lines.new()
    >>> requisition_line.product = product
    >>> requisition_line.description = 'Description'
    >>> requisition_line.quantity = 2.0
    >>> requisition_line.supplier = supplier
    >>> requisition_line.unit_price = Decimal('10.0')
    >>> requisition.warehouse = warehouse_loc
    >>> requisition.click('wait')
    >>> requisition.click('approve')
    >>> requisition.state
    'processing'

Create Purchase Request Quotation from Purchase Request and
add another supplier::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> purchase_request, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> purchase_request.state
    'draft'
    >>> create_quotation = Wizard(
    ...     'purchase.request.quotation.create', [purchase_request])
    >>> [supplier] == create_quotation.form.suppliers
    True
    >>> create_quotation.form.suppliers.append(Party(supplier2.id))
    >>> create_quotation.execute('create_quotations')
    >>> create_quotation.execute('end')
    >>> purchase_request.state
    'quotation'

Check Quotation Lines (1 Request with 2 Suppliers = 2 Quotation Lines)::

    >>> QuotationLine = Model.get('purchase.request.quotation.line')
    >>> quotation_lines = QuotationLine.find(
    ...     [('quotation_state', '=', 'draft')])
    >>> len(quotation_lines)
    2

Send Quotations::

    >>> Quotation = Model.get('purchase.request.quotation')
    >>> quotations = Quotation.find([('state', '=', 'draft')])
    >>> len(quotations)
    2
    >>> for quotation in quotations:
    ...     quotation.click('send')
    >>> quotations = Quotation.find([('state', '=', 'sent')])
    >>> len(quotations)
    2

Create the report::

    >>> quotation = quotations[0]
    >>> quotation_report = Report('purchase.request.quotation')
    >>> ext, _, _, name = quotation_report.execute(quotations[:1], {})
    >>> ext
    'odt'
    >>> name
    'Purchase Request Quotation-1'

Suppliers will answer to quotation with their best unit price::

    >>> quotation, = Quotation.find([
    ...         ('state', '=', 'sent'),
    ...         ('supplier', '=', supplier.id)
    ...     ])
    >>> quotation.lines[0].unit_price = Decimal('11.000')
    >>> quotation.click('receive')
    >>> quotation, = Quotation.find([
    ...         ('state', '=', 'sent'),
    ...         ('supplier', '=', supplier2.id)
    ...     ])
    >>> quotation.lines[0].unit_price = Decimal('8.000')
    >>> quotation.click('receive')

Purchase Request state is now 'received'::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> prequest, = PurchaseRequest.find([('state', '=', 'received')])

Duplication of the Purchase Request and set the preferred_quotation_line field
with a quotation not having the minimum price unit::

    >>> prequest2, = prequest.duplicate()
    >>> prequest2.preferred_quotation_line = sorted(
    ...     prequest2.quotation_lines, key=lambda q: q.unit_price)[-1]
    >>> prequest2.preferred_quotation_line.unit_price
    Decimal('11.000')
    >>> prequest2.save()

Create Purchase Order from Purchase Request and check if supplier with
best price from quotations was selected (supplier2 price)::

    >>> create_purchase = Wizard('purchase.request.create_purchase', [prequest])
    >>> prequest.state
    'purchased'
    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase, = Purchase.find([
    ...         ('state', '=', 'draft'),
    ...         ])
    >>> purchase.party == supplier2
    True
    >>> purchase.lines[0].unit_price
    Decimal('8.000')

Create Purchase Order from Purchase Request having a preferred_quotation_line
and check if supplier from this quotation was selected::

    >>> create_purchase = Wizard('purchase.request.create_purchase',
    ...     [prequest2])
    >>> prequest2.state
    'purchased'
    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase, = Purchase.find([
    ...         ('state', '=', 'draft'),
    ...         ('party', '=', supplier)
    ...         ])
    >>> purchase.lines[0].unit_price
    Decimal('11.000')
