=====================================
Sale Over Shipment Tolerance Scenario
=====================================

Imports::

    >>> from decimal import Decimal

    >>> from proteus import Model, Wizard
    >>> from trytond.modules.account.tests.tools import create_chart, get_accounts
    >>> from trytond.modules.company.tests.tools import create_company
    >>> from trytond.tests.tools import activate_modules

Activate modules::

    >>> config = activate_modules(
    ...     'sale_shipment_tolerance', create_company, create_chart)

Get accounts::

    >>> accounts = get_accounts()
    >>> revenue = accounts['revenue']

Create parties::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account category::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
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
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

Set tolerance::

    >>> Configuration = Model.get('sale.configuration')
    >>> config = Configuration(1)
    >>> config.sale_over_shipment_tolerance = 1.2
    >>> config.save()

Sale 10 products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale_line = sale.lines.new()
    >>> sale_line.product = product
    >>> sale_line.quantity = 10
    >>> sale.click('quote')
    >>> sale.click('confirm')
    >>> sale.click('process')

Prevent over ship 13 products::

    >>> shipment, = sale.shipments
    >>> shipment.click('draft')
    >>> move, = shipment.outgoing_moves
    >>> move.quantity = 13
    >>> shipment.click('wait')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    Traceback (most recent call last):
        ...
    OverShipmentWarning: ...

Cancel shipment and recreate::

    >>> shipment.click('cancel')
    >>> shipment.state
    'cancelled'

    >>> handle_shipment_exception = Wizard('sale.handle.shipment.exception', [sale])
    >>> handle_shipment_exception.form.recreate_moves.extend(
    ...     handle_shipment_exception.form.recreate_moves.find())
    >>> handle_shipment_exception.execute('handle')

Over ship 12 products::

    >>> shipment, = [s for s in sale.shipments if s.state != 'cancelled']
    >>> shipment.click('draft')
    >>> move, = shipment.outgoing_moves
    >>> move.quantity = 12
    >>> shipment.click('wait')
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('do')

No new shipment as shipped inside tolerance::

    >>> sale.reload()
    >>> len(sale.shipments)
    2
