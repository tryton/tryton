===========================
Purchase Amendment Scenario
===========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences

Activate modules::

    >>> config = activate_modules('purchase_amendment')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create parties::

    >>> Party = Model.get('party.party')
    >>> supplier1 = Party(name="Supplier 1")
    >>> supplier1.save()
    >>> supplier2 = Party(name="Supplier 2")
    >>> supplier2.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> _ = template.products.new()
    >>> template.save()
    >>> product1, product2 = template.products

Purchase first product::

    >>> Purchase = Model.get('purchase.purchase')
    >>> purchase = Purchase()
    >>> purchase.party = supplier1
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product1
    >>> purchase_line.quantity = 5.0
    >>> purchase_line.unit_price = Decimal('10.0000')
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.quantity = 1
    >>> purchase_line.unit_price = Decimal('5.0000')
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'
    >>> purchase.revision
    0
    >>> purchase.total_amount
    Decimal('55.00')
    >>> len(purchase.moves), len(purchase.invoices)
    (1, 1)

Add an amendment::

    >>> amendment = purchase.amendments.new()
    >>> line = amendment.lines.new()
    >>> line.action = 'taxes'
    >>> line = amendment.lines.new()
    >>> line.action = 'payment_term'
    >>> line = amendment.lines.new()
    >>> line.action = 'party'
    >>> line.party == supplier1
    True
    >>> line.party = supplier2
    >>> line = amendment.lines.new()
    >>> line.action = 'warehouse'
    >>> bool(line.warehouse)
    True
    >>> line = amendment.lines.new()
    >>> line.action = 'line'
    >>> line.line = purchase.lines[0]
    >>> line.product == product1
    True
    >>> line.product = product2
    >>> line.quantity
    5.0
    >>> line.quantity = 4.0
    >>> line.unit_price
    Decimal('10.0000')
    >>> line.unit_price = Decimal('9.0000')
    >>> line = amendment.lines.new()
    >>> line.action = 'line'
    >>> line.line = purchase.lines[1]
    >>> line.product
    >>> line.quantity = 2
    >>> amendment.save()

Validate amendment::

    >>> amendment.click('validate_amendment')
    >>> purchase.reload()
    >>> purchase.revision
    1
    >>> purchase.party == supplier2
    True
    >>> line = purchase.lines[0]
    >>> line.product == product2
    True
    >>> line.quantity
    4.0
    >>> line.unit_price
    Decimal('9.0000')
    >>> line = purchase.lines[1]
    >>> line.quantity
    2.0
    >>> purchase.total_amount
    Decimal('46.00')

    >>> move, = purchase.moves
    >>> move.product == product2
    True
    >>> move.quantity
    4.0

    >>> invoice, = purchase.invoices
    >>> line = invoice.lines[0]
    >>> line.product == product2
    True
    >>> line.quantity
    4.0
    >>> line.unit_price
    Decimal('9.0000')
    >>> line = invoice.lines[1]
    >>> line.product
    >>> line.quantity
    2.0
    >>> line.unit_price
    Decimal('5.0000')
