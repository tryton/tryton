=========================================
Stock Package Shipping Sendcloud Scenario
=========================================

Imports::

    >>> import os
    >>> from decimal import Decimal
    >>> from random import randint

    >>> import requests

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.stock_package_shipping_sendcloud.carrier import (
    ...     SENDCLOUD_API_URL)
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_package_shipping_sendcloud', 'sale', 'sale_shipment_cost'])

    >>> Address = Model.get('party.address')
    >>> Carrier = Model.get('carrier')
    >>> CarrierAddress = Model.get('carrier.sendcloud.address')
    >>> CarrierShippingMethod = Model.get('carrier.sendcloud.shipping_method')
    >>> Country = Model.get('country.country')
    >>> Credential = Model.get('carrier.credential.sendcloud')
    >>> Location = Model.get('stock.location')
    >>> Package = Model.get('stock.package')
    >>> PackageType = Model.get('stock.package.type')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUoM = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')
    >>> StockConfiguration = Model.get('stock.configuration')
    >>> UoM = Model.get('product.uom')

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

Set random sequence::

    >>> stock_config = StockConfiguration(1)
    >>> stock_config.shipment_out_sequence.number_next = randint(1, 10**6)
    >>> stock_config.shipment_out_sequence.save()
    >>> stock_config.package_sequence.number_next = randint(1, 10**6)
    >>> stock_config.package_sequence.save()

Create parties::

    >>> belgium = Country(code='BE', name='Belgium')
    >>> belgium.save()
    >>> france = Country(code='FR', name='France')
    >>> subdivision = france.subdivisions.new()
    >>> subdivision.name = "Paris"
    >>> subdivision.code = 'FR-75'
    >>> subdivision.type = 'metropolitan department'
    >>> france.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> customer_address = customer.addresses.new()
    >>> customer_address.street = 'Champs élysées'
    >>> customer_address.postal_code = '75008'
    >>> customer_address.city = 'Paris'
    >>> customer_address.country = france
    >>> customer_address.subdivision = france.subdivisions[0]
    >>> customer_address.save()
    >>> customer_phone = customer.contact_mechanisms.new()
    >>> customer_phone.type = 'phone'
    >>> customer_phone.value = '+33 93 842 8862'
    >>> customer_phone.save()

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

    >>> cm, = UoM.find([('symbol', '=', 'cm')])
    >>> g, = UoM.find([('symbol', '=', 'g')])

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUoM.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.weight = 100
    >>> template.weight_uom = g
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create Package Type::

    >>> box = PackageType(
    ...     name="Box",
    ...     length=10, length_uom=cm,
    ...     height=8, height_uom=cm,
    ...     width=1, width_uom=cm)
    >>> box.save()

Create a Sendcloud Carrier and the related credentials::

    >>> credential = Credential()
    >>> credential.company = company
    >>> credential.public_key = os.getenv('SENDCLOUD_PUBLIC_KEY')
    >>> credential.secret_key = os.getenv('SENDCLOUD_SECRET_KEY')
    >>> credential.save()
    >>> address = credential.addresses.new()
    >>> address.warehouse = warehouse
    >>> address.address = CarrierAddress.get_addresses(
    ...     {'id': address.id, 'sendcloud': {'id': credential.id}},
    ...     address._context)[-1][0]
    >>> shipping_method = credential.shipping_methods.new()
    >>> shipping_method.shipping_method, = [
    ...     m[0] for m in CarrierShippingMethod.get_shipping_methods(
    ...         {'id': shipping_method.id, 'sendcloud': {'id': credential.id}},
    ...         shipping_method._context)
    ...     if m[1] == "Unstamped letter"]
    >>> credential.save()

    >>> template = ProductTemplate()
    >>> template.name = "Sendcloud"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.list_price = Decimal(20)
    >>> template.account_category = account_category
    >>> template.save()
    >>> carrier_product, = template.products

    >>> sendcloud = Party(name="Sendcloud")
    >>> sendcloud.save()

    >>> carrier = Carrier()
    >>> carrier.party = sendcloud
    >>> carrier.carrier_product = carrier_product
    >>> carrier.shipping_service = 'sendcloud'
    >>> carrier.save()

Create a sale and thus a shipment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.shipment_address = customer_address
    >>> sale.invoice_method = 'order'
    >>> sale.carrier = carrier
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Create the packages and ship the shipment::

    >>> shipment, = sale.shipments
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> pack = shipment.packages.new()
    >>> pack.type = box
    >>> pack_move, = pack.moves.find([])
    >>> pack.moves.append(pack_move)
    >>> shipment.click('pack')

    >>> create_shipping = shipment.click('create_shipping')
    >>> shipment.reload()
    >>> bool(shipment.shipping_reference)
    True
    >>> pack, = shipment.root_packages
    >>> bool(pack.sendcloud_shipping_id)
    True
    >>> pack.shipping_label is not None
    True
    >>> pack.shipping_label_mimetype
    'application/pdf'
    >>> pack.shipping_reference is not None
    True
    >>> pack.shipping_tracking_url
    'http...'

Clean up::

    >>> _ = requests.post(
    ...     SENDCLOUD_API_URL + 'parcels/%s/cancel' % pack.sendcloud_shipping_id,
    ...     auth=(credential.public_key, credential.secret_key))
