===================
Sale Extra Scenario
===================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     create_payment_term
    >>> today = datetime.date.today()

Configure::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install sale_extra::

    >>> Module = Model.get('ir.module')
    >>> module, = Module.find([
    ...         ('name', '=', 'sale_extra'),
    ...         ])
    >>> module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> config._context = User.get_preferences(True, config.context)

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

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
    >>> template.salable = True
    >>> template.lead_time = datetime.timedelta(0)
    >>> template.list_price = Decimal('20')
    >>> template.cost_price = Decimal('8')
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product.template = template
    >>> product.save()
    >>> extra_product = Product()
    >>> extra_template = ProductTemplate()
    >>> extra_template.name = 'Extra'
    >>> extra_template.default_uom = unit
    >>> extra_template.type = 'service'
    >>> extra_template.salable = True
    >>> extra_template.lead_time = datetime.timedelta(0)
    >>> extra_template.list_price = Decimal('3')
    >>> extra_template.cost_price = Decimal('3')
    >>> extra_template.account_revenue = revenue
    >>> extra_template.save()
    >>> extra_product.template = extra_template
    >>> extra_product.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create Extra::

    >>> PriceList = Model.get('product.price_list')
    >>> Extra = Model.get('sale.extra')
    >>> price_list = PriceList(name='Default')
    >>> price_list.save()
    >>> extra = Extra(name='Free Extra')
    >>> extra.price_list = price_list
    >>> line = extra.lines.new()
    >>> line.sale_amount = Decimal('100')
    >>> line.product = extra_product
    >>> line.quantity = 2
    >>> line.free = True
    >>> line = extra.lines.new()
    >>> line.sale_amount = Decimal('50')
    >>> line.product = extra_product
    >>> line.quantity = 1
    >>> extra.save()

Sale for 100, 2 free extra added::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.price_list = price_list
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> len(sale.lines)
    1
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> len(sale.lines)
    2
    >>> sum(l.quantity for l in sale.lines)
    7.0

Back to draft, nothing change::

    >>> sale.click('draft')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('100.00')
    >>> len(sale.lines)
    2

Sale for 60, 1 extra added::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.price_list = price_list
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 3
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('60.00')
    >>> len(sale.lines)
    1
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('63.00')
    >>> len(sale.lines)
    2

Sale for 20, nothing added::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.price_list = price_list
    >>> sale.payment_term = payment_term
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1
    >>> sale.save()
    >>> sale.untaxed_amount
    Decimal('20.00')
    >>> len(sale.lines)
    1
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('20.00')
    >>> len(sale.lines)
    1
