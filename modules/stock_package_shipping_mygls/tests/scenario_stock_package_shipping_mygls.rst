=====================================
Stock Package Shipping MyGLS Scenario
=====================================

Imports::

    >>> import os
    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

Activate modules::

    >>> config = activate_modules(
    ...     ['stock_package_shipping_mygls', 'sale', 'sale_shipment_cost'])

    >>> Address = Model.get('party.address')
    >>> Carrier = Model.get('carrier')
    >>> CarrierSelection = Model.get('carrier.selection')
    >>> Country = Model.get('country.country')
    >>> Credential = Model.get('carrier.credential.mygls')
    >>> Inventory = Model.get('stock.inventory')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

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

Create countries::

    >>> hungary= Country(code='HU', name="Hungary")
    >>> hungary.save()

Create parties::

    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> customer_address = customer.addresses.new()
    >>> customer_address.street = "Európa u., 2"
    >>> customer_address.postal_code = "2351"
    >>> customer_address.city = "Alsónémedi"
    >>> customer_address.country = hungary
    >>> customer_address.save()
    >>> customer_phone = customer.contact_mechanisms.new()
    >>> customer_phone.type = 'phone'
    >>> customer_phone.value = "+36701234567"
    >>> customer_phone.save()

Set the warehouse address::

    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> company_address = Address()
    >>> company_address.party = company.party
    >>> company_address.street = "Európa u., 2"
    >>> company_address.postal_code = "2351"
    >>> company_address.city = "Alsónémedi"
    >>> company_address.country = hungary
    >>> company_address.save()
    >>> company_phone = company.party.contact_mechanisms.new()
    >>> company_phone.type = 'phone'
    >>> company_phone.value = "+36701234567"
    >>> company_phone.save()
    >>> warehouse.address = company_address
    >>> warehouse.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Create an Inventory::

    >>> storage, = Location.find([
    ...         ('code', '=', 'STO'),
    ...         ])
    >>> inventory = Inventory()
    >>> inventory.location = storage
    >>> inventory_line = inventory.lines.new(product=product)
    >>> inventory_line.quantity = 100.0
    >>> inventory_line.expected_quantity = 0.0
    >>> inventory.click('confirm')
    >>> inventory.state
    'done'

Create Package Type::

    >>> PackageType = Model.get('stock.package.type')
    >>> box = PackageType(name='Box')
    >>> box.save()

Create a MyGLS carrier::

    >>> credential = Credential()
    >>> credential.company = company
    >>> credential.server = 'testing'
    >>> credential.country = 'hu'
    >>> credential.username = os.getenv('MYGLS_USERNAME')
    >>> credential.password = os.getenv('MYGLS_PASSWORD')
    >>> credential.client_number = int(os.getenv('MYGLS_CLIENT_NUMBER'))
    >>> credential.save()

    >>> template = ProductTemplate()
    >>> template.name = "GLS"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.list_price = Decimal(20)
    >>> template.account_category = account_category
    >>> template.save()
    >>> carrier_product, = template.products

    >>> gls = Party(name="GLS")
    >>> gls.save()

    >>> carrier = Carrier()
    >>> carrier.party = gls
    >>> carrier.carrier_product = carrier_product
    >>> carrier.shipping_service = 'mygls'
    >>> carrier.mygls_type_of_printer = 'A4_2x2'
    >>> carrier.mygls_print_position = 3
    >>> carrier.mygls_services = ['CS1', 'TGS']
    >>> carrier.save()

Create a sale and thus a shipment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.shipment_address = customer_address
    >>> sale.invoice_method = 'order'
    >>> sale.carrier = carrier
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1.0
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 1.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Create the packages and ship the shipment::

    >>> shipment, = sale.shipments
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> pack = shipment.packages.new(type=box)
    >>> pack_moves = pack.moves.find([])
    >>> pack.moves.append(pack_moves[0])
    >>> pack = shipment.packages.new(type=box)
    >>> pack.moves.append(pack_moves[1])
    >>> shipment.click('pack')

    >>> create_shipping = Wizard('stock.shipment.create_shipping', [shipment])
    >>> shipment.reload()
    >>> bool(shipment.reference)
    True
    >>> pack, _ = shipment.root_packages
    >>> pack.shipping_label is not None
    True
    >>> pack.shipping_label_mimetype
    'application/pdf'
    >>> pack.mygls_shipping_id is not None
    True
    >>> bool(pack.shipping_reference)
    True
