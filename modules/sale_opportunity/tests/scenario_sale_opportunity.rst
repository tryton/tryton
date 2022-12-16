=========================
Sale Opportunity Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules, set_user
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_chart, \
    ...     get_accounts
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     create_payment_term

Activate modules::

    >>> config = activate_modules('sale_opportunity')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)
    >>> revenue = accounts['revenue']

Create sale opportunity user::

    >>> User = Model.get('res.user')
    >>> Group = Model.get('res.group')
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

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create an lead::

    >>> set_user(sale_opportunity_user)
    >>> Opportunity = Model.get('sale.opportunity')
    >>> opportunity = Opportunity()
    >>> opportunity.description = 'Opportunity'
    >>> opportunity.save()
    >>> opportunity.state
    'lead'

Convert to opportunity::

    >>> opportunity.party = customer
    >>> opportunity.address, = customer.addresses
    >>> opportunity.payment_term = payment_term
    >>> opportunity.amount = Decimal(100)
    >>> opportunity.employee = employee
    >>> opportunity.click('opportunity')
    >>> opportunity.state
    'opportunity'

Add a line::

    >>> line = opportunity.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> opportunity.save()

Convert to sale::

    >>> opportunity.click('convert')
    >>> opportunity.state
    'converted'

Find the sale::

    >>> set_user(sale_user)
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

    >>> set_user(sale_opportunity_user)
    >>> opportunity.reload()
    >>> opportunity.amount
    Decimal('90.00')
    >>> opportunity.state
    'converted'

Add a second quotation::

    >>> set_user(sale_user)
    >>> second_sale = Sale()
    >>> second_sale.origin = opportunity
    >>> second_sale.party = customer
    >>> second_sale.payment_term = payment_term
    >>> line = second_sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> second_sale.click('quote')

Check opportunity amount updated::

    >>> set_user(sale_opportunity_user)
    >>> opportunity.reload()
    >>> opportunity.amount
    Decimal('100.00')
    >>> opportunity.state
    'converted'

Cancel second quotation::

    >>> set_user(sale_user)
    >>> second_sale.click('cancel')
    >>> second_sale.state
    'cancelled'

Check opportunity amount updated::

    >>> set_user(sale_opportunity_user)
    >>> opportunity.reload()
    >>> opportunity.amount
    Decimal('90.00')
    >>> opportunity.state
    'converted'

Won opportunity::

    >>> set_user(sale_user)
    >>> sale.click('confirm')
    >>> set_user(sale_opportunity_user)
    >>> opportunity.reload()
    >>> opportunity.state
    'won'

Check opportunity state updated::

    >>> set_user(sale_opportunity_user)
    >>> opportunity.reload()
    >>> opportunity.state
    'won'
