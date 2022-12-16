========================================
Sale Shipment Cost Modify Price Scenario
========================================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)

Activate modules::

    >>> config = activate_modules('sale_shipment_cost')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create customer::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.save()

Create product::

    >>> ProductUom = Model.get('product.uom')
    >>> ProductTemplate = Model.get('product.template')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = 'Product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template = ProductTemplate()
    >>> carrier_template.name = 'Carrier Product'
    >>> carrier_template.default_uom = unit
    >>> carrier_template.type = 'service'
    >>> carrier_template.salable = True
    >>> carrier_template.list_price = Decimal('3')
    >>> carrier_template.account_category = account_category
    >>> carrier_template.save()
    >>> carrier_product, = carrier_template.products

Create carrier::

    >>> Carrier = Model.get('carrier')
    >>> carrier = Carrier()
    >>> party = Party(name='Carrier')
    >>> party.save()
    >>> carrier.party = party
    >>> carrier.carrier_product = carrier_product
    >>> carrier.save()

Make a quote::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 5.0
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.product == carrier_product
    True
    >>> cost_line.quantity
    1.0
    >>> cost_line.amount
    Decimal('3.00')

Change the shipment cost price::

    >>> sale.click('draft')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.unit_price = Decimal('2.00')
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.product == carrier_product
    True
    >>> cost_line.quantity
    1.0
    >>> cost_line.amount
    Decimal('2.00')

Change the carrier price reset the cost line::

    >>> carrier_template.list_price = Decimal('4')
    >>> carrier_template.save()

    >>> sale.click('draft')
    >>> sale.click('quote')
    >>> cost_line = sale.lines[-1]
    >>> cost_line.product == carrier_product
    True
    >>> cost_line.quantity
    1.0
    >>> cost_line.amount
    Decimal('4.00')
