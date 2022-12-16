===================
Commission Scenario
===================

Imports::

    >>> import datetime
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax, set_tax_code
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Install commission::

    >>> config = activate_modules('commission')

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

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create commission product::

    >>> Uom = Model.get('product.uom')
    >>> Template = Model.get('product.template')
    >>> Product = Model.get('product.product')
    >>> unit, = Uom.find([('name', '=', 'Unit')])
    >>> commission_product = Product()
    >>> template = Template()
    >>> template.name = 'Commission'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(0)
    >>> template.cost_price = Decimal(0)
    >>> template.account_expense = accounts['expense']
    >>> template.account_revenue = accounts['revenue']
    >>> template.save()
    >>> commission_product.template = template
    >>> commission_product.save()

Create commission plan::

    >>> Plan = Model.get('commission.plan')
    >>> plan = Plan(name='Plan')
    >>> plan.commission_product = commission_product
    >>> plan.commission_method = 'payment'
    >>> line = plan.lines.new()
    >>> line.formula = 'amount * 0.1'
    >>> plan.save()

Create payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create agent::

    >>> Agent = Model.get('commission.agent')
    >>> agent_party = Party(name='Agent')
    >>> agent_party.supplier_payment_term = payment_term
    >>> agent_party.save()
    >>> agent = Agent(party=agent_party)
    >>> agent.type_ = 'agent'
    >>> agent.plan = plan
    >>> agent.currency = company.currency
    >>> agent.save()

Create principal::

    >>> principal_party = Party(name='Principal')
    >>> principal_party.customer_payment_term = payment_term
    >>> principal_party.save()
    >>> principal = Agent(party=principal_party)
    >>> principal.type_ = 'principal'
    >>> principal.plan = plan
    >>> principal.currency = company.currency
    >>> principal.save()

Create product sold::

    >>> product = Product()
    >>> template = Template()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(100)
    >>> template.cost_price = Decimal(100)
    >>> template.account_expense = accounts['expense']
    >>> template.account_revenue = accounts['revenue']
    >>> template.principals.append(principal)
    >>> template.save()
    >>> product.template = template
    >>> product.save()


Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = customer
    >>> invoice.payment_term = payment_term
    >>> invoice.agent = agent
    >>> line = invoice.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> line.unit_price = Decimal(100)
    >>> invoice.save()

Post invoice::

    >>> invoice.click('post')
    >>> line, = invoice.lines
    >>> len(line.commissions)
    2
    >>> [c.amount for c in line.commissions]
    [Decimal('10.0000'), Decimal('10.0000')]
    >>> [c.invoice_state for c in line.commissions]
    [u'', u'']

Pending amount for agent::

    >>> agent.reload()
    >>> agent.pending_amount
    Decimal('10.0000')

Pending amount for principal::

    >>> principal.reload()
    >>> principal.pending_amount
    Decimal('10.0000')

Create commission invoices::

    >>> create_invoice = Wizard('commission.create_invoice')
    >>> create_invoice.form.from_ = None
    >>> create_invoice.form.to = None
    >>> create_invoice.execute('create_')

    >>> invoice, = Invoice.find([
    ...         ('type', '=', 'in'),
    ...         ])
    >>> invoice.total_amount
    Decimal('10.00')
    >>> invoice.party == agent_party
    True
    >>> invoice_line, = invoice.lines
    >>> invoice_line.product == commission_product
    True

    >>> invoice, = Invoice.find([
    ...         ('type', '=', 'out'),
    ...         ('party', '=', principal.party.id),
    ...         ])
    >>> invoice.total_amount
    Decimal('10.00')

    >>> Commission = Model.get('commission')
    >>> commissions = Commission.find([])
    >>> [c.invoice_state for c in commissions]
    [u'invoiced', u'invoiced']
