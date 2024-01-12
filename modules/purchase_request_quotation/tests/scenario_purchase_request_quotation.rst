=======================================
Purchase Request For Quotation Scenario
=======================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Report, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, set_user

    >>> today = dt.date.today()

Activate purchase_request_quotation Module::

    >>> config = activate_modules(
    ...     ['purchase_request_quotation', 'purchase_requisition'],
    ...     create_company, create_chart)

    >>> Employee = Model.get('company.employee')
    >>> Party = Model.get('party.party')
    >>> User = Model.get('res.user')

Set employee::

    >>> employee_party = Party(name="Employee")
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> user = User(config.user)
    >>> user.employees.append(employee)
    >>> user.employee = employee
    >>> user.save()
    >>> set_user(user.id)

Get accounts::

    >>> accounts = get_accounts()
    >>> expense = accounts['expense']

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
    >>> assertEqual(create_quotation.form.suppliers, [supplier])
    >>> create_quotation.form.suppliers.append(Party(supplier2.id))
    >>> create_quotation.execute('create_quotations')
    >>> quotations = create_quotation.actions[0]
    >>> len(quotations)
    2
    >>> purchase_request.state
    'quotation'

Check Quotation Lines (1 Request with 2 Suppliers = 2 Quotation Lines)::

    >>> len(quotations[0].lines), len(quotations[1].lines)
    (1, 1)

Send Quotations::

    >>> Quotation = Model.get('purchase.request.quotation')
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
    ...         ])
    >>> quotation.lines[0].unit_price = Decimal('11.000')
    >>> quotation.click('receive')
    >>> quotation, = Quotation.find([
    ...         ('state', '=', 'sent'),
    ...         ('supplier', '=', supplier2.id)
    ...         ])
    >>> quotation.lines[0].unit_price = Decimal('8.000')
    >>> quotation.click('receive')

Purchase Request state is now 'received'::

    >>> PurchaseRequest = Model.get('purchase.request')
    >>> prequest, = PurchaseRequest.find([('state', '=', 'received')])

Duplication of the Purchase Request and set the preferred_quotation_line field
with a quotation not having the minimum price unit::

    >>> set_user(0)
    >>> prequest2, = prequest.duplicate()
    >>> set_user()
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
    >>> assertEqual(purchase.party, supplier2)
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
