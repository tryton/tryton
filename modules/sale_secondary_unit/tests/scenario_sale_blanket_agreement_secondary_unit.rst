==============================================
Sale Blanket Agreement Secondary Unit Scenario
==============================================

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
    ...     ['sale_secondary_unit', 'sale_blanket_agreement'],
    ...     create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> SaleBlanketAgreement = Model.get('sale.blanket_agreement')

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

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> gr, = ProductUom.find([('name', '=', 'Gram')])
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('10.000')
    >>> template.salable = True
    >>> template.account_category = account_category
    >>> template.sale_secondary_uom = gr
    >>> template.sale_secondary_uom_factor = 100
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('8.000')
    >>> product.save()

Create sale blanket agreement::

    >>> blanket_agreement = SaleBlanketAgreement()
    >>> blanket_agreement.customer = customer
    >>> blanket_agreement.from_date = today
    >>> blanket_agreement.to_date = later
    >>> blanket_agreement_line = blanket_agreement.lines.new()
    >>> blanket_agreement_line.product = product
    >>> blanket_agreement_line.quantity = 800.0
    >>> blanket_agreement_line.unit = gr
    >>> blanket_agreement_line.unit_price = Decimal('9.000')
    >>> blanket_agreement.click('run')
    >>> blanket_agreement.state
    'running'

Create sale from blanket agreement::

    >>> create_sale = blanket_agreement.click('create_sale')
    >>> assertEqual(create_sale.form.lines[0].unit, gr)
    >>> create_sale.execute('create_sale')

    >>> sale, = create_sale.actions[0]
    >>> line, = sale.lines
    >>> assertEqual(line.product, product)

    >>> assertEqual(line.secondary_unit, gr)
    >>> line.secondary_quantity
    800.0
    >>> line.secondary_unit_price
    Decimal('9.0000')

    >>> assertEqual(line.unit, unit)
    >>> line.quantity
    8.0
    >>> line.unit_price
    Decimal('900.0000')

    >>> line.secondary_quantity = 300.0
    >>> sale.save()

    >>> blanket_agreement.reload()
    >>> blanket_agreement_line, = blanket_agreement.lines
    >>> blanket_agreement_line.remaining_quantity
    800.0

Confirm sale::

    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

    >>> blanket_agreement_line.reload()
    >>> blanket_agreement_line.remaining_quantity
    500.0
