========================================
Stock Package Shipping with DPD scenario
========================================

Imports::

    >>> import datetime
    >>> import os
    >>> from dateutil.relativedelta import relativedelta
    >>> from decimal import Decimal
    >>> from operator import attrgetter
    >>> from proteus import Model, Wizard, Report
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import create_company, \
    ...     get_company
    >>> from trytond.modules.account.tests.tools import create_fiscalyear, \
    ...     create_chart, get_accounts, create_tax
    >>> from trytond.modules.account_invoice.tests.tools import \
    ...     set_fiscalyear_invoice_sequences, create_payment_term
    >>> today = datetime.date.today()

Activate modules::

    >>> config = activate_modules(['stock_package_shipping_dpd', 'sale'])

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
    >>> revenue = accounts['revenue']
    >>> expense = accounts['expense']

Create a payment term::

    >>> payment_term = create_payment_term()
    >>> payment_term.save()

Create parties::

    >>> Party = Model.get('party.party')
    >>> Country = Model.get('country.country')

    >>> belgium = Country(code='BE', name='Belgium')
    >>> belgium.save()
    >>> britain = Country(code='GB', name='Great Britain')
    >>> britain.save()
    >>> customer = Party(name='Customer')
    >>> customer.save()
    >>> customer_address = customer.addresses.new()
    >>> customer_address.street = 'Anfield Road'
    >>> customer_address.zip = 'L40TH'
    >>> customer_address.city = 'Liverpool'
    >>> customer_address.country = britain
    >>> customer_address.save()
    >>> customer_phone = customer.contact_mechanisms.new()
    >>> customer_phone.type = 'phone'
    >>> customer_phone.value = '+44 151 260 6677'
    >>> customer_phone.save()

Set the warehouse address::

    >>> Address = Model.get('party.address')
    >>> Location = Model.get('stock.location')
    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> company_address = Address()
    >>> company_address.party = company.party
    >>> company_address.street = '2 rue de la Centrale'
    >>> company_address.zip = '4000'
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

    >>> UoM = Model.get('product.uom')
    >>> cm, = UoM.find([('symbol', '=', 'cm')])
    >>> g, = UoM.find([('symbol', '=', 'g')])

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = expense
    >>> account_category.account_revenue = revenue
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> ProductTemplate = Model.get('product.template')

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

Create an Inventory::

    >>> Inventory = Model.get('stock.inventory')
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
    >>> box = PackageType(
    ...     name='Box',
    ...     length=10, length_uom=cm,
    ...     height=8, height_uom=cm,
    ...     width=5, width_uom=cm)
    >>> box.save()

Create a DPD Carrier and the related credential::

    >>> Carrier = Model.get('carrier')
    >>> CarrierSelection = Model.get('carrier.selection')
    >>> DPDCredential = Model.get('carrier.credential.dpd')

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
    >>> carrier_product_template.salable = True
    >>> carrier_product_template.list_price = Decimal(20)
    >>> carrier_product_template.account_category = account_category
    >>> carrier_product_template.save()
    >>> carrier_product, = carrier_product_template.products

    >>> dpd = Party(name='DPD')
    >>> dpd.save()

    >>> carrier = Carrier()
    >>> carrier.party = dpd
    >>> carrier.carrier_product = carrier_product
    >>> carrier.shipping_service = 'dpd'
    >>> carrier.save()

    >>> catchall_selection = CarrierSelection(carrier=carrier)
    >>> catchall_selection.save()

Create a sale and thus a shipment::

    >>> Sale = Model.get('sale.sale')
    >>> SaleLine = Model.get('sale.line')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.shipment_address = customer_address
    >>> sale.payment_term = payment_term
    >>> sale.invoice_method = 'order'
    >>> sale.carrier = carrier
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 2.0
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Create the packs and ship the shipment::

    >>> Package = Model.get('stock.package')
    >>> shipment, = sale.shipments
    >>> shipment.click('assign_try')
    True
    >>> shipment.click('pick')
    >>> pack = shipment.packages.new()
    >>> pack.type = box
    >>> pack_move, = pack.moves.find([])
    >>> pack.moves.append(pack_move)
    >>> shipment.click('pack')

    >>> create_shipping = Wizard('stock.shipment.create_shipping', [shipment])
    >>> shipment.reload()
    >>> shipment.reference != ''
    True
    >>> pack, = shipment.root_packages
    >>> pack.shipping_label is not None
    True
    >>> pack.shipping_reference is not None
    True
