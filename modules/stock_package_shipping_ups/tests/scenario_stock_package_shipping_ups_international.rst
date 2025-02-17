======================================================
Stock Package Shipping with UPS International Scenario
======================================================

Imports::

    >>> import os
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_package_shipping_ups', 'stock_shipment_customs'],
    ...     create_company)

    >>> Agent = Model.get('customs.agent')
    >>> AgentSelection = Model.get('customs.agent.selection')
    >>> Address = Model.get('party.address')
    >>> Carrier = Model.get('carrier')
    >>> Country = Model.get('country.country')
    >>> Location = Model.get('stock.location')
    >>> Package = Model.get('stock.package')
    >>> PackageType = Model.get('stock.package.type')
    >>> Party = Model.get('party.party')
    >>> ProductTemplate = Model.get('product.template')
    >>> Shipment = Model.get('stock.shipment.out')
    >>> UPSCredential = Model.get('carrier.credential.ups')
    >>> UoM = Model.get('product.uom')

Get company::

    >>> company = get_company()

Create countries::

    >>> belgium = Country(code='BE', name="Belgium")
    >>> belgium.save()
    >>> switzerland = Country(code='CH', name="Switerland")
    >>> switzerland.save()
    >>> taiwan = Country(code='TW', name="Taiwan")
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

Create product::

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.weight = 100
    >>> template.weight_uom = gram
    >>> template.list_price = Decimal('10.0000')
    >>> template.country_of_origin = taiwan
    >>> template.save()
    >>> product, = template.products

Create Package Type::

    >>> ups_box = PackageType(
    ...     name='UPS Box', ups_code='02',
    ...     length=10, length_uom=cm,
    ...     height=8, height_uom=cm,
    ...     width=1, width_uom=cm)
    >>> ups_box.save()

Create a UPS Carrier and the related credential::

    >>> credential = UPSCredential()
    >>> credential.company = company
    >>> credential.client_id = os.getenv('UPS_CLIENT_ID')
    >>> credential.client_secret = os.getenv('UPS_CLIENT_SECRET')
    >>> credential.account_number = os.getenv('UPS_ACCOUNT_NUMBER')
    >>> credential.server = 'testing'
    >>> credential.use_international_forms = True
    >>> credential.save()

    >>> carrier_product_template = ProductTemplate()
    >>> carrier_product_template.name = 'UPS Ground'
    >>> carrier_product_template.default_uom = unit
    >>> carrier_product_template.type = 'service'
    >>> carrier_product_template.list_price = Decimal(20)
    >>> carrier_product_template.save()
    >>> carrier_product, = carrier_product_template.products

    >>> ups = Party(name='UPS')
    >>> ups.save()

    >>> carrier = Carrier()
    >>> carrier.party = ups
    >>> carrier.carrier_product = carrier_product
    >>> carrier.shipping_service = 'ups'
    >>> carrier.ups_service_type = '65'
    >>> carrier.ups_label_image_format = 'GIF'
    >>> carrier.ups_notifications = ['5', '7', '012']
    >>> carrier.save()

Create a shipment::

    >>> shipment = Shipment()
    >>> shipment.customer = customer
    >>> shipment.carrier = carrier
    >>> shipment.shipping_description = "Shipping description"
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
    >>> pack.type = ups_box
    >>> pack_move, = pack.moves.find([])
    >>> pack.moves.append(pack_move)
    >>> shipment.click('pack')
    >>> shipment.state
    'packed'

    >>> create_shipping = shipment.click('create_shipping')
    >>> shipment.reload()
    >>> bool(shipment.shipping_reference)
    True
