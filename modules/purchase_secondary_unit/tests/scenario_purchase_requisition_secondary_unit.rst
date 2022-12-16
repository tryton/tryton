============================================
Purchase Requisition Secondary Unit Scenario
============================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules([
    ...         'purchase_secondary_unit',
    ...         'purchase_request',
    ...         'purchase_requisition'])

    >>> Employee = Model.get('company.employee')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> PurchaseRequest = Model.get('purchase.request')
    >>> PurchaseRequisition = Model.get('purchase.requisition')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create employee::

    >>> party = Party(name="Employee")
    >>> party.save()
    >>> employee = Employee(party=party)
    >>> employee.save()

Create supplier::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> kg, = ProductUom.find([('name', '=', "Kilogram")])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> template.purchase_secondary_uom = kg
    >>> template.purchase_secondary_uom_factor = 2
    >>> product, = template.products
    >>> template.save()
    >>> product, = template.products

Create a purchase requisition using secondary unit::

    >>> requisition = PurchaseRequisition()
    >>> requisition.employee = employee
    >>> requisition.supply_date = today
    >>> line = requisition.lines.new()
    >>> line.product = product
    >>> line.unit = kg
    >>> line.quantity = 6
    >>> line.unit_price = Decimal('100.0000')
    >>> requisition.click('wait')
    >>> requisition.click('approve')
    >>> requisition.state
    'processing'

Create Purchase order from Request::

    >>> request, = PurchaseRequest.find([('state', '=', 'draft')])
    >>> create_purchase = Wizard('purchase.request.create_purchase', [request])
    >>> create_purchase.form.party = supplier
    >>> create_purchase.execute('start')
    >>> request.state
    'purchased'
    >>> request.purchase_line.unit == unit
    True
    >>> request.purchase_line.quantity
    3.0
    >>> request.purchase_line.unit_price
    Decimal('200.0000')
