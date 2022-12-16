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
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()
    >>> tomorrow = today + relativedelta(days=1)

Activate modules::

    >>> config = activate_modules('commission')

    >>> ReportingAgent = Model.get('commission.reporting.agent')
    >>> ReportingAgentTimeseries = Model.get('commission.reporting.agent.time_series')

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

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create commission product::

    >>> Uom = Model.get('product.uom')
    >>> Template = Model.get('product.template')
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

Create payment method::

    >>> Journal = Model.get('account.journal')
    >>> PaymentMethod = Model.get('account.invoice.payment.method')
    >>> Sequence = Model.get('ir.sequence')
    >>> journal_cash, = Journal.find([('type', '=', 'cash')])
    >>> payment_method = PaymentMethod()
    >>> payment_method.name = 'Cash'
    >>> payment_method.journal = journal_cash
    >>> payment_method.credit_account = accounts['cash']
    >>> payment_method.debit_account = accounts['cash']
    >>> payment_method.save()

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

    >>> template = Template()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.list_price = Decimal(100)
    >>> template.account_category = account_category
    >>> template.principals.append(principal)
    >>> template.save()
    >>> product, = template.products


Create invoice::

    >>> Invoice = Model.get('account.invoice')
    >>> invoice = Invoice()
    >>> invoice.party = customer
    >>> invoice.payment_term = payment_term
    >>> invoice.agent = agent
    >>> invoice.invoice_date
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
    >>> [c.base_amount for c in line.commissions]
    [Decimal('100.00'), Decimal('100.00')]
    >>> [c.amount for c in line.commissions]
    [Decimal('10.0000'), Decimal('10.0000')]
    >>> [c.invoice_state for c in line.commissions]
    ['', '']
    >>> [c.date for c in line.commissions]
    [None, None]

Pending amount for agent::

    >>> agent.reload()
    >>> agent.pending_amount
    Decimal('10.0000')

Pending amount for principal::

    >>> principal.reload()
    >>> principal.pending_amount
    Decimal('10.0000')

Pay invoice::

    >>> pay = Wizard('account.invoice.pay', [invoice])
    >>> pay.form.payment_method = payment_method
    >>> pay.form.date = tomorrow
    >>> pay.execute('choice')
    >>> pay.state
    'end'
    >>> Commission = Model.get('commission')
    >>> [c.date == tomorrow for c in Commission.find([])]
    [True, True]

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

    >>> commissions = Commission.find([])
    >>> [c.invoice_state for c in commissions]
    ['invoiced', 'invoiced']

Credit invoice::

    >>> invoice, = Invoice.find([
    ...         ('type', '=', 'out'),
    ...         ('agent', '=', agent.id),
    ...         ])
    >>> credit = Wizard('account.invoice.credit', [invoice])
    >>> credit.execute('credit')
    >>> credit_note, = credit.actions[0]
    >>> credit_note.agent == agent
    True

Check commission reporting per agent::

    >>> with config.set_context(type='out', period='day'):
    ...     reporting_agent, = ReportingAgent.find([])
    ...     reporting_agent_timeseries, = ReportingAgentTimeseries.find([])

    >>> reporting_agent.base_amount == Decimal('100.00')
    True
    >>> reporting_agent.amount == Decimal('10.0000')
    True
    >>> reporting_agent.number
    1

    >>> reporting_agent_timeseries.date == tomorrow
    True
    >>> reporting_agent_timeseries.base_amount == Decimal('100.00')
    True
    >>> reporting_agent_timeseries.amount == Decimal('10.00')
    True
    >>> reporting_agent_timeseries.number
    1
