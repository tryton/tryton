=========================
Sale Opportunity Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import config, Model, Wizard
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     create_payment_term

Create database::

    >>> config = config.set_trytond()
    >>> config.pool.test = True

Install sale_opportunity::

    >>> Module = Model.get('ir.module')
    >>> sale_opportunity_module, = Module.find([('name', '=', 'sale_opportunity')])
    >>> sale_opportunity_module.click('install')
    >>> Wizard('ir.module.install_upgrade').execute('upgrade')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Reload the context::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
    >>> config._context = User.get_preferences(True, config.context)

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create sale opportunity user::

    >>> sale_opportunity_user = User()
    >>> sale_opportunity_user.name = 'Sale Opportunity'
    >>> sale_opportunity_user.login = 'sale_opportunity'
    >>> sale_opportunity_user.main_company = company
    >>> sale_opportunity_group, = Group.find(
    ...     [('name', '=', 'Sale Opportunity')])
    >>> sale_opportunity_user.groups.append(sale_opportunity_group)

    >>> Employee = Model.get('company.employee')
    >>> Party = Model.get('party.party')
    >>> employee_party = Party(name='Employee')
    >>> employee_party.save()
    >>> employee = Employee(party=employee_party)
    >>> employee.save()
    >>> sale_opportunity_user.employees.append(employee)
    >>> sale_opportunity_user.employee = employee

    >>> sale_opportunity_user.save()

Create sale user::

    >>> sale_user = User()
    >>> sale_user.name = 'Sale'
    >>> sale_user.login = 'sale'
    >>> sale_user.main_company = company
    >>> sale_group, = Group.find([('name', '=', 'Sales')])
    >>> sale_user.groups.append(sale_group)
    >>> sale_user.save()

Create party::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> product = Product()
    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.cost_price = Decimal('5')
    >>> template.cost_price_method = 'fixed'
    >>> template.account_revenue = revenue
    >>> template.save()
    >>> product.template = template
    >>> product.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create an lead::

    >>> config.user = sale_opportunity_user.id
    >>> Opportunity = Model.get('sale.opportunity')
    >>> opportunity = Opportunity()
    >>> opportunity.description = 'Opportunity'
    >>> opportunity.save()
    >>> opportunity.state
    u'lead'

Convert to opportunity::

    >>> opportunity.party = customer
    >>> opportunity.address, = customer.addresses
    >>> opportunity.payment_term = payment_term
    >>> opportunity.amount = Decimal(100)
    >>> opportunity.click('opportunity')
    >>> opportunity.state
    u'opportunity'

Add a line::

    >>> line = opportunity.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> opportunity.save()

Convert to sale::

    >>> opportunity.click('convert')
    >>> opportunity.state
    u'converted'

Find the sale::

    >>> config.user = sale_user.id
    >>> Sale = Model.get('sale.sale')
    >>> sale, = Sale.find(
    ...     [('origin', '=', 'sale.opportunity,%s' % opportunity.id)])
    >>> line, = sale.lines
    >>> line.product == product
    True
    >>> line.quantity
    10.0

Quote different quantity::

    >>> line.quantity = 9
    >>> sale.click('quote')

Check opportunity amount updated::

    >>> config.user = sale_opportunity_user.id
    >>> opportunity.reload()
    >>> opportunity.amount
    Decimal('90.00')
    >>> opportunity.state
    u'converted'

Add a second quotation::

    >>> config.user = sale_user.id
    >>> second_sale = Sale()
    >>> second_sale.origin = opportunity
    >>> second_sale.party = customer
    >>> second_sale.payment_term = payment_term
    >>> line = second_sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> second_sale.click('quote')

Check opportunity amount updated::

    >>> config.user = sale_opportunity_user.id
    >>> opportunity.reload()
    >>> opportunity.amount
    Decimal('100.00')
    >>> opportunity.state
    u'converted'

Cancel second quotation::

    >>> config.user = sale_user.id
    >>> second_sale.click('cancel')
    >>> second_sale.state
    u'cancel'

Check opportunity amount updated::

    >>> config.user = sale_opportunity_user.id
    >>> opportunity.reload()
    >>> opportunity.amount
    Decimal('90.00')
    >>> opportunity.state
    u'converted'

Won opportunity::

    >>> config.user = sale_user.id
    >>> sale.click('confirm')
    >>> config.user = sale_opportunity_user.id
    >>> opportunity.reload()
    >>> opportunity.state
    u'won'

Check opportunity state updated::

    >>> config.user = sale_opportunity_user.id
    >>> opportunity.reload()
    >>> opportunity.state
    u'won'
