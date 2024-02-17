====================================
Account Stock Shipment Cost Scenario
====================================

Imports::

    >>> import datetime as dt
    >>> from decimal import Decimal

    >>> from proteus import Model
    >>> from trytond.modules.account.tests.tools import (
    ...     create_chart, create_fiscalyear, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)
    >>> from trytond.modules.account_stock_shipment_cost.exceptions import (
    ...     SamePartiesWarning)
    >>> from trytond.modules.company.tests.tools import create_company, get_company
    >>> from trytond.tests.tools import activate_modules

    >>> today = dt.date.today()

Activate modules::

    >>> config = activate_modules('account_stock_shipment_cost')

    >>> Invoice = Model.get('account.invoice')
    >>> InvoiceLine = Model.get('account.invoice.line')
    >>> Location = Model.get('stock.location')
    >>> Party = Model.get('party.party')
    >>> ProductCategory = Model.get('product.category')
    >>> ProductTemplate = Model.get('product.template')
    >>> ProductUom = Model.get('product.uom')
    >>> ShipmentOut = Model.get('stock.shipment.out')
    >>> ShipmentCost = Model.get('account.shipment_cost')
    >>> Warning = Model.get('res.user.warning')

Create company::

    >>> _ = create_company()
    >>> company = get_company()

Create fiscal year::

    >>> fiscalyear = set_fiscalyear_invoice_sequences(
    ...     create_fiscalyear(company, today))
    >>> fiscalyear.click('create_period')

Create chart of accounts::

    >>> _ = create_chart(company)
    >>> accounts = get_accounts(company)

Create parties::

    >>> customer = Party(name="Customer")
    >>> customer.save()
    >>> carrier = Party(name="Carrier")
    >>> carrier.save()

Create account category::

    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create products::

    >>> unit, = ProductUom.find([('name', '=', "Unit")])
    >>> template = ProductTemplate()
    >>> template.name = "Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('100.00')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Shipment Cost"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.shipment_cost = True
    >>> template.list_price = Decimal('4.00')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product_shipment_cost, = template.products

Get stock locations::

    >>> warehouse_loc, = Location.find([('code', '=', 'WH')])
    >>> customer_loc, = Location.find([('code', '=', 'CUS')])
    >>> output_loc, = Location.find([('code', '=', 'OUT')])
    >>> storage_loc, = Location.find([('code', '=', 'STO')])

Ship twice 10 unit of the product::

    >>> shipment1 = ShipmentOut()
    >>> shipment1.customer = customer
    >>> shipment1.cost_edit = True
    >>> shipment1.cost_used = Decimal('4.00')
    >>> shipment1.cost_currency_used = company.currency
    >>> move = shipment1.outgoing_moves.new()
    >>> move.product = product
    >>> move.quantity = 10
    >>> move.from_location = output_loc
    >>> move.to_location = customer_loc
    >>> move.unit_price = Decimal('100.00')
    >>> move.currency = company.currency
    >>> shipment1.click('wait')
    >>> shipment1.click('assign_force')
    >>> shipment1.click('pick')
    >>> shipment1.click('pack')
    >>> shipment1.click('do')
    >>> shipment1.state
    'done'

    >>> shipment2, = shipment1.duplicate()
    >>> shipment2.click('wait')
    >>> shipment2.click('assign_force')
    >>> shipment2.click('pick')
    >>> shipment2.click('pack')
    >>> shipment2.click('do')
    >>> shipment2.state
    'done'

Invoice shipment cost::

    >>> invoice = Invoice(type='in')
    >>> invoice.party = carrier
    >>> invoice.invoice_date = today
    >>> line = invoice.lines.new()
    >>> line.product = product_shipment_cost
    >>> line.quantity = 2
    >>> line.unit_price = Decimal('5.00')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Add shipment cost to both shipments::

    >>> shipment_cost1 = ShipmentCost()
    >>> shipment_cost1.invoice_lines.extend(
    ...     shipment_cost1.invoice_lines.find([]))
    >>> shipment_cost1.shipments.extend(
    ...     shipment_cost1.shipments.find([]))
    >>> shipment_cost1.save()
    >>> shipment_cost1.state
    'draft'
    >>> bool(shipment_cost1.number)
    True
    >>> post_shipment_cost = shipment_cost1.click('post_wizard')
    >>> post_shipment_cost.form.cost
    Decimal('10.0000')
    >>> sorted([s.cost for s in post_shipment_cost.form.shipments])
    [Decimal('5.0000'), Decimal('5.0000')]
    >>> post_shipment_cost.execute('post')
    >>> shipment_cost1.state
    'posted'
    >>> bool(shipment_cost1.posted_date)
    True

Show shipment cost::

    >>> show_shipment_cost = shipment_cost1.click('show')
    >>> show_shipment_cost.form.cost
    Decimal('10.0000')
    >>> sorted([s.cost for s in show_shipment_cost.form.shipments])
    [Decimal('5.0000'), Decimal('5.0000')]

Check shipment cost::

    >>> shipment1.reload()
    >>> shipment1.cost
    Decimal('5.0000')
    >>> shipment2.reload()
    >>> shipment2.cost
    Decimal('5.0000')

Add a second shipment cost to 1 shipment::

    >>> invoice, = invoice.duplicate()
    >>> invoice.invoice_date = today
    >>> line, = invoice.lines
    >>> line.quantity = 1
    >>> line.unit_price = Decimal('2.00')
    >>> invoice.click('post')
    >>> invoice.state
    'posted'

    >>> shipment_cost2 = ShipmentCost()
    >>> shipment_cost2.invoice_lines.append(InvoiceLine(line.id))
    >>> shipment_cost2.shipments.append(ShipmentOut(shipment1.id))
    >>> shipment_cost2.save()
    >>> post_shipment_cost = shipment_cost2.click('post_wizard')
    >>> post_shipment_cost.form.cost
    Decimal('2.0000')
    >>> sorted([s.cost for s in post_shipment_cost.form.shipments])
    [Decimal('2.0000')]
    >>> try:
    ...     post_shipment_cost.execute('post')
    ... except SamePartiesWarning as warning:
    ...     _, (key, *_) = warning.args
    ...     raise
    Traceback (most recent call last):
        ...
    SamePartiesWarning: ...
    >>> Warning(user=config.user, name=key).save()
    >>> post_shipment_cost.execute('post')
    >>> shipment_cost2.state
    'posted'

Check shipment cost::

    >>> shipment1.reload()
    >>> shipment1.cost
    Decimal('7.0000')
    >>> shipment2.reload()
    >>> shipment2.cost
    Decimal('5.0000')

Cancel shipment cost remove the price::

    >>> shipment_cost1.click('cancel')
    >>> shipment_cost1.state
    'cancelled'
    >>> shipment_cost1.posted_date

Check shipment cost::

    >>> shipment1.reload()
    >>> shipment1.cost
    Decimal('2.0000')
    >>> shipment2.reload()
    >>> shipment2.cost
    Decimal('0.0000')
