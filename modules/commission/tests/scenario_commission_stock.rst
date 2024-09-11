=========================
Commission Stock Scenario
=========================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules(
    ...     ['commission', 'sale', 'stock', 'account_invoice_stock'],
    ...     create_company, create_chart)

    >>> Agent = Model.get('commission.agent')
    >>> Commission = Model.get('commission')
    >>> MarginProduct = Model.get('stock.reporting.margin.product')
    >>> Party = Model.get('party.party')
    >>> Plan = Model.get('commission.plan')
    >>> ProductCategory = Model.get('product.category')
    >>> Sale = Model.get('sale.sale')
    >>> Template = Model.get('product.template')
    >>> Uom = Model.get('product.uom')

Get company::

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(today=(yesterday, today)))
    >>> fiscalyear.click('create_period')

Get accounts::

    >>> accounts = get_accounts()

Create customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create commission product::

    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> template = Template()
    >>> template.name = 'Commission'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.account_category = account_category
    >>> template.save()
    >>> commission_product, = template.products

Create commission plans::

    >>> plan1 = Plan(name='Plan 1')
    >>> plan1.commission_product = commission_product
    >>> plan1.commission_method = 'posting'
    >>> line = plan1.lines.new()
    >>> line.formula = 'amount * 0.1'
    >>> plan1.save()

    >>> plan2 = Plan(name='Plan 2')
    >>> plan2.commission_product = commission_product
    >>> plan2.commission_method = 'posting'
    >>> line = plan2.lines.new()
    >>> line.formula = 'amount * 0.05'
    >>> plan2.save()

Create agent::

    >>> agent_party = Party(name='Agent')
    >>> agent_party.save()
    >>> agent = Agent(party=agent_party)
    >>> agent.type_ = 'agent'
    >>> agent.plan = plan1
    >>> agent.currency = company.currency
    >>> agent.save()

Create principal::

    >>> principal_party = Party(name='Principal')
    >>> principal_party.save()
    >>> principal = Agent(party=principal_party)
    >>> principal.type_ = 'principal'
    >>> principal.plan = plan2
    >>> principal.currency = company.currency
    >>> principal.save()

Create product sold::

    >>> template = Template()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('100.0000')
    >>> template.account_category = account_category
    >>> template.principals.append(principal)
    >>> template.save()
    >>> product, = template.products
    >>> product.cost_price = Decimal('50.0000')
    >>> product.save()

Create a sale::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.agent = agent
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 5
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

Ship in two steps::

    >>> shipment, = sale.shipments
    >>> move, = shipment.inventory_moves
    >>> move.quantity = 3
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> sale.reload()
    >>> _, shipment = sale.shipments
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

Post the invoice::

    >>> invoice, = sale.invoices
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check stock move::

    >>> shipment, _ = sale.shipments
    >>> move, = shipment.outgoing_moves
    >>> move.commission_price
    Decimal('-5.0000')

Check reporting margin::

    >>> context = {
    ...     'from_date': yesterday,
    ...     'to_date': today,
    ...     'period': 'day',
    ...     }
    >>> with config.set_context(context=context):
    ...     report, = MarginProduct.find([])
    >>> report.cost
    Decimal('250.00')
    >>> report.revenue
    Decimal('500.00')

    >>> context['include_commission'] = True
    >>> with config.set_context(context=context):
    ...     report, = MarginProduct.find([])
    >>> report.cost
    Decimal('275.00')
    >>> report.revenue
    Decimal('500.00')

Update commission amount::

    >>> commission, = Commission.find([('agent.type_', '=', 'agent')])
    >>> commission.amount = Decimal('60.0000')

Create commission invoice::

    >>> commission.click('invoice')

Check stock move::

    >>> move.reload()
    >>> move.commission_price
    Decimal('-7.0000')
