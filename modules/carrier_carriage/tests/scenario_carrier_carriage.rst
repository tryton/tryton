=========================
Carrier Carriage Scenario
=========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

Activate modules::

    >>> config = activate_modules(
    ...     ['carrier_carriage', 'sale_shipment_cost'],
    ...     create_company, create_chart)

    >>> Carrier = Model.get('carrier')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')

Get accounts::

    >>> accounts = get_accounts()

Create customer::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', 'Unit')])

    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> carrier_template1 = ProductTemplate()
    >>> carrier_template1.name = "Carrier Product 1"
    >>> carrier_template1.default_uom = unit
    >>> carrier_template1.type = 'service'
    >>> carrier_template1.salable = True
    >>> carrier_template1.list_price = Decimal('3')
    >>> carrier_template1.account_category = account_category
    >>> carrier_template1.save()
    >>> carrier_product1, = carrier_template1.products
    >>> carrier_product1.cost_price = Decimal('2')
    >>> carrier_product1.save()

    >>> carrier_template2 = ProductTemplate()
    >>> carrier_template2.name = "Carrier Product 2"
    >>> carrier_template2.default_uom = unit
    >>> carrier_template2.type = 'service'
    >>> carrier_template2.salable = True
    >>> carrier_template2.list_price = Decimal('2')
    >>> carrier_template2.account_category = account_category
    >>> carrier_template2.save()
    >>> carrier_product2, = carrier_template2.products
    >>> carrier_product2.cost_price = Decimal('1')
    >>> carrier_product2.save()

Create carriers::

    >>> carrier1 = Carrier()
    >>> carrier1.party = Party(name="Carrier 1")
    >>> carrier1.party.save()
    >>> carrier1.carrier_product = carrier_product1
    >>> carrier1.save()

    >>> carrier2 = Carrier()
    >>> carrier2.party = Party(name="Carrier 2")
    >>> carrier2.party.save()
    >>> carrier2.carrier_product = carrier_product2
    >>> carrier2.save()

Sale products with cost on shipment::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.carrier = carrier1
    >>> sale.invoice_method = 'shipment'
    >>> sale.shipment_cost_method = 'shipment'
    >>> before_carriage = sale.before_carriages.new(type='before')
    >>> before_carriage.carrier = carrier2
    >>> before_carriage.cost_method = 'shipment'
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10.0
    >>> sale.untaxed_amount
    Decimal('200.00')
    >>> sale.click('quote')
    >>> sale.untaxed_amount
    Decimal('205.00')
    >>> len(sale.lines)
    3
    >>> sale.click('confirm')
    >>> sale.click('process')
    >>> sale.click('process')
    >>> sale.state
    'processing'

Check shipment::

    >>> shipment, = sale.shipments
    >>> assertEqual(shipment.carrier, carrier1)
    >>> shipment.cost_used
    Decimal('2.0000')
    >>> shipment.cost_sale_used
    Decimal('3.0000')

    >>> carriage, = shipment.before_carriages
    >>> assertEqual(carriage.carrier, carrier2)
    >>> carriage.cost_used
    Decimal('1.0000')
    >>> carriage.cost_sale_used
    Decimal('2.0000')

Send products::

    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')
    >>> shipment.state
    'done'

    >>> shipment.cost_sale_invoice_line.amount
    Decimal('3.00')
    >>> carriage, = shipment.before_carriages
    >>> carriage.cost_sale_invoice_line.amount
    Decimal('2.00')

Check customer invoice::

    >>> sale.reload()
    >>> invoice, = sale.invoices
    >>> invoice.untaxed_amount
    Decimal('205.00')
    >>> len(invoice.lines)
    3
