=========================================
Commission Credit Posted Invoice Scenario
=========================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules('commission', create_company, create_chart)

    >>> Agent = Model.get('commission.agent')
    >>> Commission = Model.get('commission')
    >>> Invoice = Model.get('account.invoice')
    >>> Party = Model.get('party.party')
    >>> Plan = Model.get('commission.plan')
    >>> ProductCategory = Model.get('product.category')
    >>> Template = Model.get('product.template')
    >>> Uom = Model.get('product.uom')

Get company::

    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear())
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

Create commission plan::

    >>> plan = Plan(name='Plan')
    >>> plan.commission_product = commission_product
    >>> plan.commission_method = 'payment'
    >>> line = plan.lines.new()
    >>> line.formula = 'amount * 0.1'
    >>> plan.save()

Create agent::

    >>> agent_party = Party(name='Agent')
    >>> agent_party.save()
    >>> agent = Agent(party=agent_party)
    >>> agent.type_ = 'agent'
    >>> agent.plan = plan
    >>> agent.currency = company.currency
    >>> agent.save()

Create product sold::

    >>> template = Template()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(100)
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create invoice and credit it before paying::

    >>> invoice = Invoice()
    >>> invoice.party = customer
    >>> invoice.agent = agent
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(100)
    >>> invoice.click('post')
    >>> line, = invoice.lines
    >>> commission, = line.commissions
    >>> bool(commission.date)
    False
    >>> commission.amount
    Decimal('10.0000')
    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.execute('credit')
    >>> credit_note, = credit.actions[0]
    >>> credit_note.state = 'paid'
    >>> credit_line, = credit_note.lines
    >>> credit_commission, = Commission.find([
    ...     ('id', '!=', commission.id),
    ...     ])
    >>> bool(credit_commission.date)
    True
    >>> credit_commission.amount
    Decimal('-10.0000')
    >>> commission.reload()
    >>> bool(commission.date)
    True
