========================
Agent Selection Scenario
========================

Imports::

    >>> import datetime as dt

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual, set_user

    >>> today = dt.date.today()
    >>> yesterday = today - dt.timedelta(days=1)

Activate modules::

    >>> config = activate_modules(['commission', 'sale'], create_company, create_chart)

Get company::

    >>> company = get_company()

Get accounts::

    >>> accounts = get_accounts()

Create employee::

    >>> Party = Model.get('party.party')
    >>> Employee = Model.get('company.employee')
    >>> employee = Employee()
    >>> party = Party(name='Employee')
    >>> party.save()
    >>> employee.party = party
    >>> employee.company = company
    >>> employee.save()

Create customers::

    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> other_customer = Party(name='Other Customer')
    >>> other_customer.save()

Create agent::

    >>> Agent = Model.get('commission.agent')
    >>> agent_party = Party(name='Agent')
    >>> agent_party.save()
    >>> agent = Agent(party=agent_party)
    >>> agent.type_ = 'agent'
    >>> agent.currency = company.currency
    >>> selection = agent.selections.new()
    >>> selection.start_date = today
    >>> selection.party = customer
    >>> selection = agent.selections.new()
    >>> selection.employee = employee
    >>> agent.save()

Create sale::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.save()

The agent is assigned on quotation::

    >>> sale.agent
    >>> sale.click('quote')
    >>> sale.state
    'quotation'
    >>> assertEqual(sale.agent, agent)

Agent is not set for yesterday sales::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.sale_date = yesterday
    >>> sale.party = customer
    >>> sale.click('quote')
    >>> sale.state
    'quotation'
    >>> sale.agent

Link user to employee::

    >>> User = Model.get('res.user')
    >>> user = User(config.user)
    >>> user.employees.append(employee)
    >>> user.employee = employee
    >>> user.save()
    >>> set_user(user.id)

Creating a sale and test agent is assigned::

    >>> sale = Sale()
    >>> sale.party = other_customer
    >>> sale.agent
    >>> sale.click('quote')
    >>> sale.state
    'quotation'
    >>> assertEqual(sale.quoted_by, employee)
    >>> assertEqual(sale.agent, agent)
