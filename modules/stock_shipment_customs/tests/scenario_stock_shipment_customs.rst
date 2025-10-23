===============================
Stock Shipment Customs Scenario
===============================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Report
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules('stock_shipment_customs', create_company)

    >>> Agent = Model.get('customs.agent')
    >>> AgentSelection = Model.get('customs.agent.selection')
    >>> Country = Model.get('country.country')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> Shipment = Model.get('stock.shipment.out')
    >>> UoM = Model.get('product.uom')

Setup countries::

    >>> belgium = Country(name="Belgium", code='BE')
    >>> belgium.save()
    >>> usa = Country(name="USA", code="US")
    >>> usa.save()

    >>> company = get_company()
    >>> company_address, = company.party.addresses
    >>> company_address.country = belgium
    >>> company_address.save()

Setup locations::

    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> warehouse.address = company_address
    >>> warehouse.save()

Create product::

    >>> unit, = UoM.find([('name', '=', "Unit")])

    >>> template = ProductTemplate(name="Product")
    >>> template.type = 'goods'
    >>> template.default_uom = unit
    >>> template.save()
    >>> product, = template.products

Create customs agent::

    >>> party_agent = Party(name="Agent")
    >>> tax_identifier = party_agent.identifiers.new()
    >>> tax_identifier.type = 'us_tin'
    >>> tax_identifier.code = '123456789'
    >>> party_agent.save()
    >>> agent_adress, = party_agent.addresses
    >>> agent_adress.country = usa
    >>> agent_adress.save()
    >>> agent = Agent(party=party_agent, address=agent_adress)
    >>> agent.tax_identifier, = party_agent.identifiers
    >>> agent.save()

    >>> agent_selection = AgentSelection(to_country=usa)
    >>> agent_selection.agent = agent
    >>> agent_selection.save()

Create a foreign customer::

    >>> customer = Party(name="Customer")
    >>> address, = customer.addresses
    >>> address.country = usa
    >>> customer.save()

Create an international shipment::

    >>> shipment = Shipment()
    >>> shipment.customer = customer
    >>> shipment.warehouse = warehouse
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = warehouse.output_location
    >>> move.to_location = shipment.customer_location
    >>> move.unit_price = Decimal('50.0000')
    >>> move.currency = company.currency
    >>> shipment.click('wait')
    >>> shipment.state
    'waiting'
    >>> assertEqual(shipment.customs_agent, agent)

    >>> commercial_invoice = Report('customs.commercial_invoice')
    >>> bool(commercial_invoice.execute([shipment]))
    True
