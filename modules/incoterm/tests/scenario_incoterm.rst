=================
Incoterm Scenario
=================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, get_accounts)

Activate modules::

    >>> config = activate_modules(
    ...     ['incoterm', 'sale', 'sale_shipment_cost', 'purchase'])

    >>> Address = Model.get('party.address')
    >>> Carrier = Model.get('carrier')
    >>> Country = Model.get('country.country')
    >>> Incoterm = Model.get('incoterm.incoterm')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Purchase = Model.get('purchase.purchase')
    >>> Sale = Model.get('sale.sale')

Create countries::

    >>> belgium = Country(name="Belgium", code='BE')
    >>> belgium.save()
    >>> china = Country(name="China", code='CN')
    >>> china.save()

Create company::

    >>> _ = create_company()
    >>> company = get_company()
    >>> company.incoterms.extend(Incoterm.find([
    ...         ('code', 'in', ['FCA', 'CIP', 'CFR', 'CIF']),
    ...         ('version', '=', '2020')
    ...         ]))
    >>> company.save()

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create addresses::

    >>> warehouse_address = Address(
    ...     party=company.party, name="Warehouse", country=belgium)
    >>> warehouse_address.save()

    >>> port = Party(name="Port of Fuzhou")
    >>> address, = port.addresses
    >>> address.country = china
    >>> port.save()

Set warehouse address::

    >>> warehouse, = Location.find([('type', '=', 'warehouse')])
    >>> warehouse.address = warehouse_address
    >>> warehouse.save()

Create parties::

    >>> customer = Party(name="Customer")
    >>> address, = customer.addresses
    >>> address.country = china
    >>> line = customer.sale_incoterms.new()
    >>> line.type = 'sale'
    >>> line.incoterm, = Incoterm.find([
    ...         ('code', '=', 'CIF'), ('version', '=', '2020')])
    >>> line = customer.sale_incoterms.new()
    >>> line.type = 'sale'
    >>> line.incoterm, = Incoterm.find([
    ...         ('code', '=', 'CFR'), ('version', '=', '2020')])
    >>> line = customer.sale_incoterms.new()
    >>> line.type = 'sale'
    >>> line.incoterm, = Incoterm.find([
    ...         ('code', '=', 'FCA'), ('version', '=', '2020')])
    >>> line.incoterm_location = warehouse_address
    >>> customer.save()

    >>> supplier = Party(name="Supplier")
    >>> address, = supplier.addresses
    >>> address.country = china
    >>> line = supplier.purchase_incoterms.new()
    >>> line.type = 'purchase'
    >>> line.incoterm, = Incoterm.find([
    ...         ('code', '=', 'CFR'), ('version', '=', '2020')])
    >>> line.incoterm_location = warehouse_address
    >>> supplier.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = "Carrier Product"
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.account_category = account_category
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

Create carriers::

    >>> carrier = Carrier()
    >>> party = Party(name="Carrier")
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()
    >>> carrier_waterway, = carrier.duplicate()
    >>> carrier_waterway.mode= 'waterway'
    >>> carrier_waterway.save()

Test incoterms are deducted from sale::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier_waterway
    >>> sale.incoterm.rec_name
    'CIF (2020)'
    >>> sale.incoterm_location
    >>> sale.carrier = carrier
    >>> sale.incoterm
    >>> sale.shipment_cost_method = None
    >>> sale.incoterm.rec_name
    'FCA (2020)'
    >>> sale.incoterm_location == warehouse_address
    True

Try sale without incoterm::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier_waterway
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 1
    >>> sale.incoterm = None
    >>> sale.click('quote')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    SaleQuotationError: ...

Try sale with incoterm::

    >>> sale.incoterm, = Incoterm.find([
    ...         ('code', '=', 'CIF'), ('version', '=', '2020')])
    >>> sale.click('quote')  # doctest: +IGNORE_EXCEPTION_DETAIL
    Traceback (most recent call last):
        ...
    RequiredValidationError: ...

Try sale with incoterm and location::

    >>> sale.incoterm_location, = port.addresses
    >>> sale.click('quote')
    >>> sale.state
    'quotation'

Test incoterm on shipment::

    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> shipment, = sale.shipments
    >>> shipment.incoterm.rec_name
    'CIF (2020)'
    >>> shipment.incoterm_location == port.addresses[0]
    True

Test incoterm is set on purchase::

    >>> purchase = Purchase()
    >>> purchase.party = supplier
    >>> purchase.incoterm.rec_name
    'CFR (2020)'
