===============================
Sale Blanket Agreement Scenario
===============================

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
    ...     'sale_blanket_agreement', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> SaleBlanketAgreement = Model.get('sale.blanket_agreement')
    >>> Sale = Model.get('sale.sale')

Get accounts::

    >>> accounts = get_accounts()

Create customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()

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
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product1, = template.products
    >>> product1.cost_price = Decimal('8.000')
    >>> product1.save()

    >>> template = ProductTemplate()
    >>> template.name = 'Product2'
    >>> template.default_uom = kg
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.000')
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.save()
    >>> product2, = template.products
    >>> product2.cost_price = Decimal('8.000')
    >>> product2.save()

Create sale blanket agreement::

    >>> blanket_agreement = SaleBlanketAgreement()
    >>> blanket_agreement.customer = customer
    >>> blanket_agreement.from_date = today
    >>> blanket_agreement.to_date = later
    >>> blanket_agreement_line = blanket_agreement.lines.new()
    >>> blanket_agreement_line.product = product1
    >>> blanket_agreement_line.quantity = 20.0
    >>> blanket_agreement_line.unit = unit
    >>> blanket_agreement_line.unit_price = Decimal('9.0000')
    >>> blanket_agreement.click('run')
    >>> blanket_agreement.state
    'running'

Create sale from blanket agreement::

    >>> create_sale = blanket_agreement.click('create_sale')
    >>> len(create_sale.form.lines)
    1
    >>> create_sale.form.lines[0].remaining_quantity
    20.0
    >>> create_sale.execute('create_sale')
    >>> sale, = create_sale.actions[0]

    >>> line, = sale.lines
    >>> assertEqual(line.product, product1)
    >>> line.quantity
    20.0
    >>> line.unit_price
    Decimal('9.0000')
    >>> line.quantity = 5.0
    >>> line.save()

    >>> blanket_agreement.reload()
    >>> blanket_agreement_line, = blanket_agreement.lines
    >>> blanket_agreement_line.remaining_quantity
    20.0

Confirm sale::

    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
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

Try to sale more than remaining::


    >>> sale = Sale(party=customer)
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product1
    >>> sale_line.unit_price
    Decimal('10.0000')
    >>> sale_line.blanket_agreement_line = blanket_agreement_line
    >>> sale_line.quantity
    15.0
    >>> sale_line.unit_price
    Decimal('9.0000')
    >>> sale_line.quantity = 20
    >>> sale.click('quote')
    Traceback (most recent call last):
        ...
    BlanketAgreementQuantityWarning: ...

Sale remaining quantity::

    >>> sale_line, = sale.lines
    >>> sale_line.quantity = 15
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Close blanket agreement::

    >>> blanket_agreement.click('close')
    >>> blanket_agreement.state
    'closed'
