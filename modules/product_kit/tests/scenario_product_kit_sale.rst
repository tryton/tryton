=========================
Sale Product Kit Scenario
=========================

Imports::

    >>> from decimal import Decimal
    >>> from proteus import Model, Wizard
    >>> from trytond.tests.tools import activate_modules
    >>> from trytond.modules.company.tests.tools import (
    ...     create_company, get_company)
    >>> from trytond.modules.account.tests.tools import (
    ...     create_fiscalyear, create_chart, get_accounts)
    >>> from trytond.modules.account_invoice.tests.tools import (
    ...     set_fiscalyear_invoice_sequences)

Activate product_kit, sale and account_invoice::

    >>> config = activate_modules(
    ...     ['product_kit', 'sale', 'account_invoice',
    ...         'account_invoice_stock'])

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

Create party::

    >>> Party = Model.get('party.party')
    >>> customer = Party(name='Customer')
    >>> customer.save()

Create account categories::

    >>> ProductCategory = Model.get('product.category')
    >>> account_category = ProductCategory(name="Account Category")
    >>> account_category.accounting = True
    >>> account_category.account_expense = accounts['expense']
    >>> account_category.account_revenue = accounts['revenue']
    >>> account_category.save()

Create products::

    >>> ProductUom = Model.get('product.uom')
    >>> unit, = ProductUom.find([('name', '=', 'Unit')])
    >>> meter, = ProductUom.find([('name', '=', "Meter")])
    >>> ProductTemplate = Model.get('product.template')

    >>> template = ProductTemplate()
    >>> template.name = "Product 1"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product1, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Product 2"
    >>> template.default_uom = meter
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('20')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product2, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Product 3"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.list_price = Decimal('30')
    >>> template.account_category = account_category
    >>> template.save()
    >>> product3, = template.products

    >>> template = ProductTemplate()
    >>> template.name = "Service"
    >>> template.default_uom = unit
    >>> template.type = 'service'
    >>> template.salable = True
    >>> template.list_price = Decimal('30')
    >>> template.account_category = account_category
    >>> template.save()
    >>> service, = template.products

Create composed product::

    >>> template = ProductTemplate()
    >>> template.name = "Composed Product"
    >>> template.default_uom = unit
    >>> template.type = 'goods'
    >>> template.salable = True
    >>> template.list_price = Decimal('10')
    >>> template.account_category = account_category
    >>> template.save()
    >>> composed_product, = template.products

    >>> component = composed_product.components.new()
    >>> component.product = product1
    >>> component.quantity = 2
    >>> component = composed_product.components.new()
    >>> component.product = service
    >>> component.quantity = 1
    >>> component.fixed = True
    >>> composed_product.save()

Create kit product::

    >>> template = ProductTemplate()
    >>> template.name = "Kit"
    >>> template.default_uom = unit
    >>> template.type = 'kit'
    >>> template.salable = True
    >>> template.list_price = Decimal('40')
    >>> template.account_category = account_category
    >>> template.save()
    >>> kit, = template.products

    >>> component = kit.components.new()
    >>> component.product = product2
    >>> component.quantity = 1
    >>> component = kit.components.new()
    >>> component.product = product3
    >>> component.quantity = 2
    >>> component.fixed = True
    >>> kit.save()

Sale composed and kit products::

    >>> Sale = Model.get('sale.sale')
    >>> sale = Sale()
    >>> sale.party = customer
    >>> sale.invoice_method = 'shipment'
    >>> line = sale.lines.new()
    >>> line.product = composed_product
    >>> line.quantity = 2
    >>> line = sale.lines.new()
    >>> line.product = kit
    >>> line.quantity = 5
    >>> sale.click('quote')
    >>> len(sale.lines)
    4
    >>> [l.quantity for l in sale.lines]
    [2.0, 4.0, 1.0, 5.0]
    >>> line_kit, = [l for l in sale.lines if l.product == kit]
    >>> [c.quantity for c in line_kit.components]
    [5.0, 2.0]

Reset to draft remove components::

    >>> sale.click('draft')
    >>> line_kit, = [l for l in sale.lines if l.product == kit]
    >>> bool(line_kit.components)
    False
    >>> sale.click('quote')

Process sale::

    >>> sale.click('confirm')
    >>> sale.state
    'processing'
    >>> len(sale.shipments), len(sale.invoices)
    (1, 1)

Check invoice::

    >>> invoice, = sale.invoices
    >>> line, = invoice.lines
    >>> line.product == service
    True

Check shipment::

    >>> shipment, = sale.shipments
    >>> len(shipment.outgoing_moves)
    4
    >>> product2quantity = {
    ...     m.product: m.quantity for m in shipment.outgoing_moves}
    >>> product2quantity[composed_product]
    2.0
    >>> product2quantity[product1]
    4.0
    >>> product2quantity[product2]
    5.0
    >>> product2quantity[product3]
    2.0

Ship partially::

    >>> product2move = {
    ...     m.product: m for m in shipment.inventory_moves}
    >>> product2move[product1].quantity = 2.0
    >>> product2move[product2].quantity = 3.0
    >>> shipment.click('assign_force')
    >>> shipment.click('pick')
    >>> shipment.click('pack')
    >>> shipment.click('done')
    >>> shipment.state
    'done'

Check new invoice::

    >>> sale.reload()
    >>> _, invoice = sale.invoices
    >>> len(invoice.lines)
    3
    >>> product2quantity = {l.product: l.quantity for l in invoice.lines}
    >>> product2quantity[composed_product]
    2.0
    >>> product2quantity[product1]
    2.0
    >>> product2quantity[kit]
    3.0

Post invoice::

    >>> invoice.click('post')
    >>> invoice.state
    'posted'

Check unit price of moves::

    >>> shipment.reload()
    >>> invoice.reload()
    >>> sorted([m.unit_price for m in shipment.outgoing_moves])
    [Decimal('10.0000'), Decimal('10.0000'), Decimal('15.0000'), Decimal('25.0000')]

Check backorder::

    >>> _, backorder = sale.shipments
    >>> len(backorder.outgoing_moves)
    2
    >>> product2quantity = {
    ...     m.product: m.quantity for m in backorder.outgoing_moves}
    >>> product2quantity[product1]
    2.0
    >>> product2quantity[product2]
    2.0

Cancel backorder::

    >>> backorder.click('cancel')
    >>> backorder.state
    'cancelled'
    >>> sale.reload()
    >>> sale.shipment_state
    'exception'

Handle shipment exception::

    >>> shipment_exception = Wizard('sale.handle.shipment.exception', [sale])
    >>> move, = [
    ...     m for m in shipment_exception.form.recreate_moves
    ...     if m.product == product1]
    >>> shipment_exception.form.recreate_moves.remove(move)
    >>> shipment_exception.execute('handle')

    >>> _, _, shipment = sale.shipments
    >>> len(shipment.outgoing_moves)
    1
