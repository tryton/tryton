================================
Marketing Campaign Sale Scenario
================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard

    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     ['marketing_campaign', 'sale', 'sale_opportunity'])

    >>> Category = Model.get('product.category')
    >>> Employee = Model.get('company.employee')
    >>> Opportunity = Model.get('sale.opportunity')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ReportingMain = Model.get('sale.reporting.main')
    >>> ReportingMarketing = Model.get('sale.reporting.marketing')
    >>> Sale = Model.get('sale.sale')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create employee::

    >>> employee = Employee(party=Party(name="Employee"))
    >>> employee.party.save()
    >>> employee.save()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create party::

    >>> customer = Party(name="Customer")
    >>> customer.save()

Create account category::

    >>> account_category = Category(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create an opportunity and convert to sale::

    >>> with config.set_context(
    ...         marketing_campaign='campaign',
    ...         marketing_medium='web',
    ...         ):
    ...     opportunity = Opportunity()
    >>> opportunity.employee = employee
    >>> opportunity.party = customer
    >>> opportunity.address, = customer.addresses
    >>> opportunity.amount = Decimal(100)
    >>> line = opportunity.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> opportunity.save()

    >>> opportunity.marketing_campaign.name
    'campaign'
    >>> opportunity.marketing_medium.name
    'web'
    >>> opportunity.marketing_source

    >>> opportunity.click('opportunity')
    >>> opportunity.state
    'opportunity'
    >>> opportunity.click('convert')
    >>> opportunity.state
    'converted'

Check and confirm sale::

    >>> sale, = opportunity.sales
    >>> sale.marketing_campaign.name
    'campaign'
    >>> sale.marketing_medium.name
    'web'
    >>> sale.marketing_source
    >>> sale.click('quote')
    >>> sale.click('confirm')

Create a second sale::

    >>> with config.set_context(
    ...         marketing_campaign='campaign',
    ...         marketing_medium='phone',
    ...         ):
    ...     sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.save()

    >>> sale.marketing_campaign.name
    'campaign'
    >>> sale.marketing_medium.name
    'phone'
    >>> sale.marketing_source

    >>> sale.click('quote')
    >>> sale.click('confirm')

Check sale reporting::

    >>> report, = ReportingMain.find([])
    >>> report.revenue == Decimal(110)
    True

    >>> with config.set_context(marketing_medium=sale.marketing_medium.id):
    ...     report, = ReportingMain.find([])
    >>> report.revenue == Decimal(10)
    True

    >>> report, = ReportingMarketing.find([])
    >>> report.revenue == Decimal(110)
    True
    >>> report.marketing_campaign
    >>> report.marketing_medium
    >>> report.marketing_source

    >>> with config.set_context(group_by_marketing_medium=True):
    ...     reports = ReportingMarketing.find([])
    >>> len(reports)
    2
    >>> sorted((r.marketing_medium.name, r.revenue) for r in reports) == (
    ...     [('phone', Decimal(10)), ('web', Decimal(100))])
    True

    >>> with config.set_context(
    ...         group_by_marketing_campaign=True,
    ...         group_by_marketing_medium=True,
    ...         ):
    ...     reports = ReportingMarketing.find([])
    >>> len(reports)
    2
    >>> sorted({r.marketing_campaign.name for r in reports})
    ['campaign']
    >>> sorted({r.marketing_medium.name for r in reports})
    ['phone', 'web']

    >>> with config.set_context(
    ...         group_by_marketing_campaign=True,
    ...         group_by_marketing_medium=False,
    ...         ):
    ...     report, = ReportingMarketing.find([])
