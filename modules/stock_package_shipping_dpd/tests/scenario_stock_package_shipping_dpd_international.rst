======================================================
Stock Package Shipping with DPD International Scenario
======================================================

Imports::

    >>> import os
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_package_shipping_dpd', 'stock_shipment_customs', 'incoterm'],
    ...     create_company)

    >>> Address = Model.get('party.address')
    >>> Agent = Model.get('customs.agent')
    >>> AgentSelection = Model.get('customs.agent.selection')
    >>> Carrier = Model.get('carrier')
    >>> Country = Model.get('country.country')
    >>> DPDCredential = Model.get('carrier.credential.dpd')
    >>> Incoterm = Model.get('incoterm.incoterm')
    >>> Location = Model.get('stock.location')
    >>> Package = Model.get('stock.package')
    >>> PackageType = Model.get('stock.package.type')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> Shipment = Model.get('stock.shipment.out')
    >>> TariffCode = Model.get('customs.tariff.code')
    >>> UoM = Model.get('product.uom')

Get company::

    >>> company = get_company()

Create countries::

    >>> belgium = Country(code='BE', name="Belgium")
    >>> belgium.save()
    >>> switzerland = Country(code='CH', name="Switerland")
    >>> switzerland.save()
    >>> taiwan = Country(code='TW', code_numeric='158', name="Taiwan")
    >>> taiwan.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer_address, = customer.addresses
    >>> customer_address.street = "Pfistergasse 17"
    >>> customer_address.postal_code = "6003"
    >>> customer_address.city = "Lucerna"
    >>> customer_address.country = switzerland
    >>> customer_phone = customer.contact_mechanisms.new()
    >>> customer_phone.type = 'phone'
    >>> customer_phone.value = "+(41) (041) 410-62-66"
    >>> customer_email = customer.contact_mechanisms.new()
    >>> customer_email.type = 'email'
    >>> customer_email.value = 'customer@example.com'
    >>> customer.save()

    >>> agent_party = Party(name="Agent")
    >>> agent_address, = agent_party.addresses
    >>> agent_address.street = "Gerechtigkeitsgasse 53"
    >>> agent_address.postal_code = "3011"
    >>> agent_address.city = "Berna"
    >>> agent_address.country = switzerland
    >>> agent_identifier = agent_party.identifiers.new()
    >>> agent_identifier.type = 'ch_vat'
    >>> agent_identifier.code = "CHE-123.456.788 IVA"
    >>> agent_email = agent_party.contact_mechanisms.new()
    >>> agent_email.type = 'email'
    >>> agent_email.value = 'agent@example.com'
    >>> agent_phone = agent_party.contact_mechanisms.new()
    >>> agent_phone.type = 'phone'
    >>> agent_phone.value = '+(41) (041) 745-55-28'
    >>> agent_party.save()
    >>> agent = Agent(party=agent_party)
    >>> agent.save()
    >>> AgentSelection(to_country=switzerland, agent=agent).save()

Set the warehouse address::

    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> company_address = Address()
    >>> company_address.party = company.party
    >>> company_address.street = '2 rue de la Centrale'
    >>> company_address.postal_code = '4000'
    >>> company_address.city = 'Sclessin'
    >>> company_address.country = belgium
    >>> company_address.save()
    >>> company_phone = company.party.contact_mechanisms.new()
    >>> company_phone.type = 'phone'
    >>> company_phone.value = '+32 4 2522122'
    >>> company_phone.save()
    >>> warehouse.address = company_address
    >>> warehouse.save()

Get some units::

    >>> unit, = UoM.find([('name', '=', "Unit")], limit=1)
    >>> cm, = UoM.find([('name', '=', "Centimeter")], limit=1)
    >>> gram, = UoM.find([('name', '=', "Gram")], limit=1)

Create tariff::

    >>> tariff_code = TariffCode(code='17039099')
    >>> tariff_code.save()

Create product::

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.weight = 100
    >>> template.weight_uom = gram
    >>> template.list_price = Decimal('10.0000')
    >>> template.country_of_origin = taiwan
    >>> _ = template.tariff_codes.new(tariff_code=tariff_code)
    >>> template.save()
    >>> product, = template.products

Create Package Type::

    >>> box = PackageType(
    ...     name='Box',
    ...     length=10, length_uom=cm,
    ...     height=8, height_uom=cm,
    ...     width=5, width_uom=cm)
    >>> box.save()

Create a DPD Carrier and the related credential::

    >>> credential = DPDCredential()
    >>> credential.company = company
    >>> credential.user_id = os.getenv('DPD_USER_ID')
    >>> credential.password = os.getenv('DPD_PASSWORD')
    >>> credential.server = 'testing'
    >>> credential.save()

    >>> carrier_product_template = ProductTemplate()
    >>> carrier_product_template.name = 'DPD Delivery'
    >>> carrier_product_template.default_uom = unit
    >>> carrier_product_template.type = 'service'
    >>> carrier_product_template.list_price = Decimal(20)
    >>> carrier_product_template.save()
    >>> carrier_product, = carrier_product_template.products

    >>> dpd = Party(name='DPD')
    >>> dpd.save()

    >>> carrier = Carrier()
    >>> carrier.party = dpd
    >>> carrier.carrier_product = carrier_product
    >>> carrier.shipping_service = 'dpd'
    >>> carrier.dpd_product = 'CL'
    >>> carrier.dpd_output_format = 'PDF'
    >>> carrier.dpd_paper_format = 'A6'
    >>> carrier.dpd_notification = 'sms'
    >>> carrier.save()

Create a shipment::

    >>> shipment = Shipment()
    >>> shipment.customer = customer
    >>> shipment.carrier = carrier
    >>> shipment.incoterm, = Incoterm.find([('code', '=', 'DAP')], limit=1)
    >>> move = shipment.outgoing_moves.new()
    >>> move.product = product
    >>> move.unit = unit
    >>> move.quantity = 2
    >>> move.from_location = shipment.warehouse_output
    >>> move.to_location = shipment.customer_location
    >>> move.unit_price = Decimal('50.0000')
    >>> move.currency = company.currency
    >>> shipment.click('wait')
    >>> assertEqual(shipment.customs_agent, agent)
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.state
    'picked'

Create the packs and ship the shipment::

    >>> pack = shipment.packages.new()
    >>> pack.type = box
    >>> pack_move, = pack.moves.find([])
    >>> pack.moves.append(pack_move)
    >>> shipment.click('pack')
    >>> shipment.state
    'packed'

    >>> create_shipping = shipment.click('create_shipping')
    >>> shipment.reload()
    >>> bool(shipment.shipping_reference)
    True
