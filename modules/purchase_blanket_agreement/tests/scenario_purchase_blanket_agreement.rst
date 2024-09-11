===================================
Purchase Blanket Agreement Scenario
===================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> today = dt.date.today()
    >>> later = today + dt.timedelta(days=30)


Activate modules::

    >>> config = activate_modules(
    ...     'purchase_blanket_agreement', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> PurchaseBlanketAgreement = Model.get('purchase.blanket_agreement')
    >>> Purchase = Model.get('purchase.purchase')

Get accounts::

    >>> accounts = get_accounts()

Create supplier::

    >>> supplier = Party(name="Supplier")
    >>> supplier.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> kg, = ProductUom.find([('name', '=', 'Kilogram')])
    >>> template = ProductTemplate()
    >>> template.name = 'Product1'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.000')
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> product_supplier = template.product_suppliers.new(party=supplier)
    >>> ps_price = product_supplier.prices.new()
    >>> ps_price.unit_price = Decimal('8.0000')
    >>> template.save()
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('8.000')
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = 'Product2'
    >>> template.default_uom = kg
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.000')
    >>> template.purchasable = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('8.000')
    >>> product2.save()

Create purchase blanket agreement::

    >>> blanket_agreement = PurchaseBlanketAgreement()
    >>> blanket_agreement.supplier = supplier
    >>> blanket_agreement.from_date = today
    >>> blanket_agreement.to_date = later
    >>> blanket_agreement_line = blanket_agreement.lines.new()
    >>> blanket_agreement_line.product = product1
    >>> blanket_agreement_line.quantity = 20.0
    >>> blanket_agreement_line.unit = unit
    >>> blanket_agreement_line.unit_price = Decimal('7.0000')
    >>> blanket_agreement.click('run')
    >>> blanket_agreement.state
    'running'

Create purchase from blanket agreement::

    >>> create_purchase = blanket_agreement.click('create_purchase')
    >>> len(create_purchase.form.lines)
    1
    >>> create_purchase.form.lines[0].remaining_quantity
    20.0
    >>> create_purchase.execute('create_purchase')
    >>> purchase, = create_purchase.actions[0]

    >>> line, = purchase.lines
    >>> assertEqual(line.product, product1)
    >>> line.quantity
    20.0
    >>> line.unit_price
    Decimal('7.0000')
    >>> line.quantity = 5.0
    >>> line.save()

    >>> blanket_agreement.reload()
    >>> blanket_agreement_line, = blanket_agreement.lines
    >>> blanket_agreement_line.remaining_quantity
    20.0

Confirm purchase::

    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

    >>> blanket_agreement_line.reload()
    >>> blanket_agreement_line.remaining_quantity
    15.0

Try to change product with incompatible unit::

    >>> blanket_agreement.click('draft')
    >>> line, = blanket_agreement.lines
    >>> line.product = product2
    >>> blanket_agreement.save()
    Traceback (most recent call last):
        ...
    UOMValidationError: ...

    >>> blanket_agreement.reload()
    >>> blanket_agreement.click('run')

Try to close blanket agreement with remaining quantity::

    >>> blanket_agreement.click('close')
    Traceback (most recent call last):
        ...
    BlanketAgreementClosingWarning: ...

Try to purchase more than remaining::

    >>> purchase = Purchase(party=supplier)
    >>> purchase_line = purchase.lines.new()
    >>> purchase_line.product = product1
    >>> purchase_line.unit_price
    Decimal('8.0000')
    >>> purchase_line.blanket_agreement_line = blanket_agreement_line
    >>> purchase_line.quantity
    15.0
    >>> purchase_line.unit_price
    Decimal('7.0000')
    >>> purchase_line.quantity = 20
    >>> purchase.click('quote')
    Traceback (most recent call last):
        ...
    BlanketAgreementQuantityWarning: ...

Purchase remaining quantity::

    >>> purchase_line, = purchase.lines
    >>> purchase_line.quantity = 15
    >>> purchase.click('quote')
    >>> purchase.click('confirm')
    >>> purchase.state
    'processing'

Close blanket agreement::

    >>> blanket_agreement.click('close')
    >>> blanket_agreement.state
    'closed'
