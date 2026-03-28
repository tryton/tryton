=====================================
Account Stock EU Excise Sale Scenario
=====================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.modules.currency.tests.tools import get_currency
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['account_stock_eu_excise', 'sale', 'sale_price_list'],
    ...     create_company)

    >>> Country = Model.get('country.country')
    >>> ExciseCode = Model.get('product.eu.excise_code')
    >>> ExciseTax = Model.get('account.stock.eu.excise.tax')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> PriceList = Model.get('product.price_list')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Get company::

    >>> company = get_company()

Setup tax warehouse::

    >>> liter, = ProductUom.find([('name', '=', "Liter")])
    >>> france = Country(code='FR', name='France')
    >>> france.save()

    >>> excise_code = ExciseCode(code='W200')
    >>> excise_code.save()

    >>> company_party = company.party
    >>> company_address, = company_party.addresses
    >>> company_address.country = france
    >>> excise_number = company_party.identifiers.new(type='eu_excise')
    >>> excise_number.address = company_address
    >>> excise_number.code = "LU00000987ABC"
    >>> excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> company_party.save()
    >>> excise_number, = company_party.identifiers

    >>> warehouse, = Location.find([('code', '=', 'WH')])
    >>> warehouse.address = company_address
    >>> wh_excise_number = warehouse.eu_excise_numbers.new()
    >>> wh_excise_number.eu_excise_number = excise_number
    >>> warehouse.save()

    >>> excise_tax = ExciseTax(code='TAX')
    >>> excise_tax.quantity = 'measurement_volume'
    >>> excise_tax.uom = liter
    >>> excise_tax.country = france
    >>> excise_tax.currency = get_currency('EUR')
    >>> tax_rate = excise_tax.tax_rates.new()
    >>> tax_rate.formula = 'quantity * 5'
    >>> excise_tax.save()

Create a customer::

    >>> customer = Party(name="Customer")
    >>> customer.save()
    >>> customer_excise_number = customer.identifiers.new(type='eu_excise')
    >>> customer_excise_number.address, = customer.addresses
    >>> customer_excise_number.code = "LU00000987DEF"
    >>> customer_excise_number.eu_excise_codes.append(ExciseCode(excise_code.id))
    >>> customer.save()
    >>> customer_excise_number, = customer.identifiers

Create a product::

    >>> template = ProductTemplate()
    >>> template.name = "Wine"
    >>> template.default_uom = liter
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20.0000')
    >>> template.eu_excise_code = excise_code
    >>> template.salable = True
    >>> _ = template.eu_excise_taxes.new(excise_tax=excise_tax)
    >>> template.save()
    >>> product, = template.products

Create a price list::

    >>> price_list = PriceList(name="Price", price='list_price')

    >>> price_list_line = price_list.lines.new()
    >>> price_list_line.eu_excise_tax = excise_tax
    >>> price_list_line.eu_excise_duty = 'suspension'
    >>> price_list_line.formula = 'unit_price * .9'

    >>> price_list_line = price_list.lines.new()
    >>> price_list_line.eu_excise_tax = excise_tax
    >>> price_list_line.eu_excise_duty = None
    >>> price_list_line.formula = 'unit_price'

    >>> price_list.save()

Create a sale without suspension::

    >>> sale = Sale(party=customer, price_list=price_list)
    >>> sale.invoice_method = 'manual'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.unit_price
    Decimal('20.0000')
    >>> line.quantity = 1
    >>> sale.save()
    >>> sale.eu_excise_duty_amount
    Decimal('2.50')

Create a sale with suspension::

    >>> sale = Sale(party=customer, price_list=price_list)
    >>> sale.invoice_method = 'manual'
    >>> sale.eu_excise_number = customer_excise_number
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.unit_price
    Decimal('18.0000')
    >>> line.quantity = 1
    >>> sale.save()
    >>> sale.eu_excise_duty_amount
    Decimal('0')

Check excise number is passed to shipment::

    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'

    >>> shipment, = sale.shipments
    >>> assertEqual(shipment.eu_excise_number, customer_excise_number)
