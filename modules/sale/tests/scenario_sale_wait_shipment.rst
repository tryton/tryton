===========================
Sale Wait Shipment Scenario
===========================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules, assertEqual

    >>> sale_wait_shipment = globals().get('sale_wait_shipment', True)

Activate modules::

    >>> config = activate_modules('sale', create_company, create_chart)

    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> Sale = Model.get('sale.sale')
    >>> SaleConfiguration = Model.get('sale.configuration')

Create party::

    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account categories::

    >>> accounts = get_accounts()

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create product::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])

    >>> template = ProductTemplate()
    >>> template.name = 'product'
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10.0000')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Set wait shipment::

    >>> sale_config = SaleConfiguration(1)
    >>> sale_config.sale_wait_shipment = sale_wait_shipment
    >>> sale_config.save()

Create a sale::

    >>> sale = Sale()
    >>> sale.party = customer
    >>> line = sale.lines.new()
    >>> line.product = product
    >>> line.quantity = 10
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> shipment, = sale.shipments
    >>> assertEqual(shipment.state, 'waiting' if sale_wait_shipment else 'draft')
